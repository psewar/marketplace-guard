---
status: accepted
date: 2026-11-02
decision-makers: maintainer
---

# The repository is site-neutral

Redacted on 2026-11-07: details of the development installation were removed from the context; the decision is
unchanged (as this decision allows).

## Context and Problem Statement

HACS Guard was written to be publishable: on 2026-06-07 the maintainer asked for a description fit for an add-on that
could be published, and on 2026-11-02 for a review before making it open source. A published repository must allow
no conclusions about the people, the home or the infrastructure it was developed on: no host names, addresses,
domains, people's names, device or entity names, places, or products that point at one installation.

A review on 2026-11-02 found such details in the repository:

* the `schema` in `marketplace_guard/config.yaml` listed the notification services and AI Task entities of the
  development installation as drop-down lists;
* the default `ai_task_entity` in `marketplace_guard/config.yaml` and `guard.py` was an entity of that installation;
* the maintainer's first name stood in the `decision-makers` field of the ADRs;
* an example prompt and a test named services and products in use there;
* comments and log messages were partly not in English, a language hint that the rest of the code does not need.

## Decision Drivers

* The repository can be made public without a review of every file by hand.
* A rule that only lives in documentation is the weakest protection; the check belongs in a tool.
* The site's own terms must not end up in the repository, not even as a list to check against.
* The add-on works on any installation without editing it first.

## Considered Options

* Keep the names; review by hand before publishing.
* Site-neutral from now on, by rules in `AGENTS.md` only.
* Site-neutral from now on, by rules in `AGENTS.md` and a check tool that reads the site's own terms from outside the
  repository.

## Decision Outcome

Chosen option: the third option.

* `tools/check_neutral.py` checks every tracked file, and with `--text` commit messages and pull request texts. Generic
  rules in the code catch private addresses and host names that are neither placeholders nor public sites; the
  site's own terms come from `~/.config/hacs-guard/site-terms.txt` or `$HACS_GUARD_SITE_TERMS` and never enter the
  repository. Without a list the tool refuses and says how to go on.
* Configuration is installation-neutral: notification targets are free text with `persistent_notification` as the
  default, and no AI Task entity is preset ([ADR-0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md)).
  Home Assistant's add-on schema has no selector that lists the entities of an installation, so the drop-down lists
  of 2026-06-07 give way to free text; the add-on lists what Home Assistant offers in its log and status sensor.
* ADRs name the role (`maintainer`) in `decision-makers`, not a person. Personal and site details may be redacted
  from accepted ADRs; the decision and its reasons stay.
* Code, comments, log messages and tests are English; `DOCS.md`, `README.md` and the translations are English and
  German.

### Consequences

* Good, because the repository can be published as it is, and a new detail is caught before it is pushed.
* Good, because a new user installs the add-on and it works, with nothing of another installation preselected.
* Bad, because the configuration page lost its drop-down lists; entity ids are typed in.
* Bad, because the details are still in the history of the development repository. Publishing therefore starts a
  new repository ([ADR-0013](0013-publish-as-a-new-repository-with-one-start-commit.md)).
* Bad, because the tool only knows the terms in the list; it does not replace reading the added lines.

### Confirmation

`python3 tools/check_neutral.py` is one of the checks in `AGENTS.md` and a step in `PUBLISHING.md`.

Accepted with the merge of pull request #3 on 2026-11-02.
