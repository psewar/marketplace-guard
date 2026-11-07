---
status: accepted
date: 2026-11-07
decision-makers: maintainer
---

# Docstrings are read as text unless the code reads them

Extends [ADR-0026](0026-python-is-read-the-way-python-reads-it.md).

Redacted on 2026-11-07: details of the development installation were removed from the context; the decision is
unchanged ([ADR-0011](0011-the-repository-is-site-neutral.md)).

## Context and Problem Statement

The line heuristics skip lines that hold nothing but a comment
([ADR-0026](0026-python-is-read-the-way-python-reads-it.md)); every other line is matched against the rules,
docstrings included. Docstrings describe what code does in the very words the rules look for. An integration that
installs a package at run time can be rated `high` only for its docstrings: every `runtime-fetch-exec` hit is a
sentence such as "or a runtime pip install at start-up", while the call that does install the package is not matched
by that rule at all. An AI review handed such findings can call the component malicious. A `high` verdict that rests
on prose teaches the operator to ignore the verdict.

A statement that is nothing but string literals is never run: Python evaluates it to nothing, and in docstring
position it becomes `__doc__`. Code can read `__doc__` and hand it to `exec`; then the docstring is code.

## Decision Drivers

* What is never run is not a finding: the reason ADR-0006 and ADR-0026 give for comments.
* Python's tokenizer decides what a statement is, not a guess.
* A component must not gain a place to keep code that is scanned nowhere.

## Considered Options

* Keep scanning docstrings as code.
* Skip statements made of nothing but plain string literals, found with the tokenizer; scan them as code in every
  file of the component when any Python file of it mentions reading docstrings (`__doc__`, `getdoc`,
  `get_docstring`).
* Find docstrings with the `ast` module.

## Decision Outcome

Chosen option: the second option.

* `python_text_lines()` returns, from one tokenizer pass, the comment-only lines and the lines of statements whose
  tokens are all plain string literals. An f-string (or t-string) is not plain: its braces run code. A statement with
  any other token, such as `"""…"""; os.system(…)` or `"x" + …`, is code.
* `scan_python_file()` skips those lines for the line rules, as it skips comments, unless the file mentions
  `__doc__`, `getdoc` or `get_docstring` anywhere, comments and docstrings included. `scan_component()` checks every
  Python file of the component first: one file can run another file's docstring (`exec(other.__doc__)`), so a
  mention in any file makes every file's docstrings code. Each file with a mention gets an `info` finding
  `docstring-read`.
* Unchanged: the decode-and-execute rule, raw-IP URLs, outbound hosts and the Unicode checks look at the whole text,
  and bandit analyses the code itself.

The first option keeps the false `high` verdicts. The third would add a second reader beside the tokenizer, and
`ast` needs deep recursion on deeply nested hostile input.

### Consequences

* Good, because docstrings no longer raise a verdict: the integration above is `medium` (raw-IP URLs to its own
  loopback address) instead of `high`.
* Good, because a payload in a docstring is still found whenever the component names a way to read docstrings.
* Bad, because a component can read a docstring without naming it (`getattr(m, "__d" + "oc__")`) and run it. Running
  it still takes `exec`, `eval`, `compile` or writing and importing a file: `exec` and `eval` on a code line stay a
  `medium` finding, and decode-and-execute stays `high`. A payload kept in an ordinary string and reversed or joined
  before `exec` was never caught by the line rules either; this option opens nothing that such obfuscation had not
  opened already.
* Bad, because a component that mentions `__doc__` for a harmless reason keeps the old reading of its docstrings.

### Confirmation

`TestDocstrings` in `marketplace_guard/tests/test_marketplace_guard.py`: module, class and function docstrings and a string
standing alone stay quiet although they name patterns; an f-string statement, a string with code in its statement and
a string in an assignment are found; a docstring payload is found when the same file or another file of the component
reads docstrings, together with the `docstring-read` finding. Without the change the quiet cases fail.

Accepted by the maintainer on 2026-11-07; implemented in pull request #33.
