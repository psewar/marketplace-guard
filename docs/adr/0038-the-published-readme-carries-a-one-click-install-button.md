---
status: accepted
date: 2026-11-09
decision-makers: maintainer
---

# The published README carries a one-click install button

## Context and Problem Statement

Installing Marketplace Guard starts with adding its repository to Home Assistant: Settings → Apps → Install app → ⋮ →
Repositories, then typing or pasting the repository URL. The README could not name that URL: it contains the
publishing account, which this repository must not carry
([ADR-0011](0011-the-repository-is-site-neutral.md)); only the published copy does
([ADR-0013](0013-publish-as-a-new-repository-with-one-start-commit.md), `url` and `maintainer` in `repository.yaml`,
`url` in the app's `config.yaml`). So the README said "add the URL of this repository", and a reader had to work out
which URL that is. Home Assistant offers a link through My Home Assistant
(`https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=…`) that opens the dialog with
the URL filled in, in the reader's own Home Assistant.

## Decision Drivers

* The first step of installing should be one click, or one copy of a URL that is printed, not one to find out.
* This repository stays site-neutral; the account name reaches the published copy only.
* A link that cannot be filled in must not be published broken.

## Considered Options

* Keep the generic text "add the URL of this repository".
* Write the public URL and the button into the README of this repository.
* A marker line in the README that `tools/publish.py` replaces by the button and the URL in the published copy.

## Decision Outcome

Chosen option: the third option.

* `README.md` holds the line `<!-- publish: install -->`; an HTML comment, invisible where the README is shown here.
* `tools/publish.py` replaces it by the My Home Assistant button (badge and redirect with the URL-encoded repository
  URL) and the line "Repository URL: `https://github.com/<account>/marketplace-guard`", with the same account it writes
  into `repository.yaml`.
* It refuses to publish when `README.md` has no marker line, and when a marker line is left in any other file of the
  published tree. Only a line that is the marker and nothing else counts, so code and documents may name it.
* The README also describes the manual path (Settings → Apps → Install app → ⋮ → Repositories).

The first option leaves the reader to find the URL. The second puts the account into this repository.

This extends the list of places in ADR-0013 where the account is written; the rest of ADR-0013 is unchanged.

### Consequences

* Good, because adding the repository is one click from the published README, and the URL is printed for adding it by
  hand.
* Good, because this repository keeps no account name, and a missing or stray marker stops the publication.
* Bad, because the README seen in this repository shows no button; its manual path is the same text.
* Bad, because the button depends on the My Home Assistant service and on its redirect name
  (`supervisor_add_addon_repository`), which still says "add-on" after Home Assistant renamed add-ons to apps.

### Confirmation

`tools/test_publish.py`: the published README holds the button with the URL-encoded repository URL and the printed URL
instead of the marker, and the README of the development repository keeps the marker; a README without the marker
refuses; a marker line left in another file refuses; a marker named inside a line is not one.

Accepted by the maintainer on 2026-11-09; implemented in pull request #41.
