---
status: superseded by ADR-0037
date: 2026-11-06
decision-makers: maintainer
---

# Only regular files are read, within a size limit

## Context and Problem Statement

The scan time of a new component is the time Home Assistant has to load it before the quarantine. A component could
stretch that time:

* `os.walk()` lists symbolic links to files, and every reader followed them. A link `x.py → /dev/zero` made
  `dir_hash()` read forever, a FIFO made it block; the single worker stopped and no later component was quarantined.
  A link to `secrets.yaml` named `*.py` was read and, with the AI review on, sent to the model.
* Files were read whole, without a limit.
* The line number of each raw-IP URL was counted from the start of the file (`txt[:pos].count("\n")`), quadratic in
  the number of URLs: 20,000 took 2.2 s, every doubling four times as long. Rules with an unbounded repetition such as
  `subprocess[^\n]*(curl|wget)` were retried from every start on a long line: an 85 KiB line took 2 s, a 1 MiB line
  about five minutes.

## Decision Drivers

* A component cannot make its own scan endless or slow.
* Nothing outside a component is read on its behalf.
* What is not read is reported, not silently skipped.

## Considered Options

* Time out each scan.
* Read only regular files, without following links, up to a size limit, and keep every rule linear.

## Decision Outcome

Chosen option: the second option.

* `open_regular()` opens a file only when `lstat()` says it is a regular file, with `O_NOFOLLOW` and `O_NONBLOCK`, so a
  file swapped for a link or a FIFO after the check is not followed and does not block. `read_bytes()` reads at most
  `MAX_SCAN_BYTES` (16 MiB).
* `special_entries()` reports links and special files without reading them: a link that leaves the component and a
  FIFO, device or socket are `high`, a link inside it is `info`. `dir_hash()` covers them by name and target.
* A script larger than the limit is scanned up to it: `too-large` is `high` for Python, which is never that large, and
  `medium` for JavaScript, where large bundles exist.
* Line numbers come from a bisect over the newline positions; repetitions inside rules are bounded to 500 characters.
* The hash covers more files now (this ADR and [ADR-0028](0028-compressed-copies-and-module-scripts-are-scanned.md)).
  State entries carry the hash version; an entry saved with the old hash is compared with that one and, when
  unchanged, takes the new hash, so an update of HACS Guard does not make every component look changed.

The first option was not chosen because a timeout ends a scan without a result, which is the outcome the attacker
wants; it would also have to be a process boundary to stop a blocked read.

### Consequences

* Good, because no file in a component can stop or slow the worker, and no file outside it is read for it.
* Good, because what is not read is a finding.
* Bad, because a rule now only matches when the parts it looks for are within 500 characters of each other on a line;
  bandit, which parses the code, does not have that limit.
* Bad, because a JavaScript bundle above 16 MiB is only partly scanned (and says so).

### Confirmation

`TestBoundedScanning` and `TestHashVersion` in `marketplace_guard/tests/test_marketplace_guard.py`: 100,000 raw-IP URLs and a
550 KB line scan in seconds with correct line numbers; a file above the limit is a finding; links are reported and not
followed, a link leaving the component makes the verdict `high`; a FIFO is reported and never opened (on systems with
FIFOs); an entry with the old hash is recognised as unchanged.

Accepted by the maintainer on 2026-11-06; implemented in pull request #24.
