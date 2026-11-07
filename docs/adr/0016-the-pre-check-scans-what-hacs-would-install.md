---
status: accepted
date: 2026-11-02
decision-makers: maintainer
---

# The pre-check scans what HACS would install

## Context and Problem Statement

The repository pre-check ([ADR-0001](0001-quarantine-on-write-and-a-repository-pre-check-instead-of-patching-hacs.md))
is meant to vet a repository before it is downloaded in HACS. It scanned the default branch, and under
`custom_components` the first folder the file system listed. A reading of HACS 2.0.5 on 2026-11-02 showed that HACS
installs something else in three cases:

* HACS takes the first directory of the repository tree under `custom_components`, which is git's order by name, not
  the order of a file system listing. With several folders the pre-check could scan another one than HACS installs.
* With `content_in_root` in `hacs.json`, HACS installs the repository root.
* HACS installs a release when the repository has one, not the default branch; with `zip_release` it downloads a
  release asset instead of the repository's files.

## Decision Drivers

* The verdict of a pre-check is about the code HACS would put on disk.
* Where the pre-check cannot see that code, it says so instead of reporting a verdict for something else.
* No second copy of HACS's download logic that has to follow every HACS release.

## Considered Options

* Keep scanning the default branch and the first listed folder.
* Follow HACS's choice: the newest release that is neither a draft nor a pre-release (or the default branch without
  one), the folder HACS picks, and a note where the installed files come from elsewhere.
* Also download and scan `zip_release` assets.

## Decision Outcome

Chosen option: the second option.

`pick_release()` picks the release, `scan_root_like_hacs()` the folder (first folder under `custom_components` in git's
order, a folder compared with a trailing `/`; the root with `content_in_root`; the root for repositories without
`custom_components`). `precheck_notes()` adds to report and notification what was scanned (release or default branch,
folder), how many folders `custom_components` has when there are several, and for `zip_release` that the installed
asset was not scanned.

Release assets are not downloaded: that would need a second hardened archive format (zip) and the asset rules of HACS
for every category. Quarantine on write scans the installed files in every case, so the pre-check stays a
preview and the gate stays where the code lands.

### Consequences

* Good, because the pre-check verdict refers to the version and folder HACS would install, and says what it scanned.
* Good, because a `zip_release` repository is no longer reported clean without a word about the asset.
* Bad, because a pre-release or an older version chosen in HACS by hand is not what the pre-check scans.
* Bad, because frontend repositories are still scanned as a whole; which files HACS takes from them (root, `dist`,
  release assets) is not followed.
* Bad, because the pre-check makes one more GitHub API call (releases) per repository.

### Confirmation

`TestPreCheckLikeHacs` in `marketplace_guard/tests/test_marketplace_guard.py`; a live pre-check of HACS itself on 2026-11-02 scanned
release 2.0.5 in `custom_components/hacs` and noted its release asset.

Accepted with the merge of pull request #3 on 2026-11-02.
