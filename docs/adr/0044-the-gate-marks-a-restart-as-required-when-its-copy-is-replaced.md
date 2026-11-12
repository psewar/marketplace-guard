---
status: accepted
date: 2026-11-11
decision-makers: maintainer
---

# The gate marks a restart as required when its copy is replaced

Complements [ADR-0042](0042-an-optional-gate-checks-marketplace-installs-before-they-load.md), which stays as it is.

## Context and Problem Statement

With the option `marketplace_gate` the app copies the gate integration into `custom_components` and replaces that copy
when its own version differs (ADR-0042). Home Assistant does not load the new copy until it restarts: Python keeps the
imported module, and reloading or re-adding the config entry runs the old code again. ADR-0042 only has the app log
that Home Assistant "loads it at its next restart". Home Assistant itself cannot see that a restart is pending, so an
automation that restarts when something needs it does nothing, and the version before keeps checking indefinitely.
That matters most when a Home Assistant update stopped the gate (it does not start when the Marketplace's method is
gone) and an update of the app is the fix: protection stays off until someone restarts by hand.

Home Assistant 2026.11 has a flag for this. Read on 2026-11-11 in `homeassistant/helpers/system_state.py` at tags
`2026.11.0` and `2026.11.1` and on `dev` (the file is the same in all three):

* `async_set_home_assistant_restart_required(hass, domain)` marks that Home Assistant needs a restart and lists the
  domain as its source. It must be called in the event loop. The flag latches: only a restart clears it.
* The trigger and the condition `homeassistant.restart_required` (*Restart required*) follow that flag, so automations
  can restart at a time of their choosing.
* The Marketplace does not set it for its own installs; it creates a repair instead. Nothing sets it for a custom
  integration's folder that something other than the Marketplace replaced.

The gate needs the Marketplace, which also came with 2026.11.0, so wherever the gate runs the helper exists today. A
later version could rename it.

The app cannot set the flag: it is a function inside Home Assistant's process, without an action or API that the app
could call. The gate runs inside that process.

## Decision Drivers

* Report the pending restart as a fact Home Assistant can use, not as a log line someone has to read.
* The gate knows best whether the code it runs is the code on disk.
* Work also while the gate is not active, since that is when the restart matters most.
* Check that the helper exists before using it, and say so when it does not; no exception as control flow.
* Nothing that blocks Home Assistant's event loop.

## Considered Options

* Keep logging in the app (as ADR-0042).
* The app tells Home Assistant (an action, a repair, a notification from outside).
* The gate compares the version in its `manifest.json` on disk with the version it was imported with, and sets Home
  Assistant's restart flag when they differ.
* The gate compares a hash of all its files on disk with the files it was imported from.
* The gate watches its folder for file changes instead of reading it periodically.

## Decision Outcome

Chosen option: the gate compares its manifest's version (third option).

* While Python imports the gate, it reads the version from its own `manifest.json` (`RUNNING_VERSION`) and looks up
  `homeassistant.helpers.system_state.async_set_home_assistant_restart_required` with `find_spec` and `getattr`
  (`SET_RESTART_REQUIRED`, `None` when this Home Assistant has none). Home Assistant imports custom integrations in an
  executor thread, so neither blocks the event loop. The loader's own record of the manifest is not used: it is read
  when `custom_components` is scanned, which can be before the import, after a newer copy arrived.
* The watch starts in the integration's `async_setup`, once per run of Home Assistant, for as long as the module is
  loaded. It is not bound to the config entry: a failed entry setup runs the entry's unload callbacks, which would stop
  the watch exactly when the gate is not active. `CONFIG_SCHEMA` says the integration has no YAML configuration.
* At setup and then every minute (`COPY_CHECK_SECONDS`), an executor job reads the version on disk; `CopyWatch` in
  `gatecore.py` judges it as a fact: `current` (same version), `replaced` (another version, newer or older after a
  rollback) or `unknown` (a version could not be read, for example while the app swaps the folder; nothing is
  concluded and the watch goes on). The first `replaced` sets the flag with the domain `marketplace_guard_gate` and
  stops the watch: the flag latches until the restart, and the restart loads the new copy.
* Without the helper, the gate logs at setup that it has none and, on `replaced`, raises a persistent notification that
  names both versions instead.
* The app's log line for a replaced copy says that a running gate marks the restart as required.

The app has no way to set the flag (second option): a repair or a notification from outside is not what the trigger
and condition follow. A content hash (fourth option) would also see a copy changed without a new version, but every
change to the app's files raises the version, `tools/check.py` keeps the gate's manifest at that version, and the app
replaces the copy only with the files of its own version; the version is also what the log and the user can name. A
file watch (fifth option) needs a watcher library or thread inside Home Assistant for one small file that a minute's
poll reads at no measurable cost.

### Consequences

* Good, because Home Assistant shows the pending restart with its reason, and an automation can restart in a window
  that suits the installation, so a new gate takes effect without anyone reading the app's log.
* Good, because it also covers the case where the gate is not active and an app update is the fix.
* Good, because the logic is in `gatecore.py` and tested with the standard library.
* Bad, because the gate before 2.5.0 has no watch: the update to 2.5.0 itself needs one restart by hand.
* Bad, because a copy changed by hand without a new version is not noticed (the app replaces such a copy with its own
  files at its next start).
* Bad, because the gate keeps reading one file a minute while Home Assistant runs, until the copy is replaced.
* Bad, because a removed config entry leaves the watch running until the restart; a new copy then still marks a
  restart as required, which is right, since re-adding the entry would run the old module.

### Confirmation

`marketplace_guard/tests/test_gate.py`, `TestCopyWatch`: a newer copy on disk sets the flag once (latched), the same
version does not, an older copy after a rollback does, an unreadable or missing version concludes nothing and the watch
goes on, the shipped gate can read its own version. `TestFindFunction`: the lookup finds an existing function and gives
`None` for a missing module, package or function without raising. Against Home Assistant 2026.11.1 with the gate
loaded: the same version leaves `home_assistant_restart_required` false over several minutes, a newer manifest on disk
sets it with the source `marketplace_guard_gate` within one interval, and without the helper a notification names the
new version; the gate of 2.4.2 leaves the flag unset in the same test.

Accepted by the maintainer on 2026-11-12; implemented in pull request #50.
