---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Component text is shown as code in notifications

## Context and Problem Statement

Notifications name the reasons for a verdict: the messages of the top findings, the folder a component was moved to,
the notes of a pre-check and its errors. Many of those contain text from the scanned component: a requirement string
from its manifest, a host, a file or folder name, a release tag, the AI's reason. Home Assistant renders a persistent
notification as Markdown. A requirement `[Mark as safe - restore](https://phish.example/restore)` in a hostile
manifest appeared as a clickable link in HACS Guard's own warning — the place an operator trusts most.

## Decision Drivers

* A warning about a component must not carry the component's links or formatting.
* The operator still sees the text exactly as written, to judge it.
* One rule for every place that shows component text, instead of escaping per finding type.

## Considered Options

* Escape Markdown characters with backslashes.
* Show component text as a Markdown code span: newlines and backticks replaced, the whole text between backticks.

## Decision Outcome

Chosen option: the second option. `md_code()` turns component text into a code span; `short()` uses it for each finding's
message, and the quarantine, failure and pre-check notifications for the folder, the error and the notes.

The first option was not chosen because bare URLs are turned into links by the renderer without any Markdown syntax,
and which characters need escaping depends on the renderer.

### Consequences

* Good, because nothing a component writes becomes a link, an image or formatting in a notification.
* Bad, because notify services that show plain text (push messages) show the backticks.

### Confirmation

`TestShort` in `marketplace_guard/tests/test_marketplace_guard.py`: a requirement with link and image syntax, backticks and a
newline ends up as one code span in the notification text.

Accepted by the maintainer on 2026-11-06; implemented in pull request #27.
