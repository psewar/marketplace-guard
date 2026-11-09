---
status: accepted
date: 2026-11-07
decision-makers: maintainer
---

# The add-on is renamed to Marketplace Guard

## Context and Problem Statement

Home Assistant 2026.11 built HACS into the core as the Marketplace
([ADR-0024](0024-home-assistants-marketplace-replaces-hacs.md)): the place users install custom components from is now
called the Marketplace, and the name "HACS" fades from the interface. The add-on was named after HACS. It is about to
be published ([ADR-0013](0013-publish-as-a-new-repository-with-one-start-commit.md)), and an add-on's slug is its
identity: it names the add-on's folders, the status sensor and the configuration folder on the host. Once others
install it, a new slug breaks their installations; before the publication only the maintainer's installation exists.

## Decision Drivers

* The name says where users get the components the add-on guards, in Home Assistant's own words.
* The slug is changed now or never: after the publication a rename costs every user their configuration.
* What the add-on writes into Home Assistant's folders carries its name consistently.
* Components installed through HACS on older versions, or by hand, stay covered whatever the name says.

## Considered Options

* Keep the name HACS Guard and the slug `hacs_guard`.
* Rename the add-on, keep the slug `hacs_guard` and the default paths.
* Rename the add-on, its slug and everything named after it to Marketplace Guard.
* Rename to a source-neutral name such as Component Guard.

## Decision Outcome

Chosen option: the third option, in version 2.0.0 before the first publication.

* Name "Marketplace Guard", slug `marketplace_guard`, add-on folder `marketplace_guard/` in the repository, test module
  `test_marketplace_guard.py`.
* Defaults: request file `/homeassistant/marketplace_guard/scan_request.txt` (reports next to it), quarantine folder
  `/homeassistant/_marketplace_quarantine`, status sensor `sensor.marketplace_guard`; code built into the image in
  `/opt/marketplace_guard`, AppArmor profile `marketplace_guard`; log prefix `[marketplace-guard]`, notification
  titles "Marketplace Guard"; site term list of `tools/check_neutral.py` in `~/.config/marketplace-guard/`.
* The notice about a code override in `/homeassistant/hacs_guard/code` (ADR-0033) is dropped: the renamed add-on is a
  new installation for the Supervisor and never had that folder. The notice about an `ai_prompt.txt` next to the
  request file stays.
* No migration code: the only existing installation is moved by hand (options, `ai_prompt.txt`, reports, the
  request file); its state is recorded again by the baseline of the first start, which scans every component.
* Accepted ADRs keep the name they were written under; their references to repository files point to the new paths.

The first option keeps a name that Home Assistant's interface no longer uses. The second would leave `hacs_guard` in
every folder and entity of every public installation for good. The fourth names the coverage more exactly, but users
look for the Marketplace, not for "components".

### Consequences

* Good, because the add-on is named the way Home Assistant names the place it guards, from its first public version.
* Good, because folders, entity and log carry one name.
* Bad, because an existing installation is a different add-on for Home Assistant: it is installed anew, its options
  are set again, and its baseline is recorded again. This is the one exception to "an existing configuration keeps
  working without edits" in `AGENTS.md`, taken while the maintainer's installation is the only one.
* Bad, because components installed through HACS on Home Assistant before 2026.11, or by hand, are guarded as well
  without the name saying so; `DOCS.md` says it.

### Confirmation

`marketplace_guard/config.yaml` names the add-on and the slug; `DEFAULTS` in `marketplace_guard/guard.py` and the
options agree (checked by `tools/check.py`); `TestSiteTermList` in `tools/test_check_neutral.py` covers the list left
under the former name; no file outside the changelog and the accepted ADRs names `hacs_guard` or "HACS Guard" except
where it tells the former name.

Accepted by the maintainer on 2026-11-08; implemented in pull request #36.
