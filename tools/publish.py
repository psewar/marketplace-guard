#!/usr/bin/env python3
"""Publish a release of Marketplace Guard to its public repositories, one commit each (ADR-0013, ADR-0045).

    python3 tools/publish.py [--ref main] [--owner <account>] [--dry-run] [--create] [--release]
                             [--public <git url>] [--public-gate <git url>]

Development stays in this repository; the public repositories only ever receive releases, made from the tree of --ref
(default main) - never its history:
- github.com/<account>/marketplace-guard, the app repository: the whole tree;
- github.com/<account>/marketplace-guard-gate, the gate repository for the Marketplace catalog (ADR-0045): the gate
  integration in custom_components/marketplace_guard_gate/, the files in gate_repository/ (README.md, hacs.json, the
  validation workflow) and LICENSE. The Marketplace refuses repositories with apps, so the gate has its own.
Each release is one commit per repository with the publishing account as author and a neutral date (the day, 00:00
UTC), tagged v<version>. The first one starts the repository.

The publishing account is the one gh is logged in to (or --owner). It is written into the published copies only:
`url` and `maintainer` in repository.yaml, `url` in marketplace_guard/config.yaml (the link on the app's page),
`documentation`, `issue_tracker` and `codeowners` in the gate's manifest.json, the app's install button in place of the
line `<!-- publish: install -->` in README.md and gate_repository/README.md (ADR-0038), and the gate's Marketplace
button in place of the line `<!-- publish: marketplace -->` in gate_repository/README.md. So this repository stays
site-neutral (ADR-0011).

The tool checks both repositories before it creates or pushes anything, and refuses with the state and the next step:
- the checkout is clean, HEAD is --ref, and `python3 tools/check.py --all` passes on it;
- the version in marketplace_guard/config.yaml is a release number, and the gate's manifest carries it;
- each public repository is empty, or its newest commit was made by this tool (a commit made by hand there would be
  overwritten by the next release, so it has to be brought into this repository first);
- each public repository exists, or --create is given to create it (public, with a description; the gate repository
  also with the topics the catalog asks for).
A repository that already has this version is left as it is, so a run that stopped halfway can be repeated; when both
have it, the tool refuses. Then it commits, tags v<version> and pushes; --release adds the GitHub release where it is
missing. Commit message and release notes carry the changelog sections of every version since the newest published
one, so a release that skips versions names them all. --dry-run stops before anything is created or pushed. Exit 0:
published (or dry run complete); 1: refused; 2: a step failed.
"""
import argparse
import collections
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON = "marketplace_guard"
REPO_NAME = "marketplace-guard"
GATE_DOMAIN = "marketplace_guard_gate"
GATE_REPO_NAME = "marketplace-guard-gate"
GATE_SOURCE = f"{ADDON}/gate/{GATE_DOMAIN}"  # the gate integration in the development tree
GATE_MANIFEST = f"{GATE_SOURCE}/manifest.json"
GATE_FILES = "gate_repository"  # what the gate repository carries besides the integration and the license
GATE_REQUIRED = ("README.md", "hacs.json")
GATE_README = f"{GATE_FILES}/README.md"
TRAILER = "Published-by: tools/publish.py"
# The install buttons need the public repositories' URLs, which only the published copies may contain (ADR-0038).
INSTALL_MARKER = "<!-- publish: install -->"
MARKETPLACE_MARKER = "<!-- publish: marketplace -->"
# marker line -> the files that must carry it; it may be left nowhere else
MARKER_FILES = {INSTALL_MARKER: ("README.md", GATE_README), MARKETPLACE_MARKER: (GATE_README,)}
MY_HA = "https://my.home-assistant.io"

Target = collections.namedtuple("Target", "key name title description topics")
TARGETS = (
    Target("app", REPO_NAME, "Marketplace Guard",
           "Home Assistant add-on: security scanning and quarantine for custom components from the Marketplace, HACS "
           "or by hand", ()),
    Target("gate", GATE_REPO_NAME, "Marketplace Guard Gate",
           "Home Assistant integration: lets the Marketplace Guard app check what the Marketplace installs before it "
           "can load", ("hacs", "hacs-integration", "home-assistant", "home-assistant-integration", "marketplace",
                        "security")),
)


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


def version_key(version):
    return tuple(int(p) for p in version.split("."))


def changelog_since(text, version, published=None):
    """The release notes: the changelog sections of the versions after the newest published one up to this one, newest
    first, each under its heading when there is more than one; this version's section alone for the first publication.
    None when there is none."""
    sections = [(m.group(1), m.group(2).strip())
                for m in re.finditer(r"^## (\d+\.\d+\.\d+)\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)]
    top, low = version_key(version), version_key(published) if published else None
    picked = [(v, body) for v, body in sections
              if (v == version if low is None else low < version_key(v) <= top)]
    picked.sort(key=lambda s: version_key(s[0]), reverse=True)
    if len(picked) <= 1:
        return picked[0][1] if picked else None
    return "\n\n".join(f"## {v}\n{body}" for v, body in picked)


def newest_published(path, below=None):
    """The newest version tagged v<x.y.z> in a public repository's clone (below `below` when given), or None."""
    tags = [t[1:] for t in git("tag", "--list", "v*", cwd=path).stdout.split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    if below:
        tags = [t for t in tags if version_key(t) < version_key(below)]
    return max(tags, key=version_key) if tags else None


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


def public_urls(account):
    """{target key: URL of its public repository}."""
    return {t.key: f"https://github.com/{account}/{t.name}" for t in TARGETS}


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


def _path(tree, rel):
    return os.path.join(tree, *rel.split("/"))


def read_json_object(tree, rel):
    """The JSON object in tree/rel; refuses when the file is missing or holds no JSON object."""
    path = _path(tree, rel)
    if not os.path.isfile(path):
        raise Refused(f"{rel} is missing.")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:  # parsing is the only way to know whether the file is valid JSON
        data = json.loads(text)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise Refused(f"{rel} does not hold a JSON object.")
    return data


def fill_gate_manifest(tree, account, gate_url):
    """Write the publishing account into the gate's manifest.json: documentation, issue_tracker and codeowners, which
    the Marketplace catalog asks for (ADR-0045). Refuses when one of the keys is not there to fill in."""
    manifest = read_json_object(tree, GATE_MANIFEST)
    values = {"codeowners": [f"@{account}"], "documentation": gate_url, "issue_tracker": f"{gate_url}/issues"}
    missing = [k for k in values if k not in manifest]
    if missing:
        raise Refused(f"{GATE_MANIFEST} has no {', '.join(missing)} to fill in. Next step: add the key(s) with the "
                      "placeholder OWNER (ADR-0045).")
    manifest.update(values)
    with open(_path(tree, GATE_MANIFEST), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def fill_public_fields(tree, account, email):
    """Write the publishing account into the published copy: url and maintainer in repository.yaml, url in the add-on's
    config.yaml (after its description), and the gate's manifest.json. Refuses when a file lacks the line or key it
    needs. Returns {target key: URL of its public repository}."""
    urls = public_urls(account)
    url = urls["app"]
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
    fill_gate_manifest(tree, account, urls["gate"])
    return urls


def install_block(url):
    """What the install marker becomes in the published copy: the My Home Assistant button that opens the dialog for
    adding an app repository with this URL filled in, and the URL itself for adding it by hand."""
    redirect = f"{MY_HA}/redirect/supervisor_add_addon_repository/?repository_url={urllib.parse.quote(url, safe='')}"
    return (f"[![Add the repository to your Home Assistant]({MY_HA}/badges/supervisor_add_addon_repository.svg)]"
            f"({redirect})\n\nRepository URL: `{url}`")


def marketplace_block(url):
    """What the Marketplace marker becomes: the My Home Assistant button that opens the gate repository in the
    Marketplace (which offers to add it as a custom repository while the catalog does not list it), and its URL."""
    owner, repository = url.rstrip("/").split("/")[-2:]
    query = urllib.parse.urlencode({"owner": owner, "repository": repository, "category": "integration"})
    return (f"[![Open the gate in the Marketplace of your Home Assistant]({MY_HA}/badges/marketplace_repository.svg)]"
            f"({MY_HA}/redirect/marketplace_repository/?{query})\n\nRepository URL: `{url}`")


def fill_install(tree, urls):
    """Replace each marker line in its files (MARKER_FILES) by its button: the app's install button, the gate's
    Marketplace button. Refuses when one of those files lacks its marker line, or when a marker line is left anywhere
    else in the tree (it would be published unfilled). Only a line that is the marker and nothing else counts, so code
    and documents may name it."""
    blocks = {INSTALL_MARKER: install_block(urls["app"]), MARKETPLACE_MARKER: marketplace_block(urls["gate"])}
    for marker, files in MARKER_FILES.items():
        for rel in files:
            path = _path(tree, rel)
            if not os.path.isfile(path):
                raise Refused(f"{rel} is missing; it carries the line `{marker}`.")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if not re.search(rf"^{re.escape(marker)}$", text, re.M):
                raise Refused(f"{rel} has no line `{marker}` for its button.")
            text = re.sub(rf"^{re.escape(marker)}$", lambda _: blocks[marker], text, flags=re.M)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    lines = {m: re.compile(rb"^" + re.escape(m.encode()) + rb"\r?$", re.M) for m in MARKER_FILES}
    for d, _, names in os.walk(tree):
        for name in names:
            path = os.path.join(d, name)
            with open(path, "rb") as f:
                content = f.read()
            for marker, line in lines.items():
                if line.search(content):
                    raise Refused(f"{os.path.relpath(path, tree)} still holds `{marker}`, which only "
                                  f"{', '.join(MARKER_FILES[marker])} may carry. Next step: remove it there, or add "
                                  "the file to MARKER_FILES.")


def build_gate_tree(tree, dest, version):
    """The gate repository's tree (ADR-0045), made from the filled app tree: the files in gate_repository/ at its root,
    LICENSE, and the gate integration in custom_components/<domain>/. Refuses when a part is missing, or when the gate
    does not carry the release's version (the catalog takes the release tag as the integration's version)."""
    parts = [GATE_SOURCE, "LICENSE"] + [f"{GATE_FILES}/{n}" for n in GATE_REQUIRED]
    missing = [p for p in parts if not os.path.exists(_path(tree, p))]
    if missing:
        raise Refused(f"the gate repository is made from {', '.join(missing)}, which the tree lacks.")
    manifest_version = read_json_object(tree, GATE_MANIFEST).get("version")
    if manifest_version != version:
        raise Refused(f"{GATE_MANIFEST} has version {manifest_version!r}, {ADDON}/config.yaml {version!r}. Next "
                      "step: set both (tools/check.py checks it).")
    shutil.copytree(_path(tree, GATE_FILES), dest)
    shutil.copy2(_path(tree, "LICENSE"), os.path.join(dest, "LICENSE"))
    shutil.copytree(_path(tree, GATE_SOURCE), os.path.join(dest, "custom_components", GATE_DOMAIN),
                    ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def prepare_public(public_url, workdir, version, done_ok=False):
    """Clone a public repository and check it: (path, state) with state "empty" (this release starts it), "ready", or
    "done" (it has this version already; only with done_ok, which repeats a run that stopped halfway). Refuses when the
    release exists without done_ok, or when the newest commit there was not made by this tool."""
    path = os.path.join(workdir, "public")
    git("clone", "--quiet", public_url, path, cwd=workdir)
    if git("rev-parse", "--verify", "-q", "HEAD", cwd=path, check=False).returncode != 0:
        return path, "empty"
    last = git("log", "-1", "--format=%H%n%B", cwd=path).stdout
    if TRAILER not in last:
        raise Refused(f"the newest public commit ({last[:7]}) was not made by tools/publish.py; the next release would "
                      "overwrite it. Next step: bring that change into the development repository (or revert it "
                      "publicly), then run again.")
    if git("tag", "--list", f"v{version}", cwd=path).stdout.strip():
        if done_ok:
            return path, "done"
        raise Refused(f"v{version} is already published. Next step: raise the version in {ADDON}/config.yaml (with a "
                      "changelog entry), merge, then run again.")
    return path, "ready"


def commit_release(path, tree_src, version, changelog, start, date, author, title="Marketplace Guard"):
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
        body = (f"The public repository starts here: the tree of {title} {version} from the development "
                "repository, without its history (ADR-0013).")
    else:
        body = changelog or f"Release {version}."
    git("-c", "commit.gpgsign=false", "commit", "--quiet", "-F", "-", cwd=path, env=env,
        stdin=f"{title} {version}\n\n{body}\n\n{TRAILER}\n")
    git("-c", "tag.gpgsign=false", "tag", "-a", f"v{version}", "-m", f"{title} {version}", cwd=path, env=env)
    return git("rev-parse", "HEAD", cwd=path).stdout.strip()


def release_notes(target, changelog, version, urls):
    """The commit message body and release notes of one repository: the app's changelog; for the gate, which is
    released with the app, a line that says so first."""
    notes = changelog or f"{target.title} {version}."
    if target.key == "gate":
        notes = f"Released with the Marketplace Guard app {version} ({urls['app']}).\n\n{notes}"
    return notes


def github_repo_exists(slug):
    """Whether gh sees the GitHub repository (a fact; gh answers a missing repository with a non-zero exit)."""
    return subprocess.run(["gh", "repo", "view", slug, "--json", "name"], capture_output=True, text=True).returncode == 0


def github_release_exists(slug, tag):
    """Whether the GitHub release exists (a fact; gh answers a missing release with a non-zero exit)."""
    return subprocess.run(["gh", "release", "view", tag, "--repo", slug, "--json", "tagName"], capture_output=True,
                          text=True).returncode == 0


def create_github_repo(slug, description, topics=()):
    made = subprocess.run(["gh", "repo", "create", slug, "--public", "--description", description],
                          capture_output=True, text=True)
    if made.returncode != 0:
        raise RuntimeError(f"gh repo create {slug}: {made.stderr.strip()}")
    if topics:
        edit = subprocess.run(["gh", "repo", "edit", slug, *[a for t in topics for a in ("--add-topic", t)]],
                              capture_output=True, text=True)
        if edit.returncode != 0:
            raise RuntimeError(f"gh repo edit {slug} --add-topic: {edit.stderr.strip()}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="main")
    ap.add_argument("--owner", help="publishing account (default: the account gh is logged in to)")
    ap.add_argument("--public", help="git URL of the app repository (default: github.com/<account>/marketplace-guard)")
    ap.add_argument("--public-gate",
                    help="git URL of the gate repository (default: github.com/<account>/marketplace-guard-gate)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args(argv)
    try:
        sha, version = check_source(args.ref, run_checks=True)
        account, email = publishing_account(args.owner)
        given = {"app": args.public, "gate": args.public_gate}
        with tempfile.TemporaryDirectory() as work:
            tree = os.path.join(work, "tree")
            os.makedirs(tree)
            export_tree(sha, tree)
            urls = fill_public_fields(tree, account, email)
            fill_install(tree, urls)
            trees = {"app": tree, "gate": build_gate_tree(tree, os.path.join(work, "gate-tree"), version)}
            changelog = read_at(sha, f"{ADDON}/CHANGELOG.md")
            plans = []
            for t in TARGETS:  # every check, for both repositories, before anything is created or pushed
                slug = f"{account}/{t.name}"
                public, missing = given[t.key], False
                if not public:
                    public, missing = f"https://github.com/{slug}.git", not github_repo_exists(slug)
                if missing and not (args.create or args.dry_run):
                    raise Refused(f"github.com/{slug} does not exist (or gh cannot see it). Next step: check the name "
                                  "with --dry-run, then run again with --create to create it as a public repository.")
                source = public
                if missing:  # the first commit is made against an empty stand-in; the repository is created last
                    source = os.path.join(work, f"{t.key}-stand-in.git")
                    git("init", "--quiet", "--bare", source, cwd=work)
                workdir = os.path.join(work, t.key)
                os.makedirs(workdir)
                path, state = prepare_public(source, workdir, version, done_ok=True)
                notes = release_notes(t, changelog_since(changelog, version, newest_published(path, below=version)),
                                      version, urls)
                plans.append((t, slug, public, missing, path, state, notes))
            if all(p[5] == "done" for p in plans):
                raise Refused(f"v{version} is already published in both repositories. Next step: raise the version in "
                              f"{ADDON}/config.yaml (with a changelog entry), merge, then run again.")
            for t, slug, public, missing, path, state, notes in plans:
                if state == "done":
                    print(f"{t.title} {version} is already in {slug}: left as it is")
                    continue
                new = commit_release(path, trees[t.key], version, notes, state == "empty", neutral_date(),
                                     (account, email), t.title)
                files = git("ls-tree", "-r", "--name-only", "HEAD", cwd=path).stdout.split()
                print(f"{'start commit' if state == 'empty' else 'release commit'} {new[:7]} for {t.title} {version} "
                      f"(from {sha[:7]}): {len(files)} files, tag v{version}, {urls[t.key]}"
                      + (" (repository to be created)" if missing else ""))
            if args.dry_run:
                print("dry run: nothing created or pushed")
                return 0
            for t, slug, public, missing, path, state, notes in plans:
                if state != "done":
                    if missing:
                        create_github_repo(slug, t.description, t.topics)
                        git("remote", "set-url", "origin", public, cwd=path)
                        print(f"created {urls[t.key]}")
                    git("push", "--quiet", "origin", "HEAD:refs/heads/main", f"refs/tags/v{version}", cwd=path)
                    print(f"pushed to {public}")
                if args.release and not github_release_exists(slug, f"v{version}"):
                    r = subprocess.run(["gh", "release", "create", f"v{version}", "--repo", slug, "--title",
                                        f"{t.title} {version}", "--notes", notes], capture_output=True, text=True)
                    if r.returncode != 0:
                        raise RuntimeError(f"gh release create ({slug}): {r.stderr.strip()}")
                    print(f"release v{version} created in {slug}")
        return 0
    except Refused as e:
        print(f"publish: refused: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:  # a git or gh step failed after the checks passed: report which one
        print(f"publish: failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
