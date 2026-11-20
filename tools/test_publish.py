"""Tests for tools/publish.py (standard library and git only; no network, no gh)."""
import datetime
import json
import os
import subprocess
import tempfile
import unittest

import publish

ACCOUNT = ("example-user", "example-user@users.noreply.github.com")
URLS = {"app": "https://github.com/example-user/marketplace-guard",
        "gate": "https://github.com/example-user/marketplace-guard-gate"}
CONFIG = ('name: "Marketplace Guard"\nversion: "{v}"\nslug: "marketplace_guard"\n'
          'description: "Example."\narch:\n  - amd64\n')
REPOSITORY = 'name: "Marketplace Guard"\nurl: "https://github.com/OWNER/marketplace-guard"\nmaintainer: "OWNER"\n'
README = "# Marketplace Guard\n\nInstall:\n\n<!-- publish: install -->\n\nMore.\n"
GATE_README = ("# Marketplace Guard Gate\n\nThe app:\n\n<!-- publish: install -->\n\nThe gate:\n\n"
               "<!-- publish: marketplace -->\n\nMore.\n")
GATE = "marketplace_guard/gate/marketplace_guard_gate"


def gate_manifest(version):
    return json.dumps({"domain": "marketplace_guard_gate", "name": "Marketplace Guard Gate", "codeowners": [],
                       "documentation": "https://github.com/OWNER/marketplace-guard-gate",
                       "issue_tracker": "https://github.com/OWNER/marketplace-guard-gate/issues",
                       "version": version}, indent=2) + "\n"


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
    """A development repository at version 1.0.0 and two empty public (bare) repositories: the app's and the gate's."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dev = os.path.join(self.tmp.name, "dev")
        self.public = os.path.join(self.tmp.name, "public.git")
        self.public_gate = os.path.join(self.tmp.name, "public-gate.git")
        os.makedirs(self.dev)
        run("init", "--quiet", "-b", "main", cwd=self.dev)
        for bare in (self.public, self.public_gate):
            run("init", "--quiet", "--bare", "-b", "main", bare, cwd=self.tmp.name)
        write(self.dev, "repository.yaml", REPOSITORY)
        write(self.dev, "README.md", README)
        write(self.dev, "LICENSE", "MIT License\n")
        write(self.dev, "marketplace_guard/config.yaml", CONFIG.format(v="1.0.0"))
        write(self.dev, "marketplace_guard/CHANGELOG.md", "# Changelog\n\n## 1.0.0\n- First.\n")
        write(self.dev, f"{GATE}/__init__.py", '"""The gate."""\n')
        write(self.dev, f"{GATE}/manifest.json", gate_manifest("1.0.0"))
        write(self.dev, "gate_repository/README.md", GATE_README)
        write(self.dev, "gate_repository/hacs.json", '{"name": "Marketplace Guard Gate"}\n')
        write(self.dev, "gate_repository/.github/workflows/validate.yml", "name: Validate\n")
        write(self.dev, "secret-history.txt", "removed later\n")
        run("add", "-A", cwd=self.dev)
        run("commit", "--quiet", "-m", "first, with a file that is removed later", cwd=self.dev)
        run("rm", "--quiet", "secret-history.txt", cwd=self.dev)
        run("commit", "--quiet", "-m", "remove it", cwd=self.dev)
        self.saved = (publish.ROOT, publish.check_source)
        publish.ROOT = self.dev

    def tearDown(self):
        publish.ROOT, publish.check_source = self.saved
        self.tmp.cleanup()

    def bump(self, version, changelog):
        write(self.dev, "marketplace_guard/config.yaml", CONFIG.format(v=version))
        write(self.dev, f"{GATE}/manifest.json", gate_manifest(version))
        write(self.dev, "marketplace_guard/CHANGELOG.md", changelog)
        run("commit", "--quiet", "-am", version, cwd=self.dev)

    def release(self, day=datetime.date(2026, 11, 7)):
        """Run the publication steps after the checks (no gate run, no gh) and push to both public repositories.
        Returns (sha, state) of the app repository."""
        sha, version = publish.check_source("main", run_checks=False)
        work = tempfile.mkdtemp(dir=self.tmp.name)
        tree = os.path.join(work, "tree")
        os.makedirs(tree)
        publish.export_tree(sha, tree)
        urls = publish.fill_public_fields(tree, *ACCOUNT)
        publish.fill_install(tree, urls)
        trees = {"app": tree, "gate": publish.build_gate_tree(tree, os.path.join(work, "gate-tree"), version)}
        text = publish.read_at(sha, "marketplace_guard/CHANGELOG.md")
        out = {}
        for target, public in zip(publish.TARGETS, (self.public, self.public_gate)):
            workdir = os.path.join(work, target.key)
            os.makedirs(workdir)
            path, state = publish.prepare_public(public, workdir, version)
            notes = publish.release_notes(target, publish.changelog_since(text, version, publish.newest_published(path)),
                                          version, urls)
            out[target.key] = (publish.commit_release(path, trees[target.key], version, notes, state == "empty",
                                                      publish.neutral_date(day), ACCOUNT, target.title), state)
            run("push", "--quiet", "origin", "HEAD:refs/heads/main", f"refs/tags/v{version}", cwd=path)
        return out["app"]

    def main(self, *extra):
        """tools/publish.py's main() against the local public repositories, without the check run and without gh."""
        original = self.saved[1]
        publish.check_source = lambda ref, run_checks: original(ref, run_checks=False)
        return publish.main(["--owner", ACCOUNT[0], "--public", self.public, "--public-gate", self.public_gate,
                             *extra])


class TestHelpers(unittest.TestCase):
    def test_changelog_section(self):
        text = "# Changelog\n\n## 2.0.0\n- New name.\n- More.\n\n## 1.7.2\n- Old.\n"
        self.assertEqual(publish.changelog_section(text, "2.0.0"), "- New name.\n- More.")
        self.assertEqual(publish.changelog_section(text, "1.7.2"), "- Old.")
        self.assertIsNone(publish.changelog_section(text, "9.9.9"))

    def test_release_notes_name_every_version_since_the_last_publication(self):
        text = ("# Changelog\n\n## 2.3.0\n- Page.\n\n## 2.2.0\n- Action.\n\n## 2.1.0\n- Summary.\n\n"
                "## 2.0.2\n- Texts.\n")
        self.assertEqual(publish.changelog_since(text, "2.3.0", "2.0.2"),
                         "## 2.3.0\n- Page.\n\n## 2.2.0\n- Action.\n\n## 2.1.0\n- Summary.")
        self.assertEqual(publish.changelog_since(text, "2.3.0", "2.2.0"), "- Page.")
        self.assertEqual(publish.changelog_since(text, "2.3.0"), "- Page.")
        self.assertIsNone(publish.changelog_since(text, "9.9.9"))

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
        self.bump("1.0.1", "# Changelog\n\n## 1.0.1\n- Fix.\n\n## 1.0.0\n- First.\n")
        with self.assertRaisesRegex(publish.Refused, "was not made by tools/publish.py"):
            self.release()

    def test_missing_field_line_refuses(self):
        tree = tempfile.mkdtemp(dir=self.tmp.name)
        write(tree, "repository.yaml", 'name: "x"\n')
        write(tree, "marketplace_guard/config.yaml", CONFIG.format(v="1.0.0"))
        with self.assertRaises(publish.Refused):
            publish.fill_public_fields(tree, *ACCOUNT)

    def test_a_gate_manifest_without_a_key_to_fill_in_refuses(self):
        tree = tempfile.mkdtemp(dir=self.tmp.name)
        manifest = json.loads(gate_manifest("1.0.0"))
        del manifest["issue_tracker"]
        write(tree, f"{GATE}/manifest.json", json.dumps(manifest))
        with self.assertRaisesRegex(publish.Refused, "has no issue_tracker to fill in"):
            publish.fill_gate_manifest(tree, ACCOUNT[0], URLS["gate"])
        write(tree, f"{GATE}/manifest.json", "not json")
        with self.assertRaisesRegex(publish.Refused, "does not hold a JSON object"):
            publish.fill_gate_manifest(tree, ACCOUNT[0], URLS["gate"])

    def test_readme_without_install_marker_refuses(self):
        tree = tempfile.mkdtemp(dir=self.tmp.name)
        write(tree, "README.md", "# Marketplace Guard\n\nNo marker.\n")
        write(tree, "gate_repository/README.md", GATE_README)
        with self.assertRaisesRegex(publish.Refused, "README.md has no line `<!-- publish: install -->`"):
            publish.fill_install(tree, URLS)

    def test_gate_readme_without_its_markers_refuses(self):
        for text in ("# Gate\n\n<!-- publish: install -->\n", "# Gate\n\n<!-- publish: marketplace -->\n", None):
            with self.subTest(text=text):
                tree = tempfile.mkdtemp(dir=self.tmp.name)
                write(tree, "README.md", README)
                if text is not None:
                    write(tree, "gate_repository/README.md", text)
                with self.assertRaisesRegex(publish.Refused, "gate_repository/README.md"):
                    publish.fill_install(tree, URLS)

    def test_install_marker_left_in_another_file_refuses(self):
        for marker in ("<!-- publish: install -->", "<!-- publish: marketplace -->"):
            with self.subTest(marker=marker):
                tree = tempfile.mkdtemp(dir=self.tmp.name)
                write(tree, "README.md", README)
                write(tree, "gate_repository/README.md", GATE_README)
                write(tree, "marketplace_guard/README.md", f"# App\n\n{marker}\n")
                with self.assertRaisesRegex(publish.Refused, "still holds"):
                    publish.fill_install(tree, URLS)

    def test_marker_named_inside_a_line_is_not_a_marker(self):
        tree = tempfile.mkdtemp(dir=self.tmp.name)
        write(tree, "README.md", README)
        write(tree, "gate_repository/README.md", GATE_README)
        write(tree, "AGENTS.md", "The line `<!-- publish: install -->` in README.md is filled by publish.py.\n")
        publish.fill_install(tree, URLS)

    def test_a_gate_without_the_release_version_or_a_part_refuses(self):
        sha, version = publish.check_source("main", run_checks=False)
        for broken, expected in ((f"{GATE}/manifest.json", "has version '0.9.0'"), ("LICENSE", "LICENSE"),
                                 ("gate_repository/hacs.json", "gate_repository/hacs.json")):
            with self.subTest(broken=broken):
                tree = tempfile.mkdtemp(dir=self.tmp.name)
                publish.export_tree(sha, tree)
                if broken.endswith("manifest.json"):
                    write(tree, broken, gate_manifest("0.9.0"))
                else:
                    os.remove(os.path.join(tree, *broken.split("/")))
                with self.assertRaisesRegex(publish.Refused, expected):
                    publish.build_gate_tree(tree, os.path.join(tree, "..", os.path.basename(tree) + "-gate"), version)


class TestPublication(Sandbox):
    def public_clone(self, public=None):
        path = os.path.join(self.tmp.name, f"check{len(os.listdir(self.tmp.name))}")
        run("clone", "--quiet", public or self.public, path, cwd=self.tmp.name)
        return path

    def read(self, root, rel):
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as f:
            return f.read()

    def test_start_commit_carries_the_tree_not_the_history(self):
        new, state = self.release()
        self.assertEqual(state, "empty")
        pub = self.public_clone()
        self.assertEqual(run("rev-list", "--count", "HEAD", cwd=pub).strip(), "1")
        meta = run("log", "-1", "--format=%an <%ae>|%cn <%ce>|%ai|%ci|%B", cwd=pub)
        self.assertIn(f"{ACCOUNT[0]} <{ACCOUNT[1]}>|{ACCOUNT[0]} <{ACCOUNT[1]}>", meta)
        self.assertIn("2026-11-07 00:00:00 +0000|2026-11-07 00:00:00 +0000", meta)
        self.assertIn(publish.TRAILER, meta)
        files = sorted(run("ls-tree", "-r", "--name-only", "HEAD", cwd=pub).split())
        self.assertEqual(files, ["LICENSE", "README.md", "gate_repository/.github/workflows/validate.yml",
                                 "gate_repository/README.md", "gate_repository/hacs.json",
                                 "marketplace_guard/CHANGELOG.md", "marketplace_guard/config.yaml",
                                 f"{GATE}/__init__.py", f"{GATE}/manifest.json", "repository.yaml"])
        dev_commits = run("rev-list", "--all", cwd=self.dev).split()
        for public in (pub, self.public_clone(self.public_gate)):
            for sha in dev_commits:  # no object of the development history reaches a public repository
                self.assertNotEqual(subprocess.run(["git", "cat-file", "-e", sha], cwd=public).returncode, 0)
            self.assertEqual(run("tag", "--list", cwd=public).split(), ["v1.0.0"])

    def test_the_gate_repository_holds_the_gate_its_files_and_the_license(self):
        self.release()
        gate = self.public_clone(self.public_gate)
        files = sorted(run("ls-tree", "-r", "--name-only", "HEAD", cwd=gate).split())
        self.assertEqual(files, [".github/workflows/validate.yml", "LICENSE", "README.md",
                                 "custom_components/marketplace_guard_gate/__init__.py",
                                 "custom_components/marketplace_guard_gate/manifest.json", "hacs.json"])
        body = run("log", "-1", "--format=%an|%ai|%B", cwd=gate)
        self.assertTrue(body.startswith(f"{ACCOUNT[0]}|2026-11-07 00:00:00 +0000|Marketplace Guard Gate 1.0.0\n"))
        self.assertIn("the tree of Marketplace Guard Gate 1.0.0", body)
        self.assertIn(publish.TRAILER, body)

    def test_the_account_is_written_into_the_published_copy_only(self):
        self.release()
        pub = self.public_clone()
        repo, config = self.read(pub, "repository.yaml"), self.read(pub, "marketplace_guard/config.yaml")
        url = URLS["app"]
        self.assertIn(f'url: "{url}"', repo)
        self.assertIn(f'maintainer: "{ACCOUNT[0]} <{ACCOUNT[1]}>"', repo)
        self.assertIn(f'description: "Example."\nurl: "{url}"', config)
        gate = self.public_clone(self.public_gate)
        for manifest in (json.loads(self.read(pub, f"{GATE}/manifest.json")),
                         json.loads(self.read(gate, "custom_components/marketplace_guard_gate/manifest.json"))):
            self.assertEqual(manifest["documentation"], URLS["gate"])
            self.assertEqual(manifest["issue_tracker"], URLS["gate"] + "/issues")
            self.assertEqual(manifest["codeowners"], [f"@{ACCOUNT[0]}"])
            self.assertEqual(list(manifest)[:2], ["domain", "name"])  # the order hassfest asks for is kept
        self.assertEqual(self.read(self.dev, "repository.yaml"), REPOSITORY)  # the development repository keeps its
        self.assertEqual(self.read(self.dev, f"{GATE}/manifest.json"), gate_manifest("1.0.0"))  # placeholders

    def test_the_readme_gets_the_install_button_in_the_published_copy_only(self):
        self.release()
        pub = self.public_clone()
        readme = self.read(pub, "README.md")
        self.assertNotIn("<!-- publish: install -->", readme)
        self.assertIn("https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url="
                      "https%3A%2F%2Fgithub.com%2Fexample-user%2Fmarketplace-guard)", readme)
        self.assertIn("https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg", readme)
        self.assertIn("Repository URL: `https://github.com/example-user/marketplace-guard`", readme)
        self.assertTrue(readme.startswith("# Marketplace Guard\n\nInstall:\n\n[![") and readme.endswith("\n\nMore.\n"))
        self.assertEqual(self.read(self.dev, "README.md"), README)

    def test_the_gate_readme_gets_the_app_and_the_marketplace_buttons(self):
        self.release()
        gate = self.read(self.public_clone(self.public_gate), "README.md")
        self.assertNotIn("<!-- publish:", gate)
        self.assertIn("supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fexample-user%2F"
                      "marketplace-guard)", gate)
        self.assertIn("https://my.home-assistant.io/badges/marketplace_repository.svg", gate)
        self.assertIn("https://my.home-assistant.io/redirect/marketplace_repository/?owner=example-user&repository="
                      "marketplace-guard-gate&category=integration)", gate)
        self.assertIn("Repository URL: `https://github.com/example-user/marketplace-guard-gate`", gate)
        self.assertEqual(self.read(self.public_clone(), "gate_repository/README.md"), gate)  # the same in both
        self.assertEqual(self.read(self.dev, "gate_repository/README.md"), GATE_README)

    def test_next_release_is_one_more_commit_with_its_changelog(self):
        self.release()
        self.bump("1.1.0", "# Changelog\n\n## 1.1.0\n- Second.\n\n## 1.0.0\n- First.\n")
        new, state = self.release(datetime.date(2026, 12, 1))
        self.assertEqual(state, "ready")
        pub = self.public_clone()
        self.assertEqual(run("rev-list", "--count", "HEAD", cwd=pub).strip(), "2")
        body = run("log", "-1", "--format=%B", cwd=pub)
        self.assertTrue(body.startswith("Marketplace Guard 1.1.0\n\n- Second."))
        self.assertEqual(sorted(run("tag", "--list", cwd=pub).split()), ["v1.0.0", "v1.1.0"])
        gate_body = run("log", "-1", "--format=%B", cwd=self.public_clone(self.public_gate))
        self.assertTrue(gate_body.startswith("Marketplace Guard Gate 1.1.0\n\nReleased with the Marketplace Guard app "
                                             f"1.1.0 ({URLS['app']}).\n\n- Second."))

    def test_a_release_that_skips_versions_names_them_all(self):
        self.release()
        self.bump("1.2.0", "# Changelog\n\n## 1.2.0\n- Third.\n\n## 1.1.0\n- Second.\n\n## 1.0.0\n- First.\n")
        self.release(datetime.date(2026, 12, 1))
        body = run("log", "-1", "--format=%B", cwd=self.public_clone())
        self.assertIn("## 1.2.0\n- Third.\n\n## 1.1.0\n- Second.", body)
        self.assertNotIn("First.", body)


class TestMain(Sandbox):
    """The whole run, against local public repositories (no check run, no gh)."""

    def tags(self, public):
        return run("tag", "--list", cwd=public).split()

    def test_one_run_publishes_both_repositories_from_the_same_commit(self):
        self.assertEqual(self.main("--dry-run"), 0)
        self.assertEqual(self.tags(self.public) + self.tags(self.public_gate), [])  # a dry run pushes nothing
        self.assertEqual(self.main(), 0)
        self.assertEqual(self.tags(self.public), ["v1.0.0"])
        self.assertEqual(self.tags(self.public_gate), ["v1.0.0"])

    def test_a_run_that_stopped_halfway_can_be_repeated(self):
        self.main()
        self.bump("1.1.0", "# Changelog\n\n## 1.1.0\n- Second.\n\n## 1.0.0\n- First.\n")
        sha = run("rev-parse", "HEAD", cwd=self.dev).strip()
        # the app was published, then the run stopped before the gate's push
        work = tempfile.mkdtemp(dir=self.tmp.name)
        tree = os.path.join(work, "tree")
        os.makedirs(tree)
        publish.export_tree(sha, tree)
        publish.fill_install(tree, publish.fill_public_fields(tree, *ACCOUNT))
        path, state = publish.prepare_public(self.public, work, "1.1.0")
        publish.commit_release(path, tree, "1.1.0", "- Second.", False, publish.neutral_date(), ACCOUNT)
        run("push", "--quiet", "origin", "HEAD:refs/heads/main", "refs/tags/v1.1.0", cwd=path)
        self.assertEqual(self.main(), 0)
        self.assertEqual(sorted(self.tags(self.public)), ["v1.0.0", "v1.1.0"])
        self.assertEqual(sorted(self.tags(self.public_gate)), ["v1.0.0", "v1.1.0"])
        self.assertEqual(run("rev-list", "--count", "HEAD", cwd=self.public).strip(), "2")  # the app left as it is
        self.assertEqual(self.main(), 1)  # both have it now: refused


if __name__ == "__main__":
    unittest.main()
