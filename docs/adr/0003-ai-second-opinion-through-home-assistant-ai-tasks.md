---
status: superseded by ADR-0012
date: 2026-06-07
decision-makers: maintainer
---

# AI second opinion through Home Assistant AI Tasks

Superseded by [ADR-0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md): the review is off
by default and no installation-specific entity is preset.

Backfilled on 2026-11-02, decided on 2026-06-07 (version 1.1.0). Sources: the maintainer's request of 2026-06-07 to let
an AI Task of Home Assistant check components as well, `marketplace_guard/DOCS.md` ("AI second opinion & privacy").

## Context and Problem Statement

Static checks see patterns, not intent: the same network call is legitimate in one component and exfiltration in
another. A language model can judge intent from the code, but it can also be wrong, and sending code to a cloud model
leaves the network.

## Decision Drivers

* A second, independent judgement on top of the static scan.
* Use the models the installation already has instead of configuring a provider in the add-on.
* Keep code inside the network by default.
* A model's false positive must not take a working component away.

## Considered Options

* No AI review.
* Call a model provider directly from the add-on.
* Call a Home Assistant AI Task entity through the Home Assistant API.

## Decision Outcome

Chosen option: a Home Assistant AI Task entity (the maintainer, 2026-06-07).

* The AI is a third voter that complements the static scan and never lowers its verdict.
* The default entity is a local one; choosing a cloud entity is the operator's decision and sends the (public)
  component source to that provider.
* By default the AI cannot quarantine on its own (`ai_can_quarantine: false`): a "malicious" verdict counts as
  `medium` and is reported, because small local models produce false positives.
* A fallback entity (`ai_task_entity_fallback`, version 1.3.0) is used when the first one fails, for example when the
  local model is unavailable.
* The full AI assessment goes into the component's report.

### Consequences

* Good, because the add-on needs no provider credentials and follows whatever models the installation offers.
* Good, because a wrong AI verdict alone never moves a component.
* Bad, because verdicts vary between runs and models; tuning needs several runs to judge.
* Bad, because a large component is cut to `ai_max_source_kb` before review, so the AI may not see all of it.

### Confirmation

`run_ai_review()` in `guard.py` maps the AI verdict to a severity and only maps "malicious" to `high` when
`ai_can_quarantine` is set.
