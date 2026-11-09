# Publishing Marketplace Guard as a Home Assistant add-on repository

This repository has the layout of an add-on repository: `repository.yaml` at the root and the add-on in
`marketplace_guard/`. Home Assistant builds the image on each installation from `marketplace_guard/Dockerfile`;
there is no prebuilt image to publish.

## 1. Publish a release

Development happens here; the public repository `github.com/<account>/marketplace-guard` only receives releases, one
commit each, made from the tree of `main` without its history
([ADR-0013](docs/adr/0013-publish-as-a-new-repository-with-one-start-commit.md)). After the release's pull request is
merged:

```bash
git switch main && git pull
python3 tools/publish.py --dry-run           # what would be published, nothing created or pushed
python3 tools/publish.py --release           # the first time: --create --release
```

`tools/publish.py` checks first and refuses with the next step otherwise: a clean checkout at `main`,
`python3 tools/check.py --all` passing (tests, ADR index, links, configuration, site-neutral with your own site term
list, [ADR-0011](docs/adr/0011-the-repository-is-site-neutral.md)), a version that is not yet published, and a public
repository whose newest commit it made itself. It writes the publishing account (the one `gh` is logged in to, or
`--owner`) into the published copy only: `url` and `maintainer` in `repository.yaml`, `url` in
`marketplace_guard/config.yaml` (the link on the app's page), and the install button with the repository URL in place
of the line `<!-- publish: install -->` in `README.md`
([ADR-0038](docs/adr/0038-the-published-readme-carries-a-one-click-install-button.md)). The commit has that account as
author and the day at 00:00 UTC as date; the tag is `v<version>`; `--release` adds a GitHub release. Commit message and
release notes carry the changelog sections of every version since the last publication. Never push to the public
repository by hand: the next release would refuse until the change is brought back here.

## 2. Install on any Home Assistant OS instance

The published `README.md` has a button that opens the dialog for adding the repository in your own Home Assistant. By
hand (add-ons are called *apps* since Home Assistant 2026.2):

1. Settings → Apps → **Install app** → ⋮ → **Repositories**.
2. Add `https://github.com/<account>/marketplace-guard` → the **Marketplace Guard** app appears.
3. Install → Start. The defaults work without changes.

## Notes
- **Multi-architecture:** `config.yaml`/`build.yaml` build for amd64, aarch64 and armv7, so the
  add-on works on Intel/AMD boxes and Raspberry Pi.
- **AppArmor:** `apparmor.txt` is applied automatically by the Supervisor. It allows file and network
  access (needed to scan `/config` and reach PyPI/GitHub) while confining mount/ptrace/raw
  capabilities. If the add-on ever fails to start right after an update, remove `apparmor.txt` and
  rebuild to rule it out.
- **Developer override:** `run.sh` prefers code from `code/` in the add-on's configuration folder
  (`addon_configs/<...>_marketplace_guard/code/` on the host, `/config/code/` inside the add-on) if present
  (handy for editing without a rebuild) and otherwise runs the code baked into the image. End users
  who install from the repository simply get the baked code; the override folder does not exist for
  them, so behaviour is identical. Before tagging a release you may delete the override folder on your
  own instance to confirm the baked image is current.
- **Pinned dependencies:** `bandit`, `pip-audit` and `watchdog` are named in `requirements.in`;
  `requirements.txt` pins them and everything they depend on with hashes, and the image installs it with
  `--require-hashes`. Bump them deliberately and regenerate `requirements.txt` (see `AGENTS.md`).
