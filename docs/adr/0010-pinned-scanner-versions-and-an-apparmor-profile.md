---
status: superseded by ADR-0034
date: 2026-06-08
decision-makers: maintainer
---

# Pinned scanner versions and an AppArmor profile

Superseded by [ADR-0034](0034-hash-locked-scanners-and-no-execution-from-scanned-folders.md): every package is pinned
with its hashes, and the profile denies execution from the scanned and written folders.

Backfilled on 2026-11-02, decided on 2026-06-08 (version 1.3.0). Sources: the maintainer's review list of 2026-06-08
(items 10 and 11, "implement all"), `PUBLISHING.md`.

## Context and Problem Statement

The add-on has read-write access to the whole configuration folder and reaches the network. Its scanner tools come from
PyPI. An unpinned install takes whatever version is current at build time, and an unconfined container may use every
primitive the Supervisor allows.

## Decision Drivers

* Reproducible builds; a new scanner version is a deliberate change.
* Confine what the add-on can do beyond reading files and using the network.

## Considered Options

* Unpinned `pip install`, no AppArmor profile.
* Pinned versions of `bandit`, `pip-audit` and `watchdog` in the `Dockerfile`, and an AppArmor profile.

## Decision Outcome

Chosen option: pinned versions and an AppArmor profile (the maintainer, 2026-06-08).

The profile allows file and network access, which scanning needs, and the executables of the init tree, shell and
Python. Mounting, `pivot_root`, tracing other profiles, raw capabilities and loading kernel modules stay denied.

### Consequences

* Good, because builds are reproducible and a scanner update shows up in a diff.
* Bad, because pinned versions do not update themselves; they have to be raised on purpose.
* Bad, because the profile still allows all file and network access, so it limits escalation, not data access.

### Confirmation

`marketplace_guard/Dockerfile` installs exact versions; `marketplace_guard/apparmor.txt` is applied by the Supervisor.
