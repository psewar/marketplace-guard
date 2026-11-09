---
status: proposed
date: 2026-11-09
decision-makers: maintainer
---

# The first start ends with one summary

## Context and Problem Statement

On the first start Marketplace Guard records every installed component as trusted (the baseline). Until now it sent a
notification for each component of the baseline whose verdict reached the quarantine threshold, and nothing else: an
installation without such a component heard nothing at all, one with several got several notifications, and none of
them said what to do next. What a new user needs to set (a push target, maybe the AI second opinion) depends on names
only their Home Assistant knows: its notify services and AI Task entities. Marketplace Guard already asks Home
Assistant for both ([ADR-0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md)), but showed
them only in the log.

## Decision Drivers

* A new user learns that the app works and what to set next, without reading the log.
* Names a setting needs are shown as this Home Assistant has them, not guessed or preset (ADR-0012).
* No more notifications than needed; a component worth a look is still named.
* Text from a component is shown as code (ADR-0032).

## Considered Options

* Keep one notification per component of the baseline at the quarantine threshold.
* One summary after the baseline, in place of the notifications per component.
* A summary in addition to the notifications per component.

## Decision Outcome

Proposed: the second option.

* After the baseline of the first start (no saved state, **Scan on start** on), one notification `Marketplace Guard is
  active` says: how many components were recorded as trusted; which of them are worth a look (verdict at the
  notification threshold or above, highest first, at most ten named); where alerts go, or, while only
  `persistent_notification` is set, the notify services Home Assistant has; the AI Task entities while the AI second
  opinion is off, or whether it is usable when it is on; and how to pre-check a repository.
* Components of the baseline get no notification of their own.
* When the saved state was unreadable and the baseline is recorded again, the existing "state lost" notification names
  the components worth a look; no summary is sent.
* The status sensor gets the attribute `notify_targets_available`: the notify services Home Assistant has, without
  `send_message`, which needs an entity and cannot take a message here.

The first option is silent where nothing is risky and loud where several are, and never says what to set. The third
sends the same names twice.

### Consequences

* Good, because every first start ends with a notification that confirms the app works and says what to set, with the
  names to copy.
* Good, because components of the baseline at the notification threshold are named now, not only those at the
  quarantine threshold, in one notification.
* Bad, because a component of the baseline at the quarantine threshold no longer gets a notification with its own
  findings; the summary names it, and the findings are in its report.
* Bad, because the names of the notify services (often device names) appear in a notification and a sensor attribute
  inside Home Assistant, where they already are.

### Confirmation

`TestWelcome` in `marketplace_guard/tests/test_marketplace_guard.py`: the first start sends exactly one notification,
the summary, which counts the baseline and names the component worth a look; it names the notify services without
`send_message` and the AI Task entities; with push targets set it says where alerts go; a later start and a first
start without a baseline scan send none; an unreadable state names the components in the "state lost" notification and
sends no summary; the components worth a look follow the notification threshold, highest first; the status sensor
carries `notify_targets_available`.
