---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Home Assistant's Marketplace replaces HACS

## Context and Problem Statement

Home Assistant 2026.11 (4 November 2026) ships HACS as part of Home Assistant, as the integration `marketplace`
("Settings → Marketplace"), and blocks the HACS custom integration. HACS Guard was built around HACS
([ADR-0001](0001-quarantine-on-write-and-a-repository-pre-check-instead-of-patching-hacs.md)). Read in the source of
`homeassistant/components/marketplace` at tag `2026.11.0` and in its documentation:

* **A new integration runs without a restart.** After the download, `async_post_installation()` reloads the custom
  integrations; for an integration with a config flow that the loader did not know yet, no restart is required and the
  frontend opens its setup at once. Its code runs seconds after the files are written, while HACS Guard waits
  `debounce_seconds` (20) and then scans. Integrations configured in YAML, and any integration the loader already knew,
  still need a restart.
* **An update still needs a restart** ("After you update an integration, restart Home Assistant to apply the update").
* **The records moved.** The Marketplace keeps `.storage/marketplace.repositories` (with `full_name`, `category`,
  `domain` and `directory` of each installed repository) and `.storage/marketplace.critical`. On its first start it takes
  the `hacs.*` files over and deletes them. HACS Guard read only `hacs.repositories` and `hacs.critical`, so it no
  longer knew which repository a folder came from, and fell back to the name the component's own manifest gives.
* **The catalog has a critical list.** Next to `https://data-v2.hacs.xyz/removed/data.json`, which HACS Guard read,
  the Marketplace reads `critical/data.json` and uninstalls the repositories in it.
* **Unchanged:** integrations go to `custom_components/<domain>`, dashboard cards to `www/community/<directory>`; the
  folder installed from a repository is chosen as before (the first folder under `custom_components`, `hacs.json`,
  stable releases unless the pre-release switch is on), so
  [ADR-0016](0016-the-pre-check-scans-what-hacs-would-install.md) holds. Next to each `.js` it writes a `.js.gz`.
  Nothing published in the Marketplace is reviewed by the Home Assistant project.

## Decision Drivers

* Say honestly what the quarantine can and cannot prevent now.
* Use Home Assistant's own records of where a folder came from; a manifest is written by the component's author
  ([ADR-0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md)).
* Keep working on Home Assistant versions before 2026.11.
* Report facts to the operator instead of guessing: whether a quarantined integration is running.

## Considered Options

* Change nothing.
* Hook into the Marketplace's install, so HACS Guard scans before the download is written. The Marketplace has no such
  hook for other integrations or add-ons, and patching it is what ADR-0001 rejected for HACS.
* Adapt: read the Marketplace's records first and the HACS ones as a fallback, read both catalog lists, say after a
  quarantine whether the integration runs, optionally restart Home Assistant then, and point to the pre-check as the
  way to look before installing.

## Decision Outcome

Chosen option: adapt (the third option).

* `scanner.installed_repositories()` reads `marketplace.repositories`, else `hacs.repositories`, and maps an
  integration's domain and a card's folder to its repository. `scan_component()` keeps where the name came from as
  `full_name_source` (`given`, `records`, `manifest`).
* `scanner.load_critical()` reads `marketplace.critical`, else `hacs.critical`, and the catalog's `critical` and
  `removed` lists, at most every six hours (ten minutes after a failure); a list that cannot be read is an `info`
  finding `catalog-unavailable` instead of being skipped silently.
* After quarantining a new integration, `_after_quarantine()` asks Home Assistant (`/api/config`, `components`)
  whether it is set up and says so in the notification. With the new option `restart_after_quarantine` (off by
  default), HACS Guard restarts Home Assistant when the quarantined integration is running.
* `DOCS.md` says that a new integration can run before the scan and that the pre-check is the way to look first.

### Consequences

* Good, because the repository name, the critical list, the allowlist and the owner match work again with the
  Marketplace, from Home Assistant's records instead of the component's manifest.
* Good, because the operator learns that a quarantined integration is running and can stop it.
* Bad, because for a new integration with a config flow the quarantine comes after its first run; it still keeps it
  from loading again, and the pre-check remains the way to look first.
* Bad, because "not set up" does not prove its code never ran: opening the setup imports the integration.

### Confirmation

`TestMarketplaceRecords` and `TestAfterQuarantine` in `marketplace_guard/tests/test_marketplace_guard.py`: the Marketplace records
come first and the HACS ones are a fallback; a card folder maps to its repository; the name's source is kept; the
catalog lists are read once per period and a failure is a finding; the notification says whether the integration runs,
and the restart happens only with the option and only when it runs.

Accepted by the maintainer on 2026-11-06; implemented in pull request #23.
