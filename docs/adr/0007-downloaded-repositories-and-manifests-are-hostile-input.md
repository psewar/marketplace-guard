---
status: accepted
date: 2026-06-08
decision-makers: maintainer
---

# Downloaded repositories and manifests are hostile input

Backfilled on 2026-11-02, decided on 2026-06-08 (version 1.3.0); the handling of links in archives changed on
2026-06-21. Sources: the maintainer's review list of 2026-06-08 (items 1–3, "implement all"), the review of a
quarantined component of 2026-06-21, `marketplace_guard/CHANGELOG.md`.

## Context and Problem Statement

A security scanner reads exactly the code it distrusts. A hostile `manifest.json` could make `pip-audit` fetch from an
attacker's URL during the scan; a hostile repository archive could fill memory or disk, or write outside the target
folder through path traversal or links. A scanner that can be attacked through its input would be worse than none.

## Decision Drivers

* Scanning must not fetch, run or write anything the scanned code chooses.
* Limits on size and count, so a scan cannot exhaust the add-on.
* Legitimate repositories must still scan.

## Considered Options

* Trust the input and rely on the container.
* Treat every scanned file, manifest and archive as hostile and constrain each step.

## Decision Outcome

Chosen option: treat it as hostile (the maintainer, 2026-06-08).

* Manifest requirements are sanitized before `pip-audit`: only plain specifiers pass; URL, VCS, editable and index
  options are dropped and reported. `pip-audit` runs with `--no-deps`.
* A pre-check download is capped (`max_repo_mb`); extraction is capped in total size and file count.
* Extraction writes only regular files and directories inside the target folder. Links, device nodes and FIFOs are
  skipped. A path that escapes the target folder aborts the pre-check.
* Scanned code is never imported or run.

On 2026-06-21 the handling of links changed: the first version aborted the whole archive on any link, which blocked
legitimate repositories that contain a symlink (for example a documentation file pointing to another). Links are now
skipped instead; they are never extracted, so they cannot be used to write outside the target.

### Consequences

* Good, because the scan cannot be turned into a download or write primitive by the scanned code.
* Bad, because a vulnerability behind a URL or VCS requirement is not audited; the dropped requirement is reported
  instead.
* Bad, because a repository above the size limit cannot be pre-checked.

### Confirmation

`TestSanitizeReqs` and `TestSafeExtract` in `marketplace_guard/tests/test_marketplace_guard.py` cover `_sanitize_reqs` in
`scanner.py` and `_safe_extract` in `guard.py`. The size limits have no test yet.
