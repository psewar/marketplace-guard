---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Python is read the way Python reads it

Supersedes [ADR-0006](0006-comment-lines-are-not-scanned.md).

## Context and Problem Statement

The line heuristics skipped every line whose first non-blank characters were `#` or `//`, in Python and JavaScript
alike ([ADR-0006](0006-comment-lines-are-not-scanned.md)), and read every file as UTF-8. Three kinds of valid Python
hid shell execution from them; each was reproduced and compiles:

* A continued expression line that starts with Python's floor division operator: `r = (1` followed by the line
  `//os.system("…"))`. The line starts with `//` and was skipped as a comment.
* A line that starts with `#` inside a string and then closes it: after `s = """`, the line `#"""; os.system("…")`.
* A PEP 263 cookie `# coding: utf-7` with the code written in UTF-7's `+…-` form. Python decodes it and runs
  `os.system`; the scanner read the bytes as UTF-8 and found nothing at all.

Bandit was meant to catch what the heuristics miss, but it reads its configuration from the code it scans: it honours
`# nosec` on a line, it picks up a `.bandit` ini file found below the scanned folder (which can skip tests), and with
two `.bandit` files it stops without a report — which `run_bandit()` took as "no findings".

## Decision Drivers

* Comments are still not findings: ADR-0006's reason (deny lists name the patterns they block) stands.
* What is a comment, and how the bytes are decoded, is decided the way Python decides it, not by a guess.
* Nothing the scanned component contains may configure or switch off a check
  ([ADR-0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md)).
* A tool that did not analyse the code says so; a missing report is not a clean one.

## Considered Options

* Keep ADR-0006's line rule and add special cases for the three forms.
* Use Python's own tokenizer and encoding detection for Python files, keep the `//` rule for JavaScript only, and run
  bandit with its own configuration.
* Scan Python with the `ast` module instead of line rules.

## Decision Outcome

Chosen option: the second option.

* `python_comment_lines()` takes the lines that hold only `COMMENT` tokens from `tokenize`; a line with any other token
  (a string that ends there, an operator) is code. When the text does not tokenize, no line is skipped.
* `python_source()` decodes the bytes with the codec `tokenize.detect_encoding()` finds, as Python does. A codec that
  does not read ASCII as ASCII (anything but UTF-8, ASCII, Latin-1, ISO 8859-15, cp1252) is a `high` finding
  `source-encoding`, and the decoded text is what the rules see; a codec Python cannot use is an `info` finding.
* JavaScript keeps skipping `//` lines only: `#` starts a private class field there.
* Bandit runs as `bandit -r -f json -q --ignore-nosec --ini <an ini file of its own>`, without the Supervisor token in
  its environment. `bandit_findings()` reads the outcome from the exit code and the JSON report: exit 0 or 1 with a
  `results` list is an analysis, anything else an `info` `tool-error`; files bandit could not parse are `info`
  `not-analysed`.

The first option was not chosen because each special case invites the next one. The third would be more precise for
calls, but it is a new analyser with its own gaps; the tokenizer fixes what the line rules got wrong without changing
what they look for.

### Consequences

* Good, because the three reproduced forms are found, and a component can no longer switch bandit off.
* Good, because comment-only lines, including deny lists, stay quiet as before.
* Bad, because a file that does not tokenize is scanned on every line, comments included (such a file cannot be
  imported either).
* Bad, because `# nosec` that a legitimate author added for a reviewed line no longer hides it; bandit's findings other
  than shell execution are `low` and do not change the verdict.

### Confirmation

`TestEvasion` and `TestBandit` in `marketplace_guard/tests/test_marketplace_guard.py`: the three forms compile and are found; a
Latin-1 cookie and comment lines stay quiet; a trailing comment does not hide code; a JavaScript private field is
scanned; bandit gets its own ini, `--ignore-nosec` and no token; a run without a report is a `tool-error`.

Accepted by the maintainer on 2026-11-06; implemented in pull request #24.
