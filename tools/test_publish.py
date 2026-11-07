"""Tests for tools/publish.py (standard library and git only; no network, no gh)."""
import datetime
import os
import subprocess
import tempfile
import unittest

import publish

ACCOUNT = ("example-user", "example-user@users.noreply.github.com")
CONFIG = ('name: "Marketplace Guard"\nversion: "{v}"\nslug: "marketplace_guard"\n'
          'description: "Example."\narch:\n  - amd64\n')
REPOSITORY = 'name: "Marketplace Guard"\nurl: "https://github.com/OWNER/marketplace-guard"\nmaintainer: "OWNER"\n'


def run(*args, cwd):
    env = dict(os.environ, GIT_AUTHOR_NAME="dev", GIT_AUTHOR_EMAIL="dev@example.org", GIT_COMMITTER_NAME="dev",
               GIT_COMMITTER_EMAIL="dev@example.org", GIT_AUTHOR_DATE="2026-01-02T13:14:15+0100",
               GIT_COMMITTER_DATE="2026-01-02T13:14:15+0100")
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env, capture_output=True,
                          text=True, check=True).stdout


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


class Sandbox(unittest.TestCase):
    """A development repository at version 1.0.0 and an empty public (bare) repository."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev = os.path.join(self.tmp.name, "dev")
        self.public = os.path.join(self.tmp.name, "public.git")
        os.makedirs(self.dev)
        run("init", "--quiet", "-b", "main", cwd=self.dev)
        run("init", "--quiet", "--bare", "-b", "main", self.public, cwd=self.tmp.name)
        write(self.dev, "repository.yaml", REPOSITORY)
        write(self.dev, "marketplace_guard/config.yaml", CONFIG.format(v="1.0.0"))
        write(self.dev, "marketplace_guard/CHANGELOG.md", "# Changelog\n\n## 1.0.0\n- First.\n")
        write(self.dev, "secret-history.txt", "removed later\n")
        run("add", "-A", cwd=self.dev)
        run("commit", "--quiet", "-m", "first, with a file that is removed later", cwd=self.dev)
        run("rm", "--quiet", "secret-history.txt", cwd=self.dev)
        run("commit", "--quiet", "-m", "remove it", cwd=self.dev)
        self.saved_root = publish.ROOT
        publish.ROOT = self.dev

    def tearDown(self):
        publish.ROOT = self.saved_root
        self.tmp.cleanup()

    def release(self, day=datetime.date(2026, 11, 7)):
        """Run the publication steps after the checks (no gate run, no gh) and push to the public repository."""
        sha, version = publish.check_source("main", run_checks=False)
        work = tempfile.mkdtemp(dir=self.tmp.name)
        tree = os.path.join(work, "tree")
        os.makedirs(tree)
        publish.export_tree(sha, tree)
        publish.fill_public_fields(tree, *ACCOUNT)
        path, empty = publish.prepare_public(self.public, work, version)
        changelog = publish.changelog_section(publish.read_at(sha, "marketplace_guard/CHANGELOG.md"), version)
        new = publish.commit_release(path, tree, version, changelog, empty, publish.neutral_date(day), ACCOUNT)
        run("push", "--quiet", "origin", "HEAD:refs/heads/main", f"refs/tags/v{version}", cwd=path)
        return new, empty


class TestHelpers(unittest.TestCase):
    def test_changelog_section(self):
        text = "# Changelog\n\n## 2.0.0\n- New name.\n- More.\n\n## 1.7.2\n- Old.\n"
        self.assertEqual(publish.changelog_section(text, "2.0.0"), "- New name.\n- More.")
        self.assertEqual(publish.changelog_section(text, "1.7.2"), "- Old.")
        self.assertIsNone(publish.changelog_section(text, "9.9.9"))

    def test_neutral_date_has_no_time_of_day_or_zone(self):
        self.assertEqual(publish.neutral_date(datetime.date(2026, 11, 7)), "2026-11-07T00:00:00+0000")

    def test_account_names(self):
        self.assertEqual(publish.publishing_account("example-user"), ACCOUNT)
        with self.assertRaises(publish.Refused):
            publish.publishing_account("not a name/../x")


class TestRefusals(Sandbox):
    def test_untracked_file_refuses(self):
        write(self.dev, "stray.txt", "x\n")
        with self.assertRaises(publish.Refused):
            publish.check_source("main", run_checks=False)

    def test_head_not_at_ref_refuses(self):
        run("switch", "--quiet", "-c", "topic", cwd=self.dev)
        write(self.dev, "topic.txt", "x\n")
        run("add", "-A", cwd=self.dev)
        run("commit", "--quiet", "-m", "topic", cwd=self.dev)
        with self.assertRaises(publish.Refused):
            publish.check_source("main", run_checks=False)

    def test_version_without_release_number_refuses(self):
        write(self.dev, "marketplace_guard/config.yaml", CONFIG.format(v="2.0.0-dev"))
        run("commit", "--quiet", "-am", "dev version", cwd=self.dev)
        with self.assertRaises(publish.Refused):
            publish.check_source("main", run_checks=False)

    def test_published_version_refuses(self):
        self.release()
        with self.assertRaises(publish.Refused):
            self.release()

    def test_commit_made_by_hand_in_public_refuses(self):
        self.release()
        hand = os.path.join(self.tmp.name, "hand")
        run("clone", "--quiet", self.public, hand, cwd=self.tmp.name)
        write(hand, "issue-template.md", "x\n")
        run("add", "-A", cwd=hand)
        run("commit", "--quiet", "-m", "added on the website", cwd=hand)
        run("push", "--quiet", "origin", "HEAD:main", cwd=hand)
        write(self.dev, "marketplace_guard/config.yaml", CONFIG.format(v="1.0.1"))
        run("commit", "--quiet", "-am", "1.0.1", cwd=self.dev)
        with self.assertRaises(publish.Refused):
            self.release()

    def test_missing_field_line_refuses(self):
        tree = tempfile.mkdtemp(dir=self.tmp.name)
        write(tree, "repository.yaml", 'name: "x"\n')
        write(tree, "marketplace_guard/config.yaml", CONFIG.format(v="1.0.0"))
        with self.assertRaises(publish.Refused):
            publish.fill_public_fields(tree, *ACCOUNT)


class TestPublication(Sandbox):
    def public_clone(self):
        path = os.path.join(self.tmp.name, f"check{len(os.listdir(self.tmp.name))}")
        run("clone", "--quiet", self.public, path, cwd=self.tmp.name)
        return path

    def test_start_commit_carries_the_tree_not_the_history(self):
        new, empty = self.release()
        self.assertTrue(empty)
        pub = self.public_clone()
        self.assertEqual(run("rev-list", "--count", "HEAD", cwd=pub).strip(), "1")
        meta = run("log", "-1", "--format=%an <%ae>|%cn <%ce>|%ai|%ci|%B", cwd=pub)
        self.assertIn(f"{ACCOUNT[0]} <{ACCOUNT[1]}>|{ACCOUNT[0]} <{ACCOUNT[1]}>", meta)
        self.assertIn("2026-11-07 00:00:00 +0000|2026-11-07 00:00:00 +0000", meta)
        self.assertIn(publish.TRAILER, meta)
        files = sorted(run("ls-tree", "-r", "--name-only", "HEAD", cwd=pub).split())
        self.assertEqual(files, ["marketplace_guard/CHANGELOG.md", "marketplace_guard/config.yaml", "repository.yaml"])
        dev_commits = run("rev-list", "--all", cwd=self.dev).split()
        for sha in dev_commits:  # no object of the development history reaches the public repository
            self.assertNotEqual(subprocess.run(["git", "cat-file", "-e", sha], cwd=pub).returncode, 0)
        self.assertEqual(run("tag", "--list", cwd=pub).split(), ["v1.0.0"])

    def test_the_account_is_written_into_the_published_copy_only(self):
        self.release()
        pub = self.public_clone()
        with open(os.path.join(pub, "repository.yaml"), encoding="utf-8") as f:
            repo = f.read()
        with open(os.path.join(pub, "marketplace_guard", "config.yaml"), encoding="utf-8") as f:
            config = f.read()
        url = "https://github.com/example-user/marketplace-guard"
        self.assertIn(f'url: "{url}"', repo)
        self.assertIn(f'maintainer: "{ACCOUNT[0]} <{ACCOUNT[1]}>"', repo)
        self.assertIn(f'description: "Example."\nurl: "{url}"', config)
        with open(os.path.join(self.dev, "repository.yaml"), encoding="utf-8") as f:
            self.assertEqual(f.read(), REPOSITORY)  # the development repository keeps its placeholders

    def test_next_release_is_one_more_commit_with_its_changelog(self):
        self.release()
        write(self.dev, "marketplace_guard/config.yaml", CONFIG.format(v="1.1.0"))
        write(self.dev, "marketplace_guard/CHANGELOG.md", "# Changelog\n\n## 1.1.0\n- Second.\n\n## 1.0.0\n- First.\n")
        run("commit", "--quiet", "-am", "1.1.0", cwd=self.dev)
        new, empty = self.release(datetime.date(2026, 12, 1))
        self.assertFalse(empty)
        pub = self.public_clone()
        self.assertEqual(run("rev-list", "--count", "HEAD", cwd=pub).strip(), "2")
        body = run("log", "-1", "--format=%B", cwd=pub)
        self.assertTrue(body.startswith("Marketplace Guard 1.1.0\n\n- Second."))
        self.assertEqual(sorted(run("tag", "--list", cwd=pub).split()), ["v1.0.0", "v1.1.0"])


if __name__ == "__main__":
    unittest.main()
