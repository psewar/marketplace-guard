---
status: superseded by ADR-0033
date: 2026-06-08
decision-makers: maintainer
---

# Operator guidance for the AI in a file read on every scan

Superseded by [ADR-0033](0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md): the file is still read on
every scan, but from the add-on's configuration folder, which Home Assistant integrations cannot write.

Backfilled on 2026-11-02, decided on 2026-06-08. Sources: the maintainer's request of 2026-06-08 to give the AI Task more
detail on what to check, `marketplace_guard/DOCS.md`, the false-positive tuning of 2026-07-03 in the operator's file.

## Context and Problem Statement

The AI judges better when it knows the threat model and the operator's priorities. Those differ between installations
(cameras and locks, telemetry policy, known vendors) and change as false positives show up.

## Decision Drivers

* The operator can steer the AI without changing code or rebuilding the image.
* A change takes effect at once, without restarting the add-on.
* The built-in prompt stays generic.

## Considered Options

* Only the built-in prompt.
* An add-on option with the extra text.
* A text file next to the request file, read on every scan.

## Decision Outcome

Chosen option: the file `ai_prompt.txt` in the add-on's data folder (`/homeassistant/hacs_guard/`), read fresh on every
scan; lines starting with `#` are ignored and the rest is appended to the security prompt (the maintainer, 2026-06-08).

The built-in prompt explains the Home Assistant threat model and asks for evidence by file and line. An add-on option
was not chosen because the text is several paragraphs and changing an option restarts the add-on.

### Consequences

* Good, because tuning a false positive is an edit of one file and the next scan shows the effect. On 2026-07-03 rules
  for donation and social links, public data APIs and XML namespaces turned a false "suspicious" for a frontend card
  into "clean".
* Good, because site-specific knowledge (known vendors, local priorities) stays out of the code.
* Bad, because the file is not versioned with the add-on, and rules that prove generally useful have to be moved
  into the built-in prompt by hand (done for the rules of 2026-07-03 in version 1.4.0; since then the add-on
  creates the file with commented examples on its first start).

### Confirmation

`_operator_prompt()` in `guard.py` reads the file on each review.
