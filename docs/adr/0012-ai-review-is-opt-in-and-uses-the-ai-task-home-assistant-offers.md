---
status: accepted
date: 2026-11-02
decision-makers: maintainer
---

# AI review is opt-in and uses the AI Task Home Assistant offers

Supersedes [ADR-0003](0003-ai-second-opinion-through-home-assistant-ai-tasks.md).

## Context and Problem Statement

ADR-0003 introduced the AI second opinion through Home Assistant AI Tasks, on by default with an entity of the
development installation preset. On another installation that entity does not exist, so every review failed, and the
failure only showed as an error text in the report. Whether a cloud service may receive component code is the
operator's decision, and a preset cannot know it.

## Decision Drivers

* The add-on works on any installation without editing it first.
* Code goes to a model only after the operator has turned the review on.
* The add-on knows before a call whether a review can run, and says so as a state, not as an error text.
* What ADR-0003 got right stays: the AI complements the static scan and never weakens it, and alone it cannot
  quarantine by default.

## Considered Options

* Keep the review on and preset an entity name.
* On by default with the entity Home Assistant prefers.
* Off by default; when turned on, the configured entity, or the entity Home Assistant prefers when none is
  configured.

## Decision Outcome

Chosen option: the third option.

* `ai_review` is off by default. `ai_task_entity` and `ai_task_entity_fallback` are free text; empty means none (the
  old value `none` keeps working).
* With `ai_review` on and no entity configured, the call goes without an entity id, so Home Assistant uses the AI Task
  entity its own settings prefer.
* At the start and with every status heartbeat the add-on asks Home Assistant which `ai_task.*` entities exist and
  decides up front which entities a review tries (`ai_plan()`): the configured one, then the fallback, or the
  preferred one. States: `off`, `ready`, `unknown` (Home Assistant not reachable: the configuration is tried),
  `no_ai_task_entity`, `entity_missing`. The log says what to set; the status sensor carries the state
  (`ai_review`) and the available entities (`ai_task_entities`). Without a usable entity the review is skipped
  with that state instead of failing.
* Unchanged from ADR-0003: a "malicious" AI verdict counts as `medium` unless `ai_can_quarantine` is on; the AI never
  lowers the static verdict; the full assessment goes into the report; the source sent is capped by
  `ai_max_source_kb`.

The second option was not chosen because the entity Home Assistant prefers may be a cloud service picked for another
purpose; sending component code there should be a choice made for HACS Guard.

### Consequences

* Good, because a new installation needs no AI integration and shows no AI errors.
* Good, because an existing configuration keeps working: stored values for `ai_review` and the entities stay.
* Bad, because the second opinion is unused until the operator turns it on.
* Bad, because whether Home Assistant has a preferred AI Task entity is not visible through its REST API; with none
  set, a review without a configured entity fails at the call and is reported in the finding.

### Confirmation

`TestAiPlan` in `marketplace_guard/tests/test_marketplace_guard.py`; `DEFAULTS` in `guard.py` and `options` in
`marketplace_guard/config.yaml` have `ai_review` off and no entity.

Accepted with the merge of pull request #3 on 2026-11-02.
