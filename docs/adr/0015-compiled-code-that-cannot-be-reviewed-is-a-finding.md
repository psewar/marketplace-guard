---
status: accepted
date: 2026-11-02
decision-makers: maintainer
---

# Compiled code that cannot be reviewed is a finding

## Context and Problem Statement

The scanner reads source code (`.py`, `.js`). Python also imports compiled code, and a component can ship it. A
probe with Python 3.12 on 2026-11-02 showed what the import system loads from a component folder:

| Case | Loaded |
|---|---|
| `mod.pyc` beside the code, no `mod.py` | the bytecode |
| `__pycache__/mod.<tag>.pyc` marked "unchecked hash", `mod.py` with other content | the bytecode, not the visible source |
| `__pycache__` bytecode with a timestamp that does not match `mod.py` | the source |
| `__pycache__` bytecode without any `mod.py` | nothing (not importable) |

Native extension modules (`.so`, `.pyd`) are loaded by Python before a `.py` of the same name (documented import
order; not measured). None of this was looked at: the first two cases let a component run code the scanner never
saw, or saw a harmless decoy for. [ADR-0014](0014-everything-in-a-component-folder-is-scanned-test-code-included.md)
skips `__pycache__` as source; the bytecode in it was not considered.

## Decision Drivers

* No code may run that the scan could not look at.
* Bytecode that Home Assistant writes itself on every start must not cause findings or rescans.

## Considered Options

* Ignore compiled code.
* Decompile bytecode and scan the result.
* Report compiled code that Python would import in place of reviewable source as a `high` finding.

## Decision Outcome

Chosen option: the third option.

`scanner.compiled_code()` lists native extension modules, `.pyc` files beside the code without a `.py` of the same
name, and `__pycache__` bytecode whose header (PEP 552) says "hash-based, do not check the source". Each is a `high`
finding (`native-module`, `sourceless-bytecode`, `unchecked-bytecode`). Timestamp and checked-hash bytecode in
`__pycache__` is the cache Python writes and validates itself; it is neither a finding nor part of the content hash,
so Home Assistant's own cache writes do not trigger rescans. The listed files are part of the content hash, so
dropping one in triggers a scan.

Decompiling was not chosen: decompilers lag behind new Python versions and cannot be trusted with hostile input; code
that cannot be reviewed as shipped is the finding.

### Consequences

* Good, because neither a sourceless module nor a bytecode decoy can run past the scan.
* Bad, because a legitimate component that bundles a native library is quarantined when new; the allowlist
  ([ADR-0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md)) resolves it.
* Bad, because bytecode with a forged timestamp that happens to match the installed `.py` would still be loaded
  instead of the source; the installed file's modification time is set at download, which makes this impractical.

### Confirmation

`TestCompiledCode` in `marketplace_guard/tests/test_marketplace_guard.py` builds each case with `py_compile` and checks the list,
the verdict and that a Python-written cache leaves the content hash unchanged.

Accepted with the merge of pull request #3 on 2026-11-02.
