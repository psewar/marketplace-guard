---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# One worker makes every scan and quarantine decision

## Context and Problem Statement

The daemon had two threads that scanned and changed the shared state: a start-up thread that waited for Home Assistant
and recorded the baseline, and the main loop that handled file-watcher events, pre-checks, rescans and AI retries. The
state dictionary was changed by both without a lock, so a save could fail with "dictionary changed size during
iteration" and an exception in the start-up thread ended the start-up scan halfway. The start-up thread also treated
every component it had not seen before as baseline, at every start, while
[ADR-0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md) and `DOCS.md` say "at the first start":
a component installed while the add-on was stopped became trusted. And the main loop did one thing at a time without
looking back at the watcher: a pre-check of several repositories, a full rescan or a series of AI retries delayed the
scan of a fresh install by minutes.

## Decision Drivers

* The quarantine decision about a fresh install comes before anything that can wait.
* On the first start, installed components are recorded as the baseline before anything is judged as new.
* After the first start, a component never seen before is new, as `DOCS.md` says.
* The state is changed from one place, so no lock discipline is needed to keep it consistent.

## Considered Options

* Keep both threads and put a lock around every access to the state.
* One worker in the main thread does everything; the file watcher only marks components as changed. Long tasks
  (start-up scan, rescan, pre-check, AI retries) hand over to the components whose writes have settled between their
  items.

## Decision Outcome

Chosen option: the second option.

* `Worker` in `guard.py` owns the state. The watcher thread calls `mark()` and `mark_request()`, which only record a
  time under a lock.
* Start: the worker asks Home Assistant once per pass whether it answers (`core_answers()`), for at most three minutes.
  On the first start (no component in the state) nothing else happens before the start-up scan has recorded the
  baseline; on any later start, components whose writes have settled are handled while waiting, and the start-up scan
  judges unknown components as new.
* `scan_all()`, `process_request_file()` and `retry_ai_reviews()` call `process_ready()` between their items.

The first option was not chosen because it keeps two places that decide about the same component at the same time; a
lock prevents a broken save but not two scans of one component or two quarantines of it.

### Consequences

* Good, because a fresh install waits at most for the item that is being handled, not for a whole rescan or pre-check.
* Good, because a component installed while the add-on was stopped is checked like any other new install.
* Good, because the order on the first start is fixed: baseline first, then everything else.
* Bad, because on the first start, changes noticed while waiting for Home Assistant are handled only after the
  baseline (at most three minutes plus the scan).
* Bad, because one very slow item (a large pre-check download) still holds up the worker for its own duration.

### Confirmation

`TestWorker` in `marketplace_guard/tests/test_marketplace_guard.py`: on the first start a change waits for the baseline and an
installed component stays trusted; after the first start an unknown component found at start-up is quarantined; a
fresh install is handled between the components of a rescan.

Accepted by the maintainer on 2026-11-06; implemented in pull request #22.
