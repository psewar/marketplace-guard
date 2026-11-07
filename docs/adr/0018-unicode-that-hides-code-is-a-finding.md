---
status: accepted
date: 2026-11-05
decision-makers: maintainer
---

# Unicode that hides code is a finding

## Context and Problem Statement

Trojan Source (CVE-2021-42574) uses Unicode bidirectional control characters to make source code display in another
order than the compiler or interpreter reads it: a comment that seems to end a line actually continues it, a string
that seems to close does not. A reviewer, and an AI review reading the same text, sees harmless code. Invisible
characters (zero width space, non-joiner, joiner, word joiner, a byte order mark inside a file) make a name, a string
or a host differ from what it looks like. HACS Guard did not look for either. Its line heuristics skip comment lines
([ADR-0006](0006-comment-lines-are-not-scanned.md)), and a comment is exactly where Trojan Source places its
reordering.

## Decision Drivers

* Code that reads differently than it runs defeats every human and AI review, so it must not pass unnoticed.
* Legitimate uses must not become findings: emoji sequences use the zero width joiner, Persian and Indic text the
  non-joiner, translations are JSON files, and minified JavaScript carries such characters in locale data.
* The repository's own sources must stay free of the characters, so the scanner can scan itself.

## Considered Options

* Leave it to bandit and the AI review.
* One rule for all hidden characters: `high` wherever they appear.
* Bidirectional controls `high` everywhere, comments included; invisible characters judged by file type and context.

## Decision Outcome

Chosen option: the third option. `scanner.unicode_findings()` checks every `.py`, `.js` and `.json` file of a component
(JSON when the Python or the JavaScript scan is on):

* **Bidirectional controls** U+202A–U+202E and U+2066–U+2069 are `high` (`bidi-control`) in all three file types, on
  every line, comment lines included: here ADR-0006 does not apply, because the comment is the hiding place.
* **Invisible characters** U+200B–U+200D, U+2060, and U+FEFF anywhere but as the first character of a file
  (`invisible-char`), when a neighbouring character is ASCII, where identifiers, keywords, hosts and paths are:
  * `medium` in Python. Python refuses them outside strings and comments, so they cannot make a hidden name, but in a
    string they make a value differ from what is shown: a comparison that never matches, a host that is not the one
    read. That needs a look (notification), not a quarantine.
  * `info` in JavaScript. ECMAScript allows the joiners inside names, so look-alike names are possible, but bundles
    carry these characters legitimately (locale data, text and emoji handling), like the other JavaScript heuristics,
    which are informational for minified code.
  * not checked in JSON: translations need the non-joiner and the joiner.
  * comment lines are skipped as in the other heuristics: an invisible character there changes nothing that runs.
  * Between two non-ASCII characters (inside an emoji sequence, a Persian word) they are not a finding.
* The add-on writes these characters only as escapes; a test checks that its own `.py`, `.js` and `.json` files hold
  none.

The first option was not chosen because bandit has no rule for it and the AI review receives the same misleading
text. The second was not chosen because it would quarantine new components for an emoji or a Persian translation.

A local sample of third-party packages (35,288 Python, 19,195 JavaScript and 47,836 JSON files from the dependencies
of other projects; no Home Assistant components) gave: no bidirectional control in any Python or JavaScript file, two
in JSON (tokenizer vocabularies of language models); one `medium` in Python (a byte order mark inside a docstring) and
20 `info` in JavaScript (locale data and bundles).

### Consequences

* Good, because a Trojan Source component is quarantined when new and reported loudly when known, whatever its
  comments hide.
* Good, because emoji, Persian and Indic text and byte order marks at the start of a file stay quiet.
* Bad, because a translation or minified bundle that uses bidirectional controls for right-to-left text is `high`;
  a new component with one is quarantined until the allowlist
  ([ADR-0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md)) or the operator lets it through.
  The sample above suggests this is rare.
* Bad, because components installed before the update are not scanned again by it: their content hash is unchanged.
  A hidden character in one of them shows when it changes, not at once.
* Bad, because an invisible character between two non-ASCII characters is not reported, and look-alike letters from
  other scripts (homoglyphs) are not in scope.

### Confirmation

`TestHiddenUnicode` in `marketplace_guard/tests/test_marketplace_guard.py` builds every character with `chr()`: Trojan Source on a
code line and in a comment, each control and its neighbours in the code chart, invisible characters by file type and
context, the byte order mark, a Persian translation and a manifest with a control, and the add-on's own files.

Accepted by the maintainer on 2026-11-07; implemented in pull request #8.
