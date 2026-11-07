#!/usr/bin/env python3
"""Publish a release of Marketplace Guard to the public repository as one commit (ADR-0013).

    python3 tools/publish.py [--ref main] [--owner <account>] [--dry-run] [--create] [--release] [--public <git url>]

Development stays in this repository; the public repository github.com/<account>/marketplace-guard only ever receives
releases. Each release is one commit made from the tree of --ref (default main) - never its history - with the
publishing account as author and a neutral date (the day, 00:00 UTC). The first one starts the public repository.

The publishing account is the one gh is logged in to (or --owner). It is written into the published copy only:
`url` and `maintainer` in repository.yaml and `url` in marketplace_guard/config.yaml, so that this repository stays
site-neutral (ADR-0011).

The tool checks before it acts and refuses with the state and the next step:
- the checkout is clean, HEAD is --ref, and `python3 tools/check.py --all` passes on it;
- the version in marketplace_guard/config.yaml is a release number and not yet tagged in the public repository;
- the public repository is empty, or its newest commit was made by this tool (a commit made by hand there would be
  overwritten by the next release, so it has to be brought into this repository first);
- the public repository exists, or --create is given to create it (public, with gh).
Then it commits, tags v<version> and pushes; --release adds a GitHub release with the version's changelog section.
--dry-run stops before anything is created or pushed. Exit 0: published (or dry run complete); 1: refused; 2: a step
failed.
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = "marketplace_guard"
REPO_NAME = "marketplace-guard"
TRAILER = "Published-by: tools/publish.py"


class Refused(Exception):
    """A precondition does not hold: the message says the state and the next step."""


def git(*args, cwd=None, env=None, check=True, stdin=None):
    r = subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, env=env, input=stdin)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r


def read_at(ref, path, cwd=None):
    return git("show", f"{ref}:{path}", cwd=cwd).stdout


def yaml_value(text, key):
    """The value of a top-level `key: "value"` line (the files are written by hand; no YAML library needed)."""
    m = re.search(rf"^{re.escape(key)}:\s*\"?([^\"\n]*)\"?\s*$", text, re.M)
    return m.group(1).strip() if m else None


def changelog_section(text, version):
    """The lines under '## <version>' up to the next '## ' heading, or None."""
    m = re.search(rf"^## {re.escape(version)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def neutral_date(today=None):
    """The publication day at 00:00 UTC: no time of day, no time zone of the publishing machine."""
    day = today or datetime.datetime.now(datetime.timezone.utc).date()
    return f"{day.isoformat()}T00:00:00+0000"


def publishing_account(owner=None):
    """(account, e-mail) of the publishing account: --owner, else the account gh is logged in to."""
    login = owner
    if not login:
        r = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True)
        login = r.stdout.strip() if r.returncode == 0 else ""
        if not login:
            raise Refused("no publishing account: gh is not logged in. Next step: gh auth login, or pass --owner.")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", login):
        raise Refused(f"{login!r} is not a GitHub account name.")
    return login, f"{login}@users.noreply.github.com"


def check_source(ref, run_checks):
    """The commit to publish: a clean checkout at ref whose checks pass. Returns (sha, version)."""
    if git("status", "--porcelain").stdout.strip():
        raise Refused("the checkout has uncommitted or untracked changes. Next step: commit or remove them.")
    sha = git("rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()
    head = git("rev-parse", "HEAD").stdout.strip()
    if head != sha:
        raise Refused(f"HEAD ({head[:7]}) is not {ref} ({sha[:7]}). Next step: git switch {ref}, then run again.")
    version = yaml_value(read_at(sha, f"{ADDON}/config.yaml"), "version")
    if not version or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise Refused(f"no version like 1.2.3 in {ADDON}/config.yaml at {sha[:7]}.")
    if run_checks:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check.py"), "--all"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise Refused(f"tools/check.py --all did not pass (exit {r.returncode}). Next step: fix what it reports:\n"
                          f"{r.stdout[-1500:]}{r.stderr[-500:]}")
    return sha, version


def export_tree(sha, dest):
    """The files of the commit, without history, into dest."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = os.path.join(tmp, "tree.tar")
        git("archive", "--format=tar", "-o", archive, sha)
        with tarfile.open(archive) as tar:
            tar.extractall(dest, filter="data")


def fill_public_fields(tree, account, email):
    """Write the publishing account into the published copy: url and maintainer in repository.yaml, url in the add-on's
    config.yaml (after its description). Refuses when a file lacks the line it needs."""
    url = f"https://github.com/{account}/{REPO_NAME}"
    edits = ((os.path.join(tree, "repository.yaml"), (("url", url), ("maintainer", f"{account} <{email}>")), None),
             (os.path.join(tree, ADDON, "config.yaml"), (("url", url),), "description"))
    for path, fields, after in edits:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for key, value in fields:
            line = f'{key}: "{value}"'
            if re.search(rf"^{key}:.*$", text, re.M):
                text = re.sub(rf"^{key}:.*$", lambda _: line, text, count=1, flags=re.M)
            elif after and re.search(rf"^{after}:.*$", text, re.M):
                text = re.sub(rf"^({after}:.*)$", lambda m: f"{m.group(1)}\n{line}", text, count=1, flags=re.M)
            else:
                raise Refused(f"{os.path.relpath(path, tree)} has no `{key}:` line to fill in.")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return url


def prepare_public(public_url, workdir, version):
    """Clone the public repository and check it: (path, is_empty). Refuses when the release exists or the newest commit
    there was not made by this tool."""
    path = os.path.join(workdir, "public")
    git("clone", "--quiet", public_url, path, cwd=workdir)
    if git("rev-parse", "--verify", "-q", "HEAD", cwd=path, check=False).returncode != 0:
        return path, True
    if git("tag", "--list", f"v{version}", cwd=path).stdout.strip():
        raise Refused(f"v{version} is already published. Next step: raise the version in {ADDON}/config.yaml (with a "
                      "changelog entry), merge, then run again.")
    last = git("log", "-1", "--format=%H%n%B", cwd=path).stdout
    if TRAILER not in last:
        raise Refused(f"the newest public commit ({last[:7]}) was not made by tools/publish.py; the next release would "
                      "overwrite it. Next step: bring that change into the development repository (or revert it "
                      "publicly), then run again.")
    return path, False


def commit_release(path, tree_src, version, changelog, start, date, author):
    """Replace the public tree by tree_src and commit it with neutral metadata; tag v<version>. Returns the sha."""
    for name in os.listdir(path):
        if name != ".git":
            target = os.path.join(path, name)
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
    for name in os.listdir(tree_src):
        src = os.path.join(tree_src, name)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, os.path.join(path, name))
    env = dict(os.environ, GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1], GIT_COMMITTER_NAME=author[0],
               GIT_COMMITTER_EMAIL=author[1], GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    git("add", "--all", cwd=path, env=env)
    if start:
        body = (f"The public repository starts here: the tree of Marketplace Guard {version} from the development "
                "repository, without its history (ADR-0013).")
    else:
        body = changelog or f"Release {version}."
    git("-c", "commit.gpgsign=false", "commit", "--quiet", "-F", "-", cwd=path, env=env,
        stdin=f"Marketplace Guard {version}\n\n{body}\n\n{TRAILER}\n")
    git("-c", "tag.gpgsign=false", "tag", "-a", f"v{version}", "-m", f"Marketplace Guard {version}", cwd=path, env=env)
    return git("rev-parse", "HEAD", cwd=path).stdout.strip()


def github_repo_exists(slug):
    """Whether gh sees the GitHub repository (a fact; gh answers a missing repository with a non-zero exit)."""
    return subprocess.run(["gh", "repo", "view", slug, "--json", "name"], capture_output=True, text=True).returncode == 0


def create_github_repo(slug):
    made = subprocess.run(["gh", "repo", "create", slug, "--public", "--description",
                           "Home Assistant add-on: security scanning and quarantine for custom components from the "
                           "Marketplace, HACS or by hand"], capture_output=True, text=True)
    if made.returncode != 0:
        raise RuntimeError(f"gh repo create {slug}: {made.stderr.strip()}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="main")
    ap.add_argument("--owner", help="publishing account (default: the account gh is logged in to)")
    ap.add_argument("--public", help="git URL of the public repository (default: github.com/<account>/marketplace-guard)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args(argv)
    try:
        sha, version = check_source(args.ref, run_checks=True)
        account, email = publishing_account(args.owner)
        slug = f"{account}/{REPO_NAME}"
        with tempfile.TemporaryDirectory() as work:
            public, missing = args.public, False
            if not public:
                public, missing = f"https://github.com/{slug}.git", not github_repo_exists(slug)
            if missing and args.dry_run:  # show the start commit against an empty stand-in, create nothing
                public = os.path.join(work, "stand-in.git")
                git("init", "--quiet", "--bare", public, cwd=work)
            elif missing and not args.create:
                raise Refused(f"github.com/{slug} does not exist (or gh cannot see it). Next step: check the name with "
                              "--dry-run, then run again with --create to create it as a public repository.")
            elif missing:
                create_github_repo(slug)
            tree = os.path.join(work, "tree")
            os.makedirs(tree)
            export_tree(sha, tree)
            url = fill_public_fields(tree, account, email)
            path, empty = prepare_public(public, work, version)
            changelog = changelog_section(read_at(sha, f"{ADDON}/CHANGELOG.md"), version)
            new = commit_release(path, tree, version, changelog, empty, neutral_date(), (account, email))
            files = git("ls-tree", "-r", "--name-only", "HEAD", cwd=path).stdout.split()
            print(f"{'start commit' if empty else 'release commit'} {new[:7]} for Marketplace Guard {version} "
                  f"(from {sha[:7]}): {len(files)} files, tag v{version}, {url}")
            if args.dry_run:
                print("dry run: nothing created or pushed")
                return 0
            git("push", "--quiet", "origin", "HEAD:refs/heads/main", f"refs/tags/v{version}", cwd=path)
            print(f"pushed to {public}")
            if args.release:
                r = subprocess.run(["gh", "release", "create", f"v{version}", "--repo", slug, "--title",
                                    f"Marketplace Guard {version}", "--notes", changelog or f"Marketplace Guard {version}"],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    raise RuntimeError(f"gh release create: {r.stderr.strip()}")
                print(f"release v{version} created")
        return 0
    except Refused as e:
        print(f"publish: refused: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:  # a git or gh step failed after the checks passed: report which one
        print(f"publish: failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
