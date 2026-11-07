---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# An update that brings a new risk can be quarantined

## Context and Problem Statement

[ADR-0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md) quarantines only components that are
new to HACS Guard; a known component that reaches the threshold after an update is reported (`high-known`), because
quarantining it would take a working integration away with every update. A malicious update of a trusted component —
a compromised maintainer account, a sold project — is the usual way such attacks arrive, and it was only reported.

Since Home Assistant 2026.11 ([ADR-0024](0024-home-assistants-marketplace-replaces-hacs.md)) a new integration can run
before HACS Guard has scanned it, while an update still needs a restart. The update is now the place where a quarantine
reliably comes before the code runs.

## Decision Drivers

* Stop a malicious update before the restart loads it.
* Do not take away an integration whose known, accepted risk is unchanged by an update (a power tool that has always
  run shell commands).
* The operator decides: an update quarantine leaves the integration missing until a trusted version is installed.

## Considered Options

* Keep ADR-0002 as it is: updates are only reported.
* Quarantine every update that reaches the threshold.
* Quarantine an update only when it brings a risk at the quarantine threshold that the version before did not have,
  behind an option.

## Decision Outcome

Chosen option: the third option, with the option `quarantine_updates` on by default (the maintainer, 2026-11-06): with the
Marketplace, a quarantine of an update is the one that still comes before the code runs, and an option that is off
protects nobody who does not know about it. An operator who wants ADR-0002's behaviour turns it off.

* The state keeps, per component, the risks of its last scan (`risk_keys()`): the findings rated `medium` and up, keyed
  by their code, a vulnerable requirement by its advisory, compiled code by its file. A known risk that moves to
  another file is not a new one.
* `introduced_risk()` compares the update's risks at the threshold with those kept for the version before. For a state
  saved by an older version without risks, the verdicts are compared.
* `decide_action()` returns `quarantine-update` for a known, not allowlisted component when the option is on and the
  update brings a new risk; otherwise `high-known` as before. The notification says that the version before keeps
  running until the next restart and how to go back to a trusted version.

The second option was not chosen because it would quarantine the update of every component whose accepted risk is
unchanged, which is what ADR-0002 avoided.

### Consequences

* Good, because a malicious update of a trusted component is stopped before Home Assistant loads it.
* Good, because a component whose risk an update does not change keeps working.
* Bad, because after an update quarantine the integration is missing after the next restart until a trusted version is
  installed (the Marketplace's update entity can install an earlier version).
* Bad, because a legitimate update that adds, for example, a pinned requirement with a known vulnerability is
  quarantined as well.
* Bad, because on by default, an installation that updates HACS Guard gets update quarantines without having asked
  for them; the notification of each one says how to go back.

### Confirmation

`TestUpdateQuarantine` in `marketplace_guard/tests/test_marketplace_guard.py`: the policy, what counts as a new risk (a moved risk
does not, new compiled code and a new advisory do, the verdict fallback for older states), an update that adds shell
execution is quarantined with the option and only reported without it, and the update of a known power tool stays.

Accepted by the maintainer on 2026-11-06; implemented in pull requests #23 and #30.
