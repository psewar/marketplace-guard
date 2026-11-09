# Repository guidance

How Marketplace Guard is developed. This applies to every contributor, human or coding agent. This file is the single source;
tool-specific files such as `CLAUDE.md` only import it.

## Layout

The repository is a Home Assistant add-on repository: `repository.yaml` at the root, the add-on in
`marketplace_guard/`, the license in `LICENSE` (`PUBLISHING.md` says how releases are published and installed).
Inside the add-on:

- `guard.py` is the daemon (watcher, quarantine, repository pre-check, AI review, notifications, status sensor).
- `scanner.py` is the static scan (bandit, pip-audit, heuristics, HACS critical list).
- `tests/` holds the unit tests; `tests/fixtures/` holds sample components for manual scans
  (`python3 guard.py scan-path tests/fixtures/evil`).

Outside the add-on: `tools/check.py` runs the repository checks (its own tests are `tools/test_check.py`),
`tools/check_neutral.py` keeps the repository site-neutral (`tools/test_check_neutral.py`), `tools/publish.py` copies
a release to the public repository (`tools/test_publish.py`), `docs/adr/` holds the decisions.

## Workflow

- Work on a topic branch and open a pull request against `main`. One topic per pull request; nothing is pushed to
  `main` directly.
- The maintainer reviews and merges. Do not merge your own pull request.
- There is no CI yet. `python3 tools/check.py --all` is the gate: it must pass (exit 0) before you push.
- Commit subjects say what changes, in English, and name the ADR where there is one.
- The pull request description says what changes and why, names its ADRs and says how it was tested.
- Development happens here. A merged release reaches the public repository only through `python3 tools/publish.py`,
  run by the maintainer ([ADR-0013](docs/adr/0013-publish-as-a-new-repository-with-one-start-commit.md)); nothing is
  pushed or merged there by hand. The publishing account's name is written into the published copy only; the line
  `<!-- publish: install -->` in `README.md` becomes the install button there
  ([ADR-0038](docs/adr/0038-the-published-readme-carries-a-one-click-install-button.md)), so keep it.

## What a change brings along

A pull request is complete when it contains, as far as they apply:

- **Tests.** A behaviour change comes with tests in `marketplace_guard/tests/`; a bug fix with a test that fails without the
  fix. The scanner handles hostile input: a refusal is tested as well as the accepted case. Tests use the standard
  library only, so they run without Home Assistant.
- **Version.** `version` in `marketplace_guard/config.yaml`. The Supervisor offers an update only when it changes, so every
  change to the add-on's files raises it: patch for fixes and calibration, minor for new behaviour or options.
- **Changelog.** An entry in `marketplace_guard/CHANGELOG.md` under the new version.
- **Dependencies.** A scanner version is changed in `marketplace_guard/requirements.in`; then `marketplace_guard/requirements.txt`
  is regenerated with its hashes
  ([ADR-0034](docs/adr/0034-hash-locked-scanners-and-no-execution-from-scanned-folders.md)):
  `uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes --no-header -o requirements.txt`
  in `marketplace_guard/`. The image installs only that file, with `--require-hashes`.
- **Documentation.** `marketplace_guard/DOCS.md` has an English and a German part; both change together. `marketplace_guard/README.md`
  changes where the overview changes.
- **Configuration.** A new option goes into `options` and `schema` in `marketplace_guard/config.yaml`, into the defaults in
  `guard.py`, and gets a name and description in both `marketplace_guard/translations/en.yaml` and
  `marketplace_guard/translations/de.yaml`. An existing configuration keeps working without edits.
- **ADR** for every decision (see "Architecture decisions are recorded as ADRs").

## Running the checks

```bash
python3 tools/check.py --all                              # every check below, one exit code: the gate
python3 tools/check.py                                    # ADR index, Markdown links, add-on configuration only
cd marketplace_guard && python3 -m unittest discover -s tests   # unit tests, standard library only
python3 tools/check_neutral.py                            # site-neutral check of every tracked file
python3 tools/check_neutral.py --text <file>              # commit message or pull request text
```

`tools/check.py` checks that the ADR index in `docs/adr/README.md` lists every ADR with its title, status and date and
that the numbers have no gaps; that every relative link in `AGENTS.md`, `README.md`, `PUBLISHING.md`,
`marketplace_guard/*.md` and `docs/adr/*.md` resolves and every repository path named here exists; and that options, schema,
both translations and `DEFAULTS` in `guard.py` agree (see "What a change brings along"). With `--all` it also runs the
unit tests of the add-on and of the tools, and `tools/check_neutral.py`. Exit 0: everything ran and passed; 1: a check
found problems; 2: a check could not run, for example the configuration check without PyYAML, and the output says
the next step. Commit messages and pull request texts are not in the repository; check them with `--text`.

`tools/check_neutral.py` reads your own terms (host names, people, devices, places) from
`~/.config/marketplace-guard/site-terms.txt` or the file `$MARKETPLACE_GUARD_SITE_TERMS` names, outside the repository. Without
that list it refuses and says how to go on.

## Code in the image and the override folder

`run.sh` runs the code from `code/` in the add-on's configuration folder (`/config/code/` inside the add-on) when that
folder holds `guard.py` and `scanner.py`, and the code built into the image otherwise
([ADR-0033](docs/adr/0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md)); Home Assistant integrations
cannot write that folder. The log and the status sensor say which code runs (`code_source`, `code_sha256`). The
override is for trying a change on a running instance. A change tried there is not done until it is in this repository, released with a new
version and built into the image; afterwards the override folder is removed or updated to the same code.

## Language and names

- Code, identifiers, comments, log messages, notification texts, tests, commit messages, pull request texts and ADRs
  are English.
- `marketplace_guard/DOCS.md`, `marketplace_guard/README.md` and the translations are English and German. German
  follows the standard spelling (ß, not ss); a regional spelling is a place hint, and `tools/check_neutral.py` finds it.

## Public data

The repository is meant to be publishable and is site-neutral
([ADR-0011](docs/adr/0011-the-repository-is-site-neutral.md)): nothing in it may allow conclusions about the people,
the home or the infrastructure of whoever develops or runs it.

- No host names, addresses, domains, people's names, device or entity names of a real installation, places, or paths
  outside the add-on and the repository: not in code, comments, tests, examples, documentation, commit messages or
  pull request texts. The `decision-makers` field of an ADR names a role such as `maintainer`.
- What was seen or measured on a real installation is told without what identifies it: no integration, card, device
  type, vendor or service in use there, no count of its components or files, no quote from its components. A
  published component may be measured as such, never described as installed somewhere. Changelog entries and release
  notes are public too.
- The add-on presets nothing of a particular installation: options default to what every Home Assistant has, and
  what an installation offers is discovered at run time
  ([ADR-0012](docs/adr/0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md)).
- `tools/check_neutral.py` checks this before every push; it does not replace reading your added lines.
- Examples and tests use placeholders: `*.example`, `*.invalid`, `*.test`, `example.org`, and the documentation ranges
  `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`.

## Tools check their own preconditions

Scripts and commands take the caller's intent and do everything needed for it, including the checks. They verify
their preconditions before acting and refuse with the state and the next step instead of acting halfway. What can be
derived is derived instead of asked for. A rule that only lives in documentation is the weakest protection; when the
same mistake happens twice, the check belongs in the tool. Exceptions are explicit options with a stated reason, never
a silent switch.

## Explicit control flow: errors are not a control signal

- **Report state as a fact.** A component that knows something about itself reports it as a return value, status or
  field.
- **Check first, then act.** Check existence, format, capability and availability before the operation instead of
  attempting it and catching the failure.
- **Exceptions only for real faults** that cannot be checked beforehand or whose check would race: network, file
  system, other processes.
- **Never parse error text** to decide anything. When cases must be distinguished, they get a code, a field or a
  status.
- Where there is no other way, a comment says why.

## Security

Marketplace Guard reads hostile input: the code of components and repositories it scans
([ADR-0007](docs/adr/0007-downloaded-repositories-and-manifests-are-hostile-input.md)). Nothing it scans is executed,
imported or installed. Changes to quarantine decisions, thresholds, the extraction of archives or what the AI may
decide need an ADR and tests for the refused case as well as the accepted one.

Report vulnerabilities privately to the maintainer, not in a public issue.

## Architecture decisions are recorded as ADRs

Every architecture or design decision is an ADR in `docs/adr/` (MADR 4.0, English): technology and protocol choices,
interfaces, security boundaries, data stores, modes of operation, and deliberately rejected options (status
`rejected`). The rules are in [docs/adr/README.md](docs/adr/README.md).

- A pull request that makes or changes a decision brings its ADR (`docs/adr/NNNN-title-in-kebab-case.md`, next free
  number), adds it to the index in `docs/adr/README.md` and names it in its description.
- A changed decision is a new ADR that supersedes the old one. Accepted ADRs are not rewritten; the old one only
  changes its status to `superseded by ADR-NNNN`.
- Decisions made earlier without an ADR get one afterwards, marked "Backfilled on …, decided on …" with its source.
