---
status: proposed
date: 2026-11-20
decision-makers: maintainer
---

# The gate is published as its own repository for the Marketplace catalog

Complements [ADR-0042](0042-an-optional-gate-checks-marketplace-installs-before-they-load.md) (the gate) and
[ADR-0013](0013-publish-as-a-new-repository-with-one-start-commit.md) (publishing), which stay as they are.

## Context and Problem Statement

Marketplace Guard is to be listed in Home Assistant's Marketplace, so that people who install from it find it. Read on
2026-11-20 in the Marketplace's contributor documentation (contributors.home-assistant.io/marketplace: "How it works",
the catalog, integration, release and validation guides, the `hacs.json` and repository structure references), the
pinned announcement hacs/integration#5590 and the pull request template of hacs/default:

* The Marketplace installs four types: integrations, dashboard cards (`plugin`), themes and templates. It **refuses
  repositories with apps for Home Assistant OS**; those are added under Settings → Apps instead. A repository holds
  **one item of one type**: one integration, in `custom_components/<domain>/`.
* The catalog is still hacs/default. Its owner, or a major contributor, adds `owner/repository` to the file of its type
  (`integration`) in a pull request from a personal account and fills in the template: links to the current release, to
  a passing run of the HACS action without `ignore` and, for an integration, to a passing run of hassfest. The review
  takes months. Until then the repository can be added as a custom repository; the My Home Assistant link
  `marketplace_repository` offers that when the Marketplace does not know it yet.
* An integration repository needs: `hacs.json` with `name` (and `homeassistant` for the minimum version), a README, an
  OSI license, a description, topics, issues, at least one full GitHub release whose tag is the manifest's version, and
  a manifest with `domain`, `name`, `documentation`, `issue_tracker`, `codeowners` and `version`, its keys sorted
  (`domain`, `name`, then alphabetically). Since Home Assistant 2026.3 a custom integration brings its icon in
  `brand/icon.png` (256 × 256) in its own folder. The manifest documentation says not to list `homeassistant` or
  `persistent_notification` in `dependencies`, which Home Assistant sets up itself; hassfest accepted them in a local
  run on 2026-11-20, so that is a rule of the documentation, not of the tool.
* Not accepted: integrations that override or test a core integration. Removed: what breaks Home Assistant.

The public repository of Marketplace Guard is an app repository (`repository.yaml`, `marketplace_guard/config.yaml`),
so the Marketplace refuses it as a whole. Its one part that is a Marketplace type is the gate integration
`marketplace_guard_gate`, which the app carries in its image and copies into `custom_components` when the option
`marketplace_gate` is on (ADR-0042). A gate installed from a catalog without the app would make every Marketplace
install wait two minutes and then refuse it.

## Decision Drivers

* Be findable where people install community content, without giving up what keeps the scanners out of Home
  Assistant's reach ([ADR-0033](0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md),
  [ADR-0034](0034-hash-locked-scanners-and-no-execution-from-scanned-folders.md)).
* Meet the catalog's rules as written, checked by tools here instead of found out in a review months later.
* A gate installed on its own must not harm: it checks that the app is there before it sets up.
* The app and the Marketplace must not fight over the same folder.
* One development repository, site-neutral ([ADR-0011](0011-the-repository-is-site-neutral.md)), published only by
  `tools/publish.py`.

## Considered Options

* Submit the app's public repository. The Marketplace refuses repositories with apps.
* Add `hacs.json` and `custom_components/` to the app's public repository. Still a repository with an app, and then
  two items in one repository.
* Turn Marketplace Guard into an integration. The scanners would run inside Home Assistant, against ADR-0033 and
  ADR-0034, and the quarantine could be undone by what it guards against.
* Keep the gate in the app only. Nothing of Marketplace Guard appears in the Marketplace.
* Develop the gate in a second development repository. Its code and tests would drift from the app's, which answers its
  requests.
* Publish the gate from this repository as a second public repository, `<account>/marketplace-guard-gate`, built for
  the catalog.

## Decision Outcome

Chosen option: publish the gate as its own repository (the last option), and submit that repository to the catalog.

* `tools/publish.py` publishes both public repositories from the same commit, one commit and tag `v<version>` each
  (ADR-0013), and checks both before it pushes either. The gate repository holds
  `custom_components/marketplace_guard_gate/` (the folder from `marketplace_guard/gate/`), and from
  `gate_repository/` in this repository its `README.md`, `hacs.json` and the workflow that runs the HACS action and
  hassfest; `LICENSE` is the same. `--create` creates it with a description and topics. The gate keeps the app's
  version (ADR-0042), so each release publishes both.
* The gate's manifest gets the keys the catalog needs. `documentation`, `issue_tracker` and `codeowners` name the
  publishing account, so they hold the placeholder `OWNER` here and `tools/publish.py` fills them in, in both published
  copies. `persistent_notification` leaves `dependencies`. The icon is `brand/icon.png` in the gate's folder.
* `tools/check.py` checks what the catalog and hassfest check and can be checked here: the manifest's keys and their
  order, the dependencies, the icon, `hacs.json`, and the files the gate repository is built from.
* The app reports itself to the gate as a fact: at its start and at every heartbeat it writes
  `marketplace_guard/gate/app.json` in Home Assistant's configuration folder (its version, the request protocol `1`,
  its heartbeat, the time). The gate's setup reads it first and stops with the next step when the app never reported
  itself here, last reported longer ago than two heartbeats and two minutes, or speaks another protocol. A gate that
  is already set up keeps refusing without an answer as before (ADR-0042); this check guards the setup only.
* When the Marketplace's records name the gate's domain, the app leaves `custom_components/marketplace_guard_gate`
  alone, with or without its option: the Marketplace installed it and keeps it current. The status sensor's
  `marketplace_gate` asks Home Assistant whenever the gate's folder is there, not only with the option.
* The maintainer submits the gate repository to hacs/default by hand once the workflow passes on a release
  (`PUBLISHING.md`). Neither the tool nor a coding agent opens that pull request.

### Consequences

* Good, because Marketplace users find the gate, and its README leads them to the app first.
* Good, because a gate from the Marketplace is installed, updated and removed by the Marketplace like any other
  integration, and its updates pass the gate that runs.
* Good, because a gate installed without the app stops at its setup and says what is missing, instead of refusing
  every install.
* Bad, because every release publishes two repositories, and a Marketplace user is offered a gate update, with the
  restart it needs, at each release of the app, also when the gate's code did not change.
* Bad, because the gate wraps a method of a core integration; the catalog's reviewers may refuse that, and the review
  takes months. Until then the gate can be added as a custom repository with its Marketplace link.
* Bad, because `app.json` is a convenience, not a security boundary: code running in Home Assistant can write it, as it
  can do anything else there (ADR-0042).

### Confirmation

`tools/test_publish.py`: the gate repository holds exactly the gate, its repository files and the license, with the
account filled in and the markers replaced, and no app file; both repositories are released from the same commit; a
missing placeholder refuses. `tools/test_check.py`: the gate-repository check passes the files as they are and names
each catalog rule a changed file breaks. `marketplace_guard/tests/test_gate.py`: the app's report is read as a fact
(present, missing, stale, another protocol, unreadable). `TestMarketplaceGate` in
`marketplace_guard/tests/test_marketplace_guard.py`: the app writes its report at the start and at the heartbeat; a
gate the Marketplace's records name is never replaced; the sensor asks for a gate folder without the option. hassfest
passes on the built gate repository (locally with its container image on 2026-11-20: one integration, none invalid;
the same run refuses a broken `iot_class`), then in the gate repository's workflow, and the HACS action passes there
before the submission.

Proposed on 2026-11-20.
