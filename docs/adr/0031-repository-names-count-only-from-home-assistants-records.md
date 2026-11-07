---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Repository names count only from Home Assistant's records

## Context and Problem Statement

A component's repository name (`owner/repo`) decides three things: an allowlist entry `owner/repo` exempts it from
quarantine ([ADR-0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md)), hosts that match the owner
are its own backend ([ADR-0005](0005-a-components-own-backend-is-not-a-finding.md)), and the AI is told that calls to
the owner's domain are normal. The name came from HACS's records or, when they had none, from the `documentation` or
`issue_tracker` URL in the component's own `manifest.json` — written by its author
([ADR-0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md)). Since the Marketplace deleted the HACS
records ([ADR-0024](0024-home-assistants-marketplace-replaces-hacs.md)), every component fell back to its manifest:

* a manifest naming an allowlisted repository was allowlisted;
* the owner match compared substrings after removing punctuation, so an owner `ex` made `collector.webhook.example`
  the component's own backend, and the prompt told the AI not to flag it.

## Decision Drivers

* What exempts a component or relabels its findings must not come from the component.
* An owner name, however short or chosen, must not cover unrelated hosts.

## Considered Options

* Keep using the manifest as a fallback.
* Use a repository name for the allowlist, the owner match and the AI only when it comes from Home Assistant's records
  (HACS or the Marketplace) or from the operator's pre-check request; match the owner against whole host labels.

## Decision Outcome

Chosen option: the second option.

* `scan_component()` keeps where the name came from (`full_name_source`: `records`, `given`, `manifest`).
* `is_allowlisted()` matches the folder name always, the repository only with `records` or `given`.
* The owner match relabels an `outbound-host` only with `records` or `given`, and only when the owner equals one of the
  host's labels (punctuation removed): `acmecloud` matches `api.acmecloud.example`, `ex` matches nothing in
  `collector.webhook.example`.
* The AI prompt names the owner only then; otherwise it says that the owner is not known from Home Assistant's
  records.

### Consequences

* Good, because a spoofed manifest no longer reaches the allowlist, the own-backend label or the AI's trust.
* Bad, because a component installed by hand, outside HACS and the Marketplace, can only be allowlisted by its folder
  name, and its hosts are not recognised as its own backend (they stay informational).
* Bad, because a vendor domain that only contains the owner name inside a label (`acmecloudapi.example`) is no longer
  recognised; the operator can name it in `ai_prompt.txt`.

### Confirmation

`TestTrustedNames` and `TestVendorHostRelabel` in `marketplace_guard/tests/test_marketplace_guard.py`: a manifest naming an
allowlisted repository is quarantined and gets no own-backend label; the Marketplace's records allowlist it and
relabel its owner's host; a short owner name does not match inside a label.

Accepted by the maintainer on 2026-11-06; implemented in pull request #26.
