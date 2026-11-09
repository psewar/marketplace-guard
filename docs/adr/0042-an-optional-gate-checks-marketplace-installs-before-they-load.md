---
status: accepted
date: 2026-11-09
decision-makers: maintainer
---

# An optional gate checks Marketplace installs before they load

## Context and Problem Statement

Since Home Assistant 2026.11 the Marketplace sets a new integration up without a restart
([ADR-0024](0024-home-assistants-marketplace-replaces-hacs.md)). Read again on 2026-11-09 in
`homeassistant/components/marketplace` at tag `2026.11.0` and on `dev` (the install path is the same in both), and in
the frontend's `dialog-marketplace-install.ts`:

* The Marketplace writes the content, then runs the check of its repository class, `async_check_written_content()`.
  When that check raises, it puts back what was there (the version before, or nothing for a first install), and the
  install fails with the error's message in the install dialog.
* Only after that it reloads the custom integrations' manifests (JSON, no Python) and answers the frontend.
* The frontend then opens the integration's config flow at once. That imports the integration's `config_flow.py`: its
  code runs, a fraction of a second after the files were written. Marketplace Guard's watcher scans seconds later.
* There is no public hook: no event to answer, no action, nothing to register. The Marketplace sends progress signals
  (`marketplace/subscribe`), but they cannot stop an install. The repository classes (integration, dashboard card,
  template, theme) override the check without calling `super()`.

Code that runs inside Home Assistant Core has Core's rights: it can move a quarantined folder back, change the
add-on's options through the Supervisor API, install apps. A quarantine after the fact cannot undo that. What helps is
not letting the code run at all.

[ADR-0001](0001-quarantine-on-write-and-a-repository-pre-check-instead-of-patching-hacs.md) rejected patching HACS: an
integration with its own releases, and a restart came before any code ran, so the watcher had time.

## Decision Drivers

* Stop a risky install before its code runs, not after.
* Use the Marketplace's own way to refuse content, so that it cleans up and tells the user.
* One place decides, with the same rules as for a quarantine
  ([ADR-0023](0023-one-worker-makes-every-scan-and-quarantine-decision.md)).
* Never pretend to protect: when the hook point is gone, say so loudly.
* Nothing that only works on one Home Assistant version without telling.

## Considered Options

* Keep the pre-check and the quarantine after the fact.
* Race: subscribe to the Marketplace's progress signals and move the folder away before the config flow starts.
* A gate integration that wraps `async_check_written_content()` and asks the add-on for a verdict.
* A gate in Home Assistant's loader that refuses to import an unchecked custom integration.
* Wait for Home Assistant to offer a hook (proposed to the project, see below).

## Decision Outcome

Chosen option: the gate integration (third option), opt-in, as the bridge until Home Assistant offers a hook.

* The add-on carries the integration `marketplace_guard_gate` in its image. With the option `marketplace_gate` it
  copies it into `custom_components` (again when the copy differs, ignoring `__pycache__`), records that copy as
  accepted, and notifies with a link to add the integration; when it replaces an earlier copy, it only logs that
  Home Assistant loads the new one at its next restart. Its `manifest.json` carries the add-on's version
  (`tools/check.py`).
* Once set up, the gate wraps `async_check_written_content` of the Marketplace's `Repository` class and of every
  subclass that defines its own. The Marketplace's own check runs first. For integrations and dashboard cards (the code
  Marketplace Guard scans) the gate writes a request (`marketplace_guard/gate/requests/<id>.json`: the content's path
  relative to the configuration folder, the repository, whether it is an update) and waits for the answer
  (`.../verdicts/<id>.json`). A refusal raises the Marketplace's own error (`validation_failed`): the Marketplace puts
  back what was there, and the dialog names the reason.
* The add-on's worker answers before anything else, once the baseline is recorded. It accepts only a folder directly in
  a watched folder, scans it statically and decides like for a new install or an update (thresholds, allowlist,
  `quarantine_updates`): what would be quarantined is refused, with a notification. What is allowed takes the usual way
  afterwards (scan, AI review, notifications). Answers nobody took are removed after ten minutes.
* Without an answer in time (default 120 seconds) the gate refuses; its options can allow instead. When the Marketplace
  lacks the method (another Home Assistant version), the gate changes nothing, does not start, and says so in a
  notification; the status sensor's `marketplace_gate` is `active` only while Home Assistant has the gate loaded.
  Until it is, the add-on asks Home Assistant every minute instead of at the heartbeat.
* The gate's logic lives in `gatecore.py` without Home Assistant imports and is tested with the standard library.

The race (second option) cannot win reliably: a scan takes seconds, the import follows in milliseconds. A loader gate
(fourth option) would cover copies made by hand too, but it patches the loader every integration goes through, so a
mistake would stop Home Assistant from starting; copies made by hand load only after a restart, which the watcher
already waits for. Waiting alone leaves the gap open.

What differs from ADR-0001: the gate is opt-in; it wraps a method whose purpose is to refuse content, and uses the
error path the Marketplace already handles; it checks that the method is there before it changes anything; and the
alternative now is code that runs before any scan.

### Consequences

* Good, because what would be quarantined never runs, for new installs and updates through the Marketplace alike, and
  the Marketplace cleans up itself.
* Good, because the user sees why in the install dialog, and the decision is the one a quarantine would have made.
* Bad, because it hooks into an internal method of Home Assistant. A release can rename or change it; the gate then
  does not start and says so, and Marketplace Guard has to be updated.
* Bad, because the gate is code inside Home Assistant Core. A component already running there could unwrap it; such a
  component has Core's rights anyway.
* Bad, because an install waits for the scan (seconds), and with the default no install goes through while the add-on is
  stopped.
* Bad, because the AI second opinion is not part of the gate's decision; it follows after the install.

### Confirmation

`marketplace_guard/tests/test_gate.py`: the wrapping covers every class with its own check, never twice, and is undone;
another version without the method is left alone; requests name the content relative to the configuration folder and
refuse other places; request and answer go through files, a broken answer refuses; the outcome follows the answer and
the setting. `TestMarketplaceGate` in `marketplace_guard/tests/test_marketplace_guard.py`, from the gate's request to
its decision: a risky new integration is refused, a clean one allowed; an update is refused only when it brings a new
risk; an allowlisted one is allowed; requests it cannot check are refused; requests wait for the baseline; old answers
are removed; the gate is installed once, accepted, kept current without asking again to add it, and not reinstalled
for `__pycache__`; without the Marketplace it is not installed; the gate state is a fact, asked for every minute until
it is active and not at all without the option. On a running Home Assistant: an install refused through the
Marketplace's dialog, and an allowed one.

### Toward a hook in Home Assistant

The check the gate wraps is the natural place for an official extension point: a way for an integration or app to
review content the Marketplace has written, before it is loaded, with the Marketplace's own clean-up on a refusal.
When Home Assistant offers one, the gate is replaced by it, in a new ADR that supersedes this one.

Accepted by the maintainer on 2026-11-09; implemented in pull requests #46 and #47.
