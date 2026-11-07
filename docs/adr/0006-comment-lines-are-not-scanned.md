---
status: superseded by ADR-0026
date: 2026-06-21
decision-makers: maintainer
---

# Comment lines are not scanned

Superseded by [ADR-0026](0026-python-is-read-the-way-python-reads-it.md): comments are still not scanned, but in
Python they are found by Python's tokenizer, not by the first characters of a line.

Backfilled on 2026-11-02, decided on 2026-06-21. Source: the review of a quarantined component of 2026-06-21, done by a
coding agent at the maintainer's request and kept in operation by the maintainer.

Redacted on 2026-11-07: details of the development installation were removed from the context; the decision is
unchanged ([ADR-0011](0011-the-repository-is-site-neutral.md)).

## Context and Problem Statement

A newly installed integration was quarantined with a `high` "secret-store access" finding. The match was a comment
that named the secret store. Comments never run, but they often name exactly the patterns the heuristics look for.

## Decision Drivers

* Findings should describe what code does, not what it mentions.
* A false `high` takes a working integration away and, after a restore with an old scanner, can take it away again.

## Considered Options

* Scan all lines.
* Skip comment lines: lines whose first non-blank characters are `#` or `//`, in Python and JavaScript alike.

## Decision Outcome

Chosen option: skip comment lines in the heuristics (2026-06-21).

### Consequences

* Good, because this class of false positive is gone; the integration from the review scans `clean`.
* Bad, because code hidden in a comment-like construct that is later evaluated is not matched by the line heuristics;
  the evaluation itself (`eval`, `exec`, decode-and-execute) is still matched.

### Confirmation

`TestSecretStoreRegex` in `marketplace_guard/tests/test_marketplace_guard.py` has a deny-list comment that must not be flagged.
