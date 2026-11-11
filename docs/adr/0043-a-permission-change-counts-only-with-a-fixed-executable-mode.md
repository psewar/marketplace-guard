---
status: proposed
date: 2026-11-11
decision-makers: maintainer
---

# A permission change counts only with a fixed executable mode

Calibrates the rule `runtime-fetch-exec` of the static scan, as
[ADR-0035](0035-docstrings-are-read-as-text-unless-the-code-reads-them.md) did for docstrings.

## Context and Problem Statement

`runtime-fetch-exec` is a `high` rule: code that downloads or installs more code at run time. One of its parts looks
for `os.chmod`, the step that makes a downloaded file runnable. It matched any `os.chmod(` followed on the same line by
`07` or `05` (with or without `o`), anywhere before the next `)`.

A published integration's update replaces a file atomically: it writes a temporary copy and gives that copy the
permissions of the file it replaces, `os.chmod(temp_name, original.st_mode & 0o7777)`. `0o7777` is a mask that keeps
the existing bits; it grants nothing. The rule rated the update `high`, and the gate refused it before it could load
([ADR-0042](0042-an-optional-gate-checks-marketplace-installs-before-they-load.md)), although the version before was
`medium` and the update brought no new behaviour of that kind. Keeping permissions while replacing a file is common
and correct, so the rule would keep refusing careful code.

The same part missed real cases: a first argument with parentheses (`os.chmod(os.path.join(d, "x"), 0o755)`) ended
the search at the first `)`, and a mode with a leading special bit (`0o4755`) did not start with `7` or `5`.

## Decision Drivers

* A `high` verdict that rests on harmless code teaches the operator to ignore verdicts, and with the gate it blocks
  updates.
* The rule must still find the step it is meant for: a fixed mode that makes a file executable.
* Rules stay bounded per line ([ADR-0037](0037-each-reader-gets-a-limit-that-fits-what-it-costs.md)).

## Considered Options

* Keep the rule; let operators allowlist components that keep permissions.
* Match `os.chmod` only when its mode is a fixed number that grants execution: the last argument is an octal
  literal (with or without `0o`, optionally `mode=`) with an odd digit, that is an execute bit.
* Drop `os.chmod` from the rule; downloading and running stay covered by its other parts and by `shell-exec`.

## Decision Outcome

Proposed: the second option.

* The `os.chmod` part of `runtime-fetch-exec` matches a call whose last argument is a literal mode with an execute bit:
  `0o755`, `0755`, `0o700`, `0o555`, `0o711`, `0o4755`, `mode=0o711`. The first argument may contain one level of
  parentheses. Every repetition is bounded.
* A mode computed from something else does not match: `st_mode & 0o7777`, `stat.S_IMODE(...)`, `0o7777 & mode`. A
  literal mode without an execute bit (`0o644`, `0o600`) did not match before and does not now.
* The other parts of the rule (`urlretrieve`, `wget`/`curl` with a URL, `pip install`, a subprocess running `curl` or
  `wget`) are unchanged.

The first option keeps refusing correct code and makes the allowlist a habit, which turns off every later check of
that component. The third loses the one part that sees a downloaded binary being made runnable without a shell.

### Consequences

* Good, because keeping a replaced file's permissions is no longer `high`: the update above is `medium`, like the
  version before it.
* Good, because a fixed executable mode is found in more forms than before (nested first argument, special bits).
* Bad, because adding execute bits to an existing mode (`st_mode | 0o111`, `| stat.S_IEXEC`) is not matched, as
  before. Running the file afterwards still needs `subprocess`, `os.system` or similar, which other rules and bandit
  report.
* Neutral: a fixed `0o700` on a private folder stays a finding, as before; directories need the execute bit to be
  entered, and the rule cannot tell a folder from a file.

### Confirmation

`TestRuntimeFetchExec` in `marketplace_guard/tests/test_marketplace_guard.py`: fixed executable modes, including a
nested first argument and special bits, are found; masks and modes derived from an existing file are not; a long
line stays fast. Without the change the cases that keep permissions fail. The evil fixture
(`python3 guard.py scan-path tests/fixtures/evil`) keeps both of its `runtime-fetch-exec` findings.
