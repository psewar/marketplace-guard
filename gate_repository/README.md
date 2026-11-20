# Marketplace Guard Gate

Stops risky integrations and dashboard cards from Home Assistant's Marketplace **before they can load**. When the
Marketplace has written what you install or update, the gate asks the **Marketplace Guard** app to scan it. What the
app would quarantine is not installed: the Marketplace puts back what was there, its install dialog says why, and the
code never runs.

The gate scans nothing itself. It needs the Marketplace Guard app (Home Assistant OS or Supervised), which runs the
scanners in its own container, out of Home Assistant's reach, and also watches components installed in other ways.
Without the app, the gate does not set up.

Requires Home Assistant 2026.11 or later (the first version with the Marketplace).

## Install

### 1. The app

Add the app repository, install **Marketplace Guard** and start it:

[![Add the repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fpsewar%2Fmarketplace-guard)

Repository URL: `https://github.com/psewar/marketplace-guard`

### 2. The gate

Install **Marketplace Guard Gate** from the Marketplace:

[![Open the gate in the Marketplace of your Home Assistant](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=psewar&repository=marketplace-guard-gate&category=integration)

Repository URL: `https://github.com/psewar/marketplace-guard-gate`

### 3. Set it up

Its setup opens right after the install (or Settings → Devices & services → Add integration → *Marketplace Guard
Gate*). The setup first checks that the app answers in this Home Assistant; if not, it says what is missing.

Instead of steps 2 and 3, the app can put the gate in place itself: turn on its option *Check Marketplace installs
before they load*. Use one way, not both: a gate installed from the Marketplace is updated by the Marketplace, and the
app leaves it alone.

## What it does

* It checks integrations and dashboard cards, new installs and updates alike; themes and templates are not code and
  pass unchecked.
* The decision is the one a quarantine would make, with the app's thresholds and allowlist. An update is refused when
  it brings a new risk (the app's default).
* The install dialog waits for the scan, which takes a few seconds.
* The app's AI second opinion, if you turned it on, follows after the install.

## Options

Settings → Devices & services → Marketplace Guard Gate → Configure:

* **When Marketplace Guard does not answer:** refuse the install (default: nothing is installed while the app is
  stopped) or allow it unchecked.
* **Wait for an answer:** 120 seconds by default.

## Limits

The Marketplace has no public hook for this yet. The gate wraps the method the Marketplace uses to check written
content, so a Home Assistant update can change what it relies on. It then does not start, says so in a notification,
and the app's status sensor shows `not set up`; until the gate is updated, pre-check repositories with the app before
you install them.

Each release of the app releases the gate with the same version. Home Assistant loads a new version of the gate at
its next restart; until then, the version before keeps checking.

## Remove

Delete the integration Marketplace Guard Gate (Settings → Devices & services), remove it in the Marketplace, and
restart Home Assistant.

## More

The app's documentation (its **Documentation** tab in Home Assistant, in English and German) describes the gate, the
pre-check of repositories, the quarantine and every option. This repository is published from the app's development
repository with each release.

Security problems in the gate or the app: please report them privately to the maintainer, not in a public issue.
