---
status: superseded by ADR-0033
date: 2026-06-07
decision-makers: maintainer
---

# Override code folder takes precedence over the built-in code

Superseded by [ADR-0033](0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md): the override folder moved
to the add-on's configuration folder, which Home Assistant integrations cannot write.

Backfilled on 2026-11-02, decided on 2026-06-07; kept on 2026-06-08. Sources: `marketplace_guard/run.sh`, `PUBLISHING.md`
("Developer override"), the maintainer's review list of 2026-06-08 (item 9).

## Context and Problem Statement

Changing the add-on's code normally means a new version and an image rebuild. While the scanner was being calibrated,
changes were frequent and had to be tried on a running instance.

## Decision Drivers

* Try a code change with an add-on restart instead of a rebuild.
* Users who install the add-on from a repository must get exactly the built-in code.

## Considered Options

* Built-in code only.
* `run.sh` prefers `guard.py` and `scanner.py` from `/homeassistant/hacs_guard/code/` when both exist, and runs the
  built-in code otherwise.

## Decision Outcome

Chosen option: the override folder (2026-06-07). The review of 2026-06-08 first proposed removing it before
publishing; `PUBLISHING.md` keeps it, because the folder does not exist on other installations, so their behaviour is
the same as without it.

### Consequences

* Good, because a calibration can be tried with one add-on restart.
* Bad, because the running code can differ from the image and from this repository without any version showing it.
  This happened: a notification change of 2026-07-03 ran only in the override folder, still as version 1.3.0, until it
  was brought into the repository on 2026-11-02.
* Bad, because a change to the override folder needs an add-on restart, not a Home Assistant restart; mixing the two
  up once let an old scanner quarantine a component again.

### Confirmation

`run.sh` logs which code it starts. `AGENTS.md` ("Code in the image and the override folder") says that a change is
done only when it is released and built into the image.
