---
status: accepted
date: 2026-06-07
decision-makers: maintainer
---

# Quarantine on write and a repository pre-check instead of patching HACS

Backfilled on 2026-11-02, decided on 2026-06-07. Sources: the maintainer's design conversation of 2026-06-07 (options
A, B and C below; the decision was "C with B"), `marketplace_guard/DOCS.md`.

## Context and Problem Statement

The goal was to scan a HACS repository for security problems before its code can do harm. HACS has no plugin or hook
API and no extension point before a download. Downloads come straight from GitHub over HTTPS, and HACS has no proxy
setting.

## Decision Drivers

* Stop a malicious component before Home Assistant runs it.
* Survive HACS updates without maintaining a fork of HACS.
* Cover components installed by hand as well as through HACS.

## Considered Options

* A: Fork or monkey-patch HACS so that its download function calls the scanner first.
* B: An out-of-band pre-check: give it a repository URL, it downloads the repository, scans it and reports, without
  installing anything.
* C: Quarantine on write: watch `custom_components` and `www/community`, scan what is written there, and move a risky
  component aside before the next Home Assistant restart loads it.
* A scanning proxy between HACS and GitHub.

## Decision Outcome

Chosen option: C, with B as an additional on-demand check (the maintainer, 2026-06-07).

Downloading a component is not running it: a custom integration runs only when Home Assistant loads it, after a
restart. That window is the gate. C needs nothing from HACS, so it survives HACS updates and also catches manual
installs. B lets the operator vet a repository before pressing download.

A was rejected because HACS updates itself and would overwrite the patch, so it would need a permanent fork that misses
HACS's own fixes. The proxy was rejected because it would have to break TLS, and HACS cannot be pointed at a proxy.

Both run in a Home Assistant add-on with read-write access to the configuration folder. The scanner tools (bandit,
pip-audit) live in the add-on image, not in Home Assistant's own environment.

### Consequences

* Good, because the gate sits before execution and works for every way a component arrives.
* Good, because quarantine only moves the folder (to `<quarantine_dir>/<name>__<timestamp>/` with a `SCAN_REPORT.txt`);
  nothing is deleted and the operator can move it back.
* Bad, because the gate is before execution, not before download: the code is on disk until the scan has run.
* Bad, because a frontend card in `www/community` is served to browsers without a restart, so for cards the window may
  already be closed. Static checks of minified bundles are informational only anyway.
* Bad, because static analysis is a filter and tripwire, not a malware guarantee.

### Confirmation

`guard.py` moves risky components in `quarantine()` and runs pre-checks from the request file; the decision policy is
covered by `TestDecisionPolicy` in `marketplace_guard/tests/test_marketplace_guard.py`.
