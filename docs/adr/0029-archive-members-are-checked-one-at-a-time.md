---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Archive members are checked one at a time

## Context and Problem Statement

The repository pre-check downloads a tarball of at most `max_repo_mb` (50 MB) and extracts it with limits on the
number of files and their total size ([ADR-0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md)).
`_safe_extract()` called `tar.getmembers()` first, which reads every header of the archive into memory, and checked
the limits afterwards. Headers of empty files compress well: 200,000 of them are 1.2 MB of gzip and took 87 MB of
memory and 6.8 seconds before the refusal; within the download limit that is several gigabytes, enough to end the
add-on on a small machine. Skipped links did not count against any limit at all. The refusal itself was an exception
that the caller turned into a message.

## Decision Drivers

* An archive is refused at the limit, not after it has been read completely.
* Every entry counts against a limit, also those that are skipped.
* A refusal is a fact the caller reports, not an exception it catches
  (AGENTS.md, "errors are not a control signal").

## Considered Options

* Keep `getmembers()` and lower the download limit.
* Read the members one at a time with `tar.next()` and check the limits as they come; count every entry against a
  limit of 50,000 (the Marketplace uses the same number for ZIP archives); return the reason for a refusal.

## Decision Outcome

Chosen option: the second option.

* `_safe_extract()` returns `None` when it extracted the archive, or the reason it refused it: too many entries, too
  many files or bytes, a path that leaves the target folder, a damaged archive. Nothing is written before all members
  were checked.
* `scan_repo()` reports the reason like any other pre-check failure.

The first option was not chosen because a smaller download limit still allows hundreds of thousands of headers and
would refuse large legitimate repositories.

### Consequences

* Good, because memory and time of a refusal are bounded by the limit: the 200,000-entry archive is refused after
  20,001 files with 9 MB in 0.8 seconds.
* Good, because an archive of countless links is refused as well.
* Bad, because a legitimate repository with more than 50,000 entries cannot be pre-checked (the Marketplace would not
  install such an archive either).

### Confirmation

`TestSafeExtract` and `TestSafeExtractLimits` in `marketplace_guard/tests/test_marketplace_guard.py`: the limits are exact, the
refusal comes after the first member over the limit (the remaining headers are not read), skipped links count against
the entry limit, and a damaged archive is refused with nothing written.

Accepted by the maintainer on 2026-11-06; implemented in pull request #25.
