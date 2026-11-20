# Publishing Marketplace Guard as a Home Assistant add-on repository

This repository has the layout of an add-on repository: `repository.yaml` at the root and the add-on in
`marketplace_guard/`. Home Assistant builds the image on each installation from `marketplace_guard/Dockerfile`;
there is no prebuilt image to publish.

## 1. Publish a release

Development happens here; the public repositories only receive releases, one commit each, made from the tree of `main`
without its history ([ADR-0013](docs/adr/0013-publish-as-a-new-repository-with-one-start-commit.md)):

* `github.com/<account>/marketplace-guard`, the app repository: the whole tree;
* `github.com/<account>/marketplace-guard-gate`, the gate repository for the Marketplace catalog, which refuses
  repositories with apps
  ([ADR-0045](docs/adr/0045-the-gate-is-published-as-its-own-repository-for-the-marketplace-catalog.md)): the gate in
  `custom_components/marketplace_guard_gate/`, the files in `gate_repository/` and `LICENSE`.

After the release's pull request is merged:

```bash
git switch main && git pull
python3 tools/publish.py --dry-run           # what would be published, nothing created or pushed
python3 tools/publish.py --release           # a repository that does not exist yet: --create --release
```

`tools/publish.py` checks both repositories before it creates or pushes anything, and refuses with the next step
otherwise: a clean checkout at `main`, `python3 tools/check.py --all` passing (tests, ADR index, links, configuration,
the gate repository's catalog rules, site-neutral with your own site term list,
[ADR-0011](docs/adr/0011-the-repository-is-site-neutral.md)), a version the gate carries too, and public repositories
whose newest commit it made itself. It writes the publishing account (the one `gh` is logged in to, or `--owner`) into
the published copies only: `url` and `maintainer` in `repository.yaml`, `url` in `marketplace_guard/config.yaml` (the
link on the app's page), `documentation`, `issue_tracker` and `codeowners` in the gate's `manifest.json`, the app's
install button in place of the line `<!-- publish: install -->` in `README.md` and `gate_repository/README.md`
([ADR-0038](docs/adr/0038-the-published-readme-carries-a-one-click-install-button.md)), and the gate's Marketplace
button in place of `<!-- publish: marketplace -->` in `gate_repository/README.md`. Each commit has that account as
author and the day at 00:00 UTC as date; the tag is `v<version>`; `--release` adds the GitHub releases. Commit messages
and release notes carry the changelog sections of every version since the last publication. `--create` creates a
missing repository, the gate repository with a description and the topics the catalog asks for. A repository that
already has the version is left as it is, so a run that stopped halfway can be repeated. Never push to a public
repository by hand: the next release would refuse until the change is brought back here.

## 2. Install on any Home Assistant OS instance

The published `README.md` has a button that opens the dialog for adding the repository in your own Home Assistant. By
hand (add-ons are called *apps* since Home Assistant 2026.2):

1. Settings → Apps → **Install app** → ⋮ → **Repositories**.
2. Add `https://github.com/<account>/marketplace-guard` → the **Marketplace Guard** app appears.
3. Install → Start. The defaults work without changes.

The optional gate comes from the Marketplace (Settings → Marketplace → **Marketplace Guard Gate**; the button in the
gate repository's README opens it there and, while the catalog does not list it, offers to add the repository first),
or from the app's option *Check Marketplace installs before they load*.

## 3. Submit the gate to the Marketplace catalog

The catalog is the repository `hacs/default`; the Marketplace refuses repositories with apps, so only the gate
repository is submitted (ADR-0045). The maintainer, as the owner of the repository, does this once, by hand; no tool
and no coding agent opens this pull request.

1. Publish a release with `--create --release` (above). In the gate repository, under **Actions**, the workflow
   *Validate* has to pass on the release's commit, both jobs: *HACS action* and *hassfest*. If a job fails, fix it here,
   raise the version, publish again; a release whose checks failed is not submitted.
2. Check the gate repository's page: a description and topics (set by `--create`), issues turned on, the license
   recognised as MIT, and the release `v<version>`.
3. Fork `hacs/default` with your personal account (not an organisation account, so that the catalog's team can edit
   the pull request), create a branch from `master`, and add `<account>/marketplace-guard-gate` to the file
   `integration`, in alphabetical order.
4. Open the pull request and fill in its template completely; tick an item only where it is true. Links: the release
   (`https://github.com/<account>/marketplace-guard-gate/releases/tag/v<version>`), the passing run of the HACS action
   and the passing run of hassfest from step 1. Do not request reviews.
5. The review takes months. A pull request set to draft has small problems: fix them, publish a new release, then mark
   it ready for review. Until it is merged, the Marketplace button in the gate's README adds the repository as a custom
   repository, so the gate can be installed from the Marketplace already.

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
