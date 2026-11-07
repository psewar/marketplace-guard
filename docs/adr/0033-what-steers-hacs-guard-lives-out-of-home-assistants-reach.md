---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# What steers HACS Guard lives out of Home Assistant's reach

Supersedes [ADR-0004](0004-operator-guidance-for-the-ai-in-a-file-read-on-every-scan.md) (the place of the file) and
[ADR-0009](0009-override-code-folder-takes-precedence-over-the-built-in-code.md).

## Context and Problem Statement

Two files steer HACS Guard: `ai_prompt.txt`, whose lines are appended to the AI prompt as the operator's instructions
("prioritise these", ADR-0004), and the override folder, whose `guard.py` and `scanner.py` run instead of the code in
the image (ADR-0009). Both lived in `/homeassistant/hacs_guard/`, the Home Assistant configuration folder. Every
custom integration runs inside Home Assistant Core with full access to that folder. A component that got in — part of
the baseline, allowlisted, a known component whose update was only reported, or one the Marketplace set up before the
scan ([ADR-0024](0024-home-assistants-marketplace-replaces-hacs.md)) — could therefore write its own `guard.py` and
switch the guard off from the next add-on start, with the add-on's Supervisor token, or tell the AI to answer
"clean". Nothing showed which code ran, apart from one log line.

The Supervisor mounts the configuration folder, `ssl`, `share` and `media` into the Home Assistant Core container,
but not the add-on configuration folders (`addon_configs`); an add-on gets its own with the `addon_config` map, at
`/config` inside the add-on. The operator reaches it through the Samba, File editor or SSH add-ons.

## Decision Drivers

* Nothing that runs inside Home Assistant Core can change what HACS Guard runs or what it tells the AI.
* The operator keeps both: guidance for the AI, read on every scan, and an override for trying code.
* Which code runs is a fact anyone can see, not something to infer.

## Considered Options

* Keep both in `/homeassistant/hacs_guard/` and check them (a signature, an allowlist of hashes).
* Move both to the add-on's configuration folder; ignore the old places and say so.
* Drop the override and the instructions file.

## Decision Outcome

Chosen option: the second option.

* `config.yaml` maps `addon_config:rw`. `run.sh` runs `/config/code/guard.py` when `guard.py` and `scanner.py` are
  there, logs that as an override with the start of their SHA-256, and runs the built-in code otherwise. A
  `guard.py` in `/homeassistant/hacs_guard/code/` is ignored with a warning in the log and a notification.
* `ai_prompt.txt` is read from `/config/ai_prompt.txt`, on every scan as before; lines starting with `#` are ignored.
  An old `/homeassistant/hacs_guard/ai_prompt.txt` that holds instructions is not read and not copied (Home Assistant
  could have written it); a notification asks the operator to move them.
* The log and the status sensor carry `code_source` (`built-in` or `override`) and `code_sha256`.
* The request file and the reports stay in `/homeassistant/hacs_guard/`: the request file only asks for pre-checks,
  which cannot quarantine or exempt anything.

The first option was not chosen because whatever checks the override would be code that the override replaces. The
third was not chosen because both are needed: the instructions tune the AI for an installation, and the override is
how a change is tried on a running instance.

### Consequences

* Good, because a component running in Home Assistant can no longer replace the guard or speak to the AI as the
  operator.
* Good, because the running code is visible as a fact.
* Bad, because operators who wrote instructions have to move them once; the notification says where.
* Bad, because the files are reached through Samba, the File editor or SSH instead of the configuration folder.

### Confirmation

`TestSteeringFilesOutOfReach` in `marketplace_guard/tests/test_marketplace_guard.py`: the instructions come only from the add-on's
configuration folder, an old file with instructions or an old code folder is named in a notice, and the code source
and hash are reported. `run.sh` was started in the amd64 add-on image under its init with the built-in code, with an
override in `/config/code` and with an old override folder: it ran the expected code each time, and the hash it logs
equals `code_sha256`. The `addon_config` map itself needs the Supervisor and is not covered by a test.

Accepted by the maintainer on 2026-11-06; implemented in pull request #28.
