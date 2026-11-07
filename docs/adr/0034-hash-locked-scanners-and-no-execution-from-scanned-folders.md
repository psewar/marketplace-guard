---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Hash-locked scanners and no execution from scanned folders

Supersedes [ADR-0010](0010-pinned-scanner-versions-and-an-apparmor-profile.md).

## Context and Problem Statement

ADR-0010 pinned `bandit`, `pip-audit` and `watchdog` in the `Dockerfile` and added an AppArmor profile. The add-on is
built on each installation from its `Dockerfile`, so every build resolved the packages these three depend on anew —
about thirty, among them `requests`, `urllib3`, `rich`, `PyYAML` and `msgpack` — and took whatever PyPI served for them,
without any check of their content. The packages were installed into the system Python
(`PIP_BREAK_SYSTEM_PACKAGES=1`), and `git` was installed without being used. The AppArmor profile allowed all file
access, including starting programs from the folders HACS Guard scans and writes.

## Decision Drivers

* A security add-on should not take unreviewed code into its own image at build time.
* A dependency update is a deliberate change that shows in a diff, the transitive ones included.
* A scanned component or a downloaded repository is data; it must never become a running program
  ([ADR-0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md)).

## Considered Options

* Keep pins of the three direct packages.
* Pin every package with its hashes in `requirements.txt` (generated from `requirements.in` with
  `uv pip compile --universal --generate-hashes`), install with `pip --require-hashes` into a virtual environment, drop
  `git`; and deny execution from the scanned and written folders in the AppArmor profile.
* Publish prebuilt images instead of building on each installation.

## Decision Outcome

Chosen option: the second option.

* `marketplace_guard/requirements.in` names the three direct packages; `marketplace_guard/requirements.txt` pins all 34 packages with
  the hashes of all their distributions, for Python 3.11 and later on every platform, so the same file serves amd64,
  aarch64 and armv7 (Python 3.11 on bookworm).
* The `Dockerfile` creates `/opt/venv`, installs with `--require-hashes` and puts `/opt/venv/bin` first on `PATH`;
  `python3-pip` and `git` are no longer installed.
* The AppArmor profile allows running the scanners from `/opt/venv/bin` and denies execution from `/homeassistant`,
  `/config`, `/data`, `/share` and `/tmp`.

The third option is the better long-term one (the build happens once, in the open), but it needs a container registry
and a release pipeline that the repository does not have yet; it does not exclude the second.

### Consequences

* Good, because a package that changed on PyPI fails the build instead of entering the image.
* Good, because a dependency update, transitive ones included, shows in the diff of `requirements.txt`.
* Good, because nothing HACS Guard reads or writes can be started as a program, even if a parser bug were exploited.
* Bad, because `requirements.txt` has to be regenerated when a direct package is raised (`AGENTS.md` says how).
* Bad, because the profile still allows reading and writing all files the add-on maps; it confines execution and
  escalation, not data access.

### Confirmation

The amd64 image was built with `--require-hashes`, started under its init with `bandit` 1.9.4 and `pip-audit` 2.10.1
from the virtual environment, and ran the unit tests and the bandit check. The aarch64 and armv7 images were not built
(no emulation was available); instead `pip download --require-hashes --no-deps --platform …` fetched every package of
`requirements.txt` with a matching hash for aarch64 (Python 3.13, all 34 as wheels) and armv7 (Python 3.11: msgpack,
PyYAML and watchdog as source packages, built in the image as before; pip does not hash-check the build tools of a
source package). `apparmor_parser -Q -K` (AppArmor 4.1.0) parses the profile. Whether the Supervisor's kernel enforces
the deny rules was not tested here.

Accepted by the maintainer on 2026-11-06; implemented in pull request #29.
