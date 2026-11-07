---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# The static verdict is acted on before the AI review

## Context and Problem Statement

A new or changed component was scanned, then reviewed by the AI
([ADR-0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md)), and only then quarantined or
reported. The AI call waits up to `ai_timeout` (120 seconds by default), and `_ha_post()` repeated a timed-out call
twice more, for the configured entity and again for the fallback: up to about twelve minutes in which a component whose
static verdict already reached the quarantine threshold stayed where Home Assistant loads it. HACS and the Home
Assistant Marketplace ask for a restart right after an install, so that is exactly the window the quarantine is for
([ADR-0001](0001-quarantine-on-write-and-a-repository-pre-check-instead-of-patching-hacs.md)).

## Decision Drivers

* A quarantine must not wait for anything it does not need.
* The AI review only ever raises a verdict, it never lowers one.
* The operator gets one notification per scan, not one before and one after the review.
* A review that did not get through is retried later ([ADR-0017](0017-an-unreachable-ai-review-is-retried-within-a-bound.md)),
  so retrying inside the scan only adds waiting.

## Considered Options

* Keep the order: scan, AI review, decision.
* Decide on the static verdict first; when that decision is a quarantine, act at once and skip the review; otherwise
  run the review and decide once on the combined verdict.
* Always act on the static verdict first and review afterwards, notifying again when the AI raises the verdict.

## Decision Outcome

Chosen option: the second option.

* `handle_component()` computes `decide_action()` on the static verdict. A `quarantine` is carried out at once, without
  calling the AI. Any other outcome runs the review (when it is on) and then decides once on the combined verdict, so
  the AI can still raise a component to quarantine and the operator is told once.
* The AI call makes one attempt per entity (`_ha_post(..., retries=1)`); a review that could not reach Home Assistant
  or the AI Task is retried by the heartbeat as before.

The third option was not chosen because it notifies twice for every component the AI looks at, and a notification that
is replaced a minute later teaches the operator to ignore them.

### Consequences

* Good, because a statically high component is quarantined within the scan time, whatever the model does.
* Good, because a slow or absent model costs `ai_timeout` once per entity instead of three times.
* Bad, because a quarantined component gets no AI assessment in its report; the AI could only have confirmed it.
* Bad, because a component below the threshold is still reported only after the review; that is a notification, not a
  protection, so waiting is acceptable.

### Confirmation

`TestStaticVerdictFirst` in `marketplace_guard/tests/test_marketplace_guard.py`: a statically high component is quarantined without
an AI call; the AI still raises a quiet new component to quarantine; a reported component gets one notification; the
AI call is made with `retries=1`.

Accepted by the maintainer on 2026-11-06; implemented in pull request #22.
