---
status: accepted
date: 2026-11-05
decision-makers: maintainer
---

# The base image follows the newest stable Debian release

## Context and Problem Statement

The add-on image is built from the Home Assistant base images `ghcr.io/home-assistant/{arch}-base-debian`, pinned by
tag in `marketplace_guard/build.yaml` ([ADR-0010](0010-pinned-scanner-versions-and-an-apparmor-profile.md)). Up to version
1.4.2 they were Debian 12 (bookworm) images. The base images are published for Debian 12 and Debian 13 (trixie) from
the same release. On bookworm the add-on runs Debian's Python 3.11.2, which lacks `tarfile.data_filter`: the `data`
filter for archive extraction that version 1.3.1 added (ADR-0007) is skipped there. That was found by building the
image and reading the runtime facts that version 1.4.1 logs.

## Decision Drivers

* The newest stable versions, with lags reported rather than silently kept.
* Hardening that the code has should also be active in the image.
* Only what was built and tested is changed.

## Considered Options

* Stay on bookworm and raise the tag to the newest bookworm release.
* Move to trixie, the newest stable Debian release of the base images.

## Decision Outcome

Chosen option: the second option, for the architectures the base images are still built for (amd64, aarch64):
`trixie-2026.10.3`, with Debian's Python 3.13. Later raises take the newest release tag of the newest stable Debian
release the base images offer. armv7 is no longer built by Home Assistant; its tag is left as it is (see
[ADR-0020](0020-drop-armv7.md)).

### Consequences

* Good, because Python 3.13 has the `data` extraction filter, so pre-checks use it.
* Good, because the base gets Debian's security updates for longer.
* Bad, because armv7 stays on bookworm and Python 3.11.2 while it is still listed, so the platforms differ.
* Bad, because only amd64 was built and tested; aarch64 uses the same release and Dockerfile but was not built.

### Confirmation

`marketplace_guard/build.yaml` names the tags. The amd64 image was built with `trixie-2026.10.3`; inside it the unit tests
passed, the runtime facts showed Python 3.13.5 with `tar_data_filter` true, bandit scanned a sample component and a
watchdog observer reported file events.

Accepted by the maintainer on 2026-11-07; implemented in pull request #9.
