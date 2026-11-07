---
status: accepted
date: 2026-11-02
decision-makers: maintainer
---

# Publish as a new repository with one start commit

Redacted on 2026-11-07: details of the development installation were removed from the context; the decision is
unchanged ([ADR-0011](0011-the-repository-is-site-neutral.md)).

## Context and Problem Statement

The maintainer considers publishing HACS Guard as open source. The development repository's history contains
details of the development installation that were removed later
([ADR-0011](0011-the-repository-is-site-neutral.md)): entity and device names. Commit
metadata also carries the time zone of the development machine. Whatever is in a public history stays readable.

## Decision Drivers

* Nothing removed from the tree may be readable in the public history.
* The development repository keeps its history, reviews and branch protection.
* Publishing is one repeatable step, not a manual cleanup.

## Considered Options

* Publish the development repository with its history.
* Rewrite the history of the development repository (filter out the details) and publish it.
* Publish a new repository that starts with one commit of the current, checked tree.

## Decision Outcome

Chosen option: a new repository with one start commit, made from the tree of `main` after `tools/check_neutral.py`
passed, with a neutral commit date in UTC.

Publishing the history as it is was rejected because it contains the details. Rewriting the history was rejected
because it changes every commit of the development repository and still leaves the old commits in clones and pull
request records.

The points left open when this was proposed, decided by the maintainer on 2026-11-07:

* **Where:** a public GitHub repository `marketplace-guard` under the maintainer's account (the add-on's name since
  [ADR-0036](0036-the-add-on-is-renamed-to-marketplace-guard.md)). The account name is written into the published
  copy only (`url` and `maintainer` in `repository.yaml`, `url` in the add-on's `config.yaml`); this repository keeps
  placeholders and stays site-neutral ([ADR-0011](0011-the-repository-is-site-neutral.md)).
* **License:** MIT, in `LICENSE`, held by "The Marketplace Guard contributors".
* **Development** continues in this repository, with its reviews and branch protection. Each release is copied over
  as one commit by `tools/publish.py`: it refuses unless the checkout is clean at `main`, `tools/check.py --all`
  passes, the version is not yet published and the newest public commit is its own; then it commits the tree with the
  publishing account as author and the day at 00:00 UTC as date, tags `v<version>` and pushes. Nothing is pushed to
  the public repository by hand.

### Consequences

* Good, because the public history starts clean.
* Bad, because the public repository does not show how the add-on came to be; the ADRs carry the reasons instead.
* Bad, because the publishing account is visible as the owner of the repository; that is unavoidable for a public
  repository.

### Confirmation

`tools/publish.py` makes every public commit and checks its preconditions itself; `tools/test_publish.py` covers its
refusals (unclean checkout, HEAD not at the ref, no release number, a published version, a commit made by hand in the
public repository) and that a start commit carries the tree without any object of the development history.
`PUBLISHING.md` lists the steps.

Accepted by the maintainer on 2026-11-07; implemented in pull request #37.
