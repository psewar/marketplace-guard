---
status: rejected
date: 2026-11-05
decision-makers: maintainer
---

# Drop armv7

## Context and Problem Statement

`marketplace_guard/config.yaml` and `marketplace_guard/build.yaml` list amd64, aarch64 and armv7. Home Assistant deprecated its
32-bit architectures, and its base images stopped building them: the release notes of `home-assistant/docker-base`
2025.11.2 say "Drop deprecated architectures", and the newest armv7 tags are `bookworm-2025.11.1` and
`trixie-2025.11.1`, while amd64 and aarch64 continue (2026.10.3 at the time of writing). An armv7 build of the add-on
therefore gets no base image updates, and it cannot be tested without an armv7 machine or emulation.

## Decision Drivers

* Every listed platform should get security updates and be buildable from a maintained base.
* An existing installation should not lose its add-on without notice.

## Considered Options

* Keep armv7 on its last base image.
* Remove armv7 from `arch` in `config.yaml` and from `build.yaml`, with a changelog entry.

## Decision Outcome

Rejected: the second option was proposed, in a release of its own; armv7 is kept on its last base image
`bookworm-2025.11.1`, its newest bookworm image (the first option).

### Consequences

* Good, because every listed platform is maintained and its base receives updates.
* Bad, because an armv7 installation gets no further add-on updates; the installed version keeps running.

### Confirmation

`arch` in `marketplace_guard/config.yaml` and `build_from` in `marketplace_guard/build.yaml` no longer list armv7.

Rejected by the maintainer on 2026-11-07: since 1.7.1 the armv7 image builds again (`msgpack` as pure Python,
pull request #32) and passes the unit tests under emulation, so dropping it would cost armv7 installations their
updates for no gain. armv7 stays on `bookworm-2025.11.1`. If its build breaks for good, a new ADR decides again.
