---
status: accepted
date: 2026-11-02
decision-makers: maintainer
---

# Everything in a component folder is scanned, test code included

## Context and Problem Statement

Since June 2026 the scanner skipped folders named `test`, `tests`, `testing`, `fixtures` and `node_modules`, and files
named `test_*.py`, `*_test.py` and `conftest.py`, on the assumption that Home Assistant never loads them; test suites
do things that look dangerous (a test `secrets.yaml`, mocks). The AI prompt told the model the same.

A review on 2026-11-02 showed two ways around the scan:

* The check looked at the whole path, so a component whose own folder had one of these names was not scanned at all
  and reported clean.
* A component can import its own test modules: `from .tests.payload import run` in `__init__.py` runs code that the
  scanner never read. A probe that reads the secret store and sends it to a raw IP gave `high` in `helpers/` and
  `clean` in `tests/`. bandit, which never skipped these files, rates file reads and `urlopen` as code hygiene, so it
  did not catch it either.

## Decision Drivers

* A malicious component must not be able to hide code from the scan by naming a file or folder.
* Few false positives: test suites shipped inside a component folder should not quarantine a legitimate component.

## Considered Options

* Keep the exclusion and describe the gap as a known limitation.
* Scan test code, but cap its findings at `medium` unless the runtime code visibly imports it.
* Scan everything in the component folder like any other code; skip only what cannot be imported (`.git`, `.github`,
  `__pycache__`).

## Decision Outcome

Chosen option: scan everything (the maintainer, 2026-11-02).

Home Assistant installs the component folder, and any module in it can be imported. Capping findings in test code
would be bypassed by a dynamic import, which the cap cannot see. A repository pre-check of an integration scans
`custom_components/<domain>`, so a test suite at repository level stays outside, as before; a frontend repository
without that folder is scanned as a whole, test folders included, which can only cause a notification (pre-checks
never quarantine). The AI prompt
now says that test files can be imported and are judged like the rest; scaffolding that the runtime code never
imports is not a risk by itself.

### Consequences

* Good, because a name no longer hides code from the scan, and the AI sees the code that is installed.
* Good, because the rule is simple: what is installed is scanned.
* Bad, because a component that ships its test suite inside its folder can produce findings from tests; for a known
  component that means a notification, for a new one possibly a quarantine, which the allowlist
  ([ADR-0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md)) resolves.
* Bad, because components with such files get a new content hash with this version and are scanned once more after
  the update.

### Confirmation

`TestIterFilesExclusion` in `marketplace_guard/tests/test_marketplace_guard.py`: test folders and files are scanned, a component
named like a test folder is scanned, and a payload imported from `tests/` gives the same verdict as from `helpers/`.
