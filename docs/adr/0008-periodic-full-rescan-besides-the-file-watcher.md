---
status: accepted
date: 2026-06-08
decision-makers: maintainer
---

# Periodic full rescan besides the file watcher

Backfilled on 2026-11-02, decided on 2026-06-08 (version 1.3.0). Source: the maintainer's review list of 2026-06-08
(item 4, "implement all").

## Context and Problem Statement

Quarantine on write ([ADR-0001](0001-quarantine-on-write-and-a-repository-pre-check-instead-of-patching-hacs.md))
depends on file system events. An event can be missed, for example with atomic moves or while the add-on restarts.
A missed event lets a component through until something else changes it.

## Decision Drivers

* A missed event must not leave a component unscanned for long.
* Unchanged components should not be scanned again and again.

## Considered Options

* Rely on the watcher alone.
* Rescan all components on a timer, skipping those whose content hash is unchanged.

## Decision Outcome

Chosen option: a periodic rescan every `rescan_interval_minutes` (default 360; 0 turns it off) (the maintainer,
2026-06-08).

### Consequences

* Good, because a missed event is caught within the interval.
* Bad, because within the interval a missed component can still be loaded by a Home Assistant restart.

### Confirmation

The daemon loop in `guard.py` runs the rescan when the interval has passed.
