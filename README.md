# Marketplace Guard

A Home Assistant app (add-on) that checks custom components from Home Assistant's Marketplace, HACS or installed by
hand for security problems: new or changed components are scanned and, if risky, moved to a quarantine folder before
Home Assistant loads them; repositories can be checked before you install them; an AI Task of your choice can add a
second opinion. Until version 2.0.0 it was called *HACS Guard*.

## Install

Add this repository to your Home Assistant (Home Assistant OS or Supervised), then install **Marketplace Guard** and
start it:

[![Add the repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpsewar%2Fmarketplace-guard)

Repository URL: `https://github.com/psewar/marketplace-guard`

By hand: Settings → Apps → **Install app** → ⋮ → **Repositories**, add the repository URL, then install
**Marketplace Guard** from the list. The defaults work without changes: alerts appear as notifications in Home
Assistant, and everything installed before the first start is recorded as trusted.

## Learn more

- Getting started, everyday use and all options: [marketplace_guard/DOCS.md](marketplace_guard/DOCS.md) (English and
  German; Home Assistant shows it on the app's **Documentation** tab)
- Changes: [marketplace_guard/CHANGELOG.md](marketplace_guard/CHANGELOG.md)
- Why it is built this way: [docs/adr/](docs/adr/README.md)
- Contributing: [AGENTS.md](AGENTS.md) (workflow, tests, what a change brings along)

Security problems in Marketplace Guard itself: please report them privately to the maintainer, not in a public issue.
