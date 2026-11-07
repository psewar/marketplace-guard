# Marketplace Guard

A Home Assistant add-on that scans HACS, Home Assistant's Marketplace and `custom_components` for security problems:
new or changed components are scanned and, if risky, moved to a quarantine folder; repositories can be checked before
you install them; an AI Task of your choice can add a second opinion. Until version 2.0.0 it was called
*HACS Guard*.

- What it does and how to use it: [marketplace_guard/DOCS.md](marketplace_guard/DOCS.md) (English and German)
- Install: Settings → Add-ons → Add-on Store → ⋮ → **Repositories**, add the URL of this repository, then
  install **Marketplace Guard**. The defaults work without changes.
- Changes: [marketplace_guard/CHANGELOG.md](marketplace_guard/CHANGELOG.md)
- Why it is built this way: [docs/adr/](docs/adr/README.md)
- Contributing: [AGENTS.md](AGENTS.md) (workflow, tests, what a change brings along)

Security problems in Marketplace Guard itself: please report them privately to the maintainer, not in a public issue.
