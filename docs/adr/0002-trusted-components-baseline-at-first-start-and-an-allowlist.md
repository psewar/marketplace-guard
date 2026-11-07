---
status: accepted
date: 2026-06-07
decision-makers: maintainer
---

# Trusted components: a baseline at first start and an allowlist

Backfilled on 2026-11-02. The baseline was decided on 2026-06-07 with the first version, the allowlist on 2026-06-08
(version 1.3.0). Sources: `marketplace_guard/DOCS.md`, the maintainer's review list of 2026-06-08 (item "allowlist"),
`marketplace_guard/CHANGELOG.md`.

## Context and Problem Statement

Quarantine moves a component away before Home Assistant loads it. Applied to everything, it would take running
integrations away on the first start, and it would take a known, legitimately high-rated component away again with
every update.

## Decision Drivers

* Never disrupt a running system when the add-on is installed.
* Let the operator trust a component explicitly instead of moving it back by hand after every update.

## Considered Options

* Quarantine everything that reaches the threshold.
* Record everything present at the first start as a trusted baseline; only components installed or changed later can
  be quarantined.
* Additionally, an allowlist of component names or repositories that are only reported, never quarantined.

## Decision Outcome

Chosen option: the baseline plus the allowlist (the maintainer, 2026-06-07 and 2026-06-08).

Components of the baseline and allowlisted ones are still scanned and reported; they are only exempt from quarantine. A
baseline component that reaches the quarantine threshold raises a loud alert instead.

### Consequences

* Good, because installing the add-on never breaks a working installation.
* Good, because trust is explicit and visible in the configuration (`allowlist`).
* Bad, because a component that was already malicious before the first start is only alerted on, never quarantined.
* Bad, because an allowlisted repository that is later compromised is only reported.

### Confirmation

For a verdict at the quarantine threshold, `decide_action()` in `guard.py` returns `allowlisted` for an allowlisted
component and `high-known` (alert, never move) for one that was already installed, instead of `quarantine`;
`TestDecisionPolicy` covers both.
