# Changelog

## 2.4.1
- **Status sensor:** until the gate is active, Marketplace Guard asks Home Assistant every minute instead of every 15
  minutes, so `marketplace_gate` says `active` within a minute after you add the integration.
- **Gate updates:** an update of the app brings the gate's new version along without the notification that asks to add
  the integration again; Home Assistant loads it at its next restart, the version before keeps checking until then.

## 2.4.0
- **Gate for Marketplace installs (optional, off by default):** with **Check Marketplace installs before they load**,
  Marketplace Guard installs the small integration *Marketplace Guard Gate*. Once added, the Marketplace asks Marketplace
  Guard before an integration or dashboard card it wrote can load; what would be quarantined is not installed: the
  Marketplace puts back what was there, its install dialog says why, and the code never runs. It hooks into an internal
  part of the Marketplace: when a Home Assistant update changes it, the gate says so and does not start (ADR-0042).
- **Status sensor:** the attribute `marketplace_gate` says whether the gate is `active`.

## 2.3.0
- **Web page:** Marketplace Guard has a page in Home Assistant's sidebar (for administrators; turn on *Show in sidebar*
  on the Info tab): status, a field to pre-check a repository, the components in quarantine with their reports, and
  the latest reports (ADR-0041).
- **Restore from the page:** after reading a quarantined component's report, type its name to put it back. This copy is
  accepted as installed (not quarantined again for being back, a later change is checked as an update), without an
  allowlist entry. A notification names the component and the user; then restart Home Assistant to load it.

## 2.2.0
- **Pre-check from Home Assistant:** run the action `hassio.addon_stdin` with `addon: <app slug>` and
  `input: owner/repo` (or a GitHub URL, or a list of up to ten) to pre-check a repository without editing a file;
  from Developer tools, a script, an automation or a dashboard. The documentation has a script with a field for a
  dashboard. The app names its slug in the log, the first-start summary and the status sensor (`app_slug`). Requests
  are bounded (20 waiting at most) and can only ask for pre-checks (ADR-0040).

## 2.1.0
- **First start:** one notification sums up the baseline: how many components were recorded as trusted, which of them
  are worth a look (verdict at the notification threshold or above), the notify services and AI Task entities your Home
  Assistant has for the settings, and how to pre-check a repository. It replaces the notification per component of the
  baseline; a component at the quarantine threshold is named there, its findings are in its report (ADR-0039).
- **Status sensor:** the attribute `notify_targets_available` lists the notify services Home Assistant has.
- When the saved state was unreadable, the "state lost" notification names the components worth a look.

## 2.0.3
- **Documentation:** the Documentation tab starts with getting started (what the first start does, push alerts, the AI
  second opinion), then everyday use (installing, pre-checking a repository, reports, restoring a component), the
  status sensor with a dashboard card, a table of all options, and troubleshooting; English and German alike. It uses
  Home Assistant's current names (apps, since Home Assistant 2026.2) and fixes two places where the former name was
  left.
- **Install:** the published README has a button that adds the repository to your Home Assistant in one click, and
  prints the repository URL (ADR-0038).
- No change in behaviour.

## 2.0.2
- Documentation and tests: examples are described without details of any installation; consistent spelling in the
  German documentation. No change in behaviour.

## 2.0.1
- **Calibration:** a Python file larger than 16 MiB is no longer `high` when it holds only data. Python's tokenizer
  reads it whole, line by line, up to 64 MiB; a file of nothing but imports and constants (embedded images, tables) is
  an informational `large-data` finding. Code, or a file too large or too odd to tell, stays `high` (ADR-0037). A
  26 MiB module of embedded images, as published integrations ship them, made its integration `high` for that file
  alone.
- **Fix:** bandit gets only Python files up to 2 MiB, named one by one instead of the whole folder. Its memory grows
  about 160-fold with the code: one component with 64 MiB of code took 9.9 GB and 148 s; now that component is `high`
  after a few seconds with 152 MiB. A larger file is reported as not analysed by bandit (the line rules read it), and
  bandit no longer meets a symbolic link.

## 2.0.0
- **Renamed to Marketplace Guard** (ADR-0036). Since Home Assistant 2026.11 the way custom components are installed is
  called the Marketplace; the add-on now carries that name. The slug is `marketplace_guard`, so Home Assistant treats
  it as a new add-on: install Marketplace Guard, then uninstall HACS Guard. Its first start records the installed
  components as trusted again (baseline), as on any first start. What changes:
  - default request file `/homeassistant/marketplace_guard/scan_request.txt` and reports in
    `/homeassistant/marketplace_guard/reports/`; quarantine folder `/homeassistant/_marketplace_quarantine`;
  - status sensor `sensor.marketplace_guard`; the configuration folder is `addon_configs/<...>_marketplace_guard`
    (move `ai_prompt.txt` there);
  - log lines start with `[marketplace-guard]`, notifications with "Marketplace Guard".
  Options you set for HACS Guard are not carried over by Home Assistant: set them again (the AI review, for example).
- The notice about a code override in `/homeassistant/hacs_guard/code` (versions before 1.6.0) is gone: a new
  installation never had that folder.

## 1.7.2
- **Calibration:** docstrings are read as text, like comments. A statement made of nothing but string literals is
  never run, so the patterns its words name (`pip install`, `os.system(`) are no longer findings; a component whose
  only `high` findings were sentences in its docstrings is no longer rated `high`. An f-string, or a string with code
  in its statement, is still code. When any Python file of a component mentions reading docstrings (`__doc__`,
  `getdoc`, `get_docstring`), all its docstrings are scanned as code as before, and an informational
  `docstring-read` finding says so (ADR-0035).

## 1.7.1
- **Fix:** the armv7 image could not be built, already with 1.4.4: PyPI has no armv7 wheel of `msgpack` (a
  dependency of `pip-audit`), and the image has no compiler. It is now built as pure Python there
  (`MSGPACK_PUREPYTHON=1`); amd64 and aarch64 keep the prebuilt wheels. Verified under emulation: the armv7 and
  aarch64 images build, start their scanners and pass the unit tests.

## 1.7.0
- **Quarantine risky updates** (`quarantine_updates`) is on by default. With Home Assistant's Marketplace a new
  integration can run before HACS Guard has scanned it, but an update only runs after the next restart: quarantining
  an update that brings a risk the version before did not have is the quarantine that still comes first. Turn the
  option off to have such updates only reported (ADR-0025).

## 1.6.1
- **Security:** the image installs the scanners from `requirements.txt`, which pins every package, the about thirty
  that `bandit`, `pip-audit` and `watchdog` depend on included, with its hashes (`pip --require-hashes`). Before, each
  build took whatever PyPI served for those dependencies. They live in a virtual environment (`/opt/venv`) instead of
  the system Python; `git` is no longer installed (ADR-0034, supersedes ADR-0010).
- **Security:** the AppArmor profile denies starting programs from the folders HACS Guard scans or writes
  (`/homeassistant`, `/config`, `/data`, `/share`, `/tmp`) (ADR-0034).
- Scanner versions are unchanged: `bandit` 1.9.4, `pip-audit` 2.10.1, `watchdog` 7.0.0.

## 1.6.0
- **Fix (security):** the files that steer HACS Guard lay in the Home Assistant configuration folder, which every
  custom integration can write: a component that got in could replace the guard's code from the next add-on start
  (`/homeassistant/hacs_guard/code/`) or tell the AI to answer "clean" (`ai_prompt.txt`, read as the operator's
  instructions). Both now live in the add-on's own configuration folder (`addon_configs/<...>_hacs_guard/`, `/config`
  inside the add-on), which Home Assistant Core cannot reach (ADR-0033, supersedes ADR-0004 and ADR-0009).
- **Action needed** if you wrote AI instructions: copy them from `/homeassistant/hacs_guard/ai_prompt.txt` to
  `ai_prompt.txt` in the add-on's configuration folder (Samba, File editor or SSH add-on). The old file is no longer
  read; a notification reminds you while it still holds instructions. A code override in
  `/homeassistant/hacs_guard/code/` is ignored, with a warning.
- The log and the status sensor say which code runs: `code_source` (`built-in` or `override`) and `code_sha256`.

## 1.5.4
- **Fix (security):** text from a scanned component could appear in HACS Guard's notifications as a link: a
  requirement `[Mark as safe](https://…)` in a hostile manifest was rendered as a clickable link in the warning. Text
  that comes from a component (finding messages, folder names, pre-check notes and errors) is now shown as code
  (ADR-0032).

## 1.5.3
- **Fix (security):** an AI answer without the `VERDICT=` line was read by keywords, so "no evidence of malicious
  intent" — the wording the prompt asks for — became `malicious` (with **Let AI trigger quarantine**: a quarantine),
  and a `VERDICT=` line quoted from the reviewed code could decide the verdict. Only the first line of the answer
  counts now; anything else is reported as an unusable answer (ADR-0030).
- **Fix (security):** everything taken from the component is marked as untrusted data in the AI prompt, between
  markers with a random token per review. The AI sees the lines around the static findings first, so harmless code
  in front no longer pushes them out of view, and dashboard cards are reviewed with their scripts (ADR-0030).
- **Fix (security):** a repository named in a component's own `manifest.json` no longer counts for the allowlist, the
  own-backend label of hosts or the AI's trust; only Home Assistant's records (HACS, Marketplace) and the pre-check
  do. Components installed by hand are allowlisted by their folder name. The owner must equal a whole host label: a
  short owner name no longer turns unrelated hosts into the component's own backend (ADR-0031).

## 1.5.2
- **Fix (security):** a repository pre-check read every header of a downloaded archive before checking its limits, so
  an archive of countless empty entries could take gigabytes of memory. Members are now read and checked one at a
  time, and every entry, skipped links included, counts against a limit of 50,000 (ADR-0029).
- A pre-check refusal (too large, unsafe path, damaged archive) is reported as the reason, as before.
- Only a trailing `.git` is removed from a repository name (`owner/foo.gitlab` was read as `owner/foolab`); `.` and
  `..` are not accepted as names.
- A component folder whose name starts with two dots is watched like any other.

## 1.5.1
- **Fix (security):** three kinds of valid Python hid shell execution from the heuristics: a continued line starting
  with the `//` operator, a line starting with `#` inside a string that it closes, and source declared as UTF-7.
  Python files are now read the way Python reads them: comment lines come from its tokenizer, the text is decoded with
  the declared codec, and a codec that can hide code is a `high` finding `source-encoding` (ADR-0026, supersedes
  ADR-0006). In JavaScript, only `//` lines are skipped (`#` starts a private field there).
- **Fix (security):** the scanned code could switch bandit off: `# nosec`, a `.bandit` file, or two `.bandit` files
  (bandit then stopped without a report, which was taken as clean). Bandit runs with its own empty ini file and
  `--ignore-nosec`; a run without a report is an `info` `tool-error` (ADR-0026). Verified with bandit 1.9.4 in the
  add-on image.
- **Fix (security):** a component could stop or slow its own scan: a symbolic link to `/dev/zero` or a FIFO stopped
  the worker for good, and many raw-IP URLs or a long line made the scan take minutes. Only regular files are read,
  without following links and up to 16 MiB; links leaving a component and special files are `high` findings; a larger
  script is a `too-large` finding; every rule runs in linear time (ADR-0027).
- **Fix (security):** the compressed copies the web server sends instead of a script (`.js.gz`, `.js.br`) are checked:
  a copy that differs from its script is `high` and its content is scanned; a `.br` copy is `high`. `.mjs` and `.cjs`
  scripts are scanned (ADR-0028).
- bandit and pip-audit run without the Supervisor token in their environment.
- Hosts that serve anyone's files (`raw.githubusercontent.com`, gists, release downloads) are listed as outbound hosts.
- The content hash covers the newly checked files. Entries saved by earlier versions are recognised as unchanged, so
  the update does not rescan every component; components are checked with the new rules when they next change.

## 1.5.0
Home Assistant 2026.11 replaced HACS by the built-in **Marketplace** (ADR-0024).
- **Fix (security):** HACS Guard reads the Marketplace's records (`.storage/marketplace.repositories`,
  `marketplace.critical`), and those of HACS on older versions. The Marketplace deletes the HACS files, so the
  repository name of a component, the critical-list check, the allowlist by repository and the owner match fell back
  to what the component's own manifest says.
- **Fix (security):** the catalog's list of critical repositories is checked as well as the list of removed ones. The
  lists are read every six hours instead of for every component; a list that cannot be read is an `info` finding
  `catalog-unavailable` instead of being skipped silently.
- The Marketplace sets a new integration up without a restart, so its code can run before HACS Guard has scanned it.
  After quarantining a new integration, the notification says whether it is running in Home Assistant. New option
  **Restart after quarantining a running integration** (`restart_after_quarantine`, off): restart Home Assistant then.
- New option **Quarantine risky updates** (`quarantine_updates`, off): an update of an installed component that
  brings a risk at the quarantine threshold the version before did not have is quarantined before the restart loads
  it. A risk the component already had (for example a power tool that runs shell commands) does not count (ADR-0025).
- Texts and documentation name the Marketplace next to HACS; the pre-check scans what both would install.
- Components installed before this update keep their state; the risks used by `quarantine_updates` are recorded when
  a component is next scanned (until then, the verdicts are compared).

## 1.4.5
- **Fix (security):** a quarantined component that appears again in place — moved back, or downloaded again by HACS
  or the Marketplace — is a new install. An identical copy was taken as unchanged: it was not scanned, no notification
  was sent, and Home Assistant loaded it at the next start while the status sensor still listed it as quarantined; a
  changed copy was only reported. To restore a component you trust, add it to the allowlist first.
- **Fix (security):** a component found at a later start that HACS Guard had never seen (installed while the add-on
  was stopped) was recorded as trusted baseline. Only the very first start records the baseline, as documented.
- **Fix (security):** the quarantine no longer waits for the AI review. A component whose static verdict reaches the
  quarantine threshold is moved at once; otherwise the review runs and the decision is made once on the combined
  verdict. The AI call is made once per entity instead of three times on a timeout (ADR-0022).
- One worker makes every scan and quarantine decision. The start-up scan no longer runs in a second thread that
  changed the state at the same time as the main loop; a fresh install is handled between the items of a rescan, a
  pre-check or the AI retries instead of after them (ADR-0023).
- Quarantining the same component twice within a second moved the second copy into the first quarantine folder; each
  quarantine now gets a folder of its own.
- The state is saved with a copy of the save before. A damaged state file is read from that copy; if neither can be
  read, the baseline is recorded again and a notification says so, instead of silently starting over.

## 1.4.4
- **Fix (security):** the dependency CVE check works. `pip-audit` failed for every component because it tried to
  install the requirements into a virtual environment, which the image cannot create; reports only carried a
  `tool-note`. Requirements pinned to an exact version (`name==1.2.3`) are now audited with
  `pip-audit --no-deps --disable-pip`, which looks up name and version and installs nothing; a known vulnerability
  is a `high` `cve` finding. Requirements given as a range or without a version are an `info` `not-audited` finding
  that names them. A failed run is an `info` `tool-error` with pip-audit's exit code. URL, VCS and editable
  requirements are still dropped and reported (ADR-0021).
- Components installed before this update get their dependencies audited when they next change.

## 1.4.3
- Base image for amd64 and aarch64: Debian 13 (trixie) `2026.10.3` instead of Debian 12 (bookworm) `2026.02.0`. Its
  Python 3.13 has the `data` filter for unpacking archives, so repository pre-checks now use it; on bookworm's Python
  3.11.2 it was not available (ADR-0019).
- armv7 keeps `bookworm-2025.11.1`: Home Assistant no longer builds base images for it (ADR-0020, proposed).
- `pip-audit` 2.10.1 (was 2.10.0) and `watchdog` 7.0.0 (was 6.0.0); `bandit` 1.9.4 is current.

## 1.4.2
- **Fix (security):** Trojan Source (CVE-2021-42574). Unicode bidirectional control characters in `.py`, `.js` and
  `.json` files are a `high` finding, on every line including comments, since a comment is where they hide code
  (ADR-0018).
- Invisible characters (zero width space, joiners, word joiner, a byte order mark after the start of a file) next to
  ordinary text are a `medium` finding in Python and informational in JavaScript; inside emoji sequences, Persian or
  Indic text and in JSON translations they are not a finding (ADR-0018).
- Tests for the size and file-count limits of archive extraction in repository pre-checks.
- Components installed before this update are checked for these characters when they next change.

## 1.4.1
- **Fix:** an AI review that could not reach Home Assistant or the AI Task (for example HTTP 502 while Home Assistant
  restarts, a time-out, or the model's service failing) is retried with the status heartbeat: after 15 minutes, 1, 4
  and 12 hours, then given up. Before, the component kept the `ai-review-error` finding and was never reviewed again.
  A verdict reached on a retry is acted on like a scan's, including quarantine of a component that was new. No AI
  Task entity, a turned-off review and refused requests (HTTP 4xx) are not retried. Pre-checks are not retried
  (ADR-0017).
- The status sensor lists components waiting for an AI review retry (`ai_review_pending`).
- The log names the runtime at the start, and the status sensor carries it: `python_version`, `tar_data_filter`
  (whether Python has the `data` filter for archives), `bandit_version` and `pip_audit_version` (`missing` when
  not installed).

## 1.4.0
- Works without changes on any installation: notification targets are free text (default: a persistent
  notification), and no installation-specific entity is preset.
- The AI second opinion is **off by default** (ADR-0012). When on, an empty **AI Task** uses the entity Home
  Assistant prefers. Before any call the add-on asks Home Assistant which AI Task entities and notify services
  exist; the log and the status sensor (`ai_review`, `ai_task_entities`, `notify_problems`) say what is usable.
  Unknown notification targets are skipped; with none left, alerts fall back to a persistent notification.
  Existing configurations keep working, including `none` as an empty fallback.
- The request file and `ai_prompt.txt` are created with instructions on the first start (never overwritten).
- The AI prompt now carries the general false-positive rules: links, image sources and XML namespaces are not
  data flows, public keyless data APIs fit for the purpose are normal, no verdict on speculative wording.
- Log messages are English throughout.

## 1.3.2
- **Fix (security):** a component whose own folder is named like a test folder (`test`, `tests`, `testing`,
  `fixtures`) was skipped entirely and reported as clean; such a name could hide a malicious component from the
  scan. Only folders *below* the scanned component are skipped now.
- **Fix (security):** test folders and `test_*.py`/`conftest.py` files inside a component were never scanned, but the
  component can import them, so code placed there ran unchecked. Everything in the component folder is scanned now,
  except `.git`, `.github` and `__pycache__` (ADR-0014); the AI prompt treats test files as importable code.
  Components that contain such files are scanned once more after the update.
- **Fix (security):** compiled code that Python imports in place of reviewable source is a `high` finding: native
  extension modules (`.so`, `.pyd`), `.pyc` files without a `.py` of the same name, and `__pycache__` bytecode marked
  "unchecked hash", which runs instead of the `.py` next to it (ADR-0015). Bytecode Python writes itself is not.
- **Fix:** the repository pre-check scans what HACS would install: the newest release (the default branch when there
  is none) and the folder HACS picks (first under `custom_components` in git's order, or the root with
  `content_in_root`). Report and notification say what was scanned, and for `zip_release` repositories that the
  installed release asset was not (ADR-0016).

## 1.3.1
- Notifications name `medium` findings too, each with its severity, so a medium verdict says why. They end with a link
  to the status sensor: the configured `status_entity`, and no link when the status sensor is off.
- Hardening: repository pre-checks extract archives with Python's `data` filter where the Python in the image has it
  (it strips setuid and device bits and refuses escaping names), on top of the existing checks.

## 1.3.0
- Hardening: manifest requirements are sanitized before `pip-audit` (URL/VCS/editable specs are
  dropped and flagged), so a hostile manifest cannot make the scanner fetch attacker-controlled
  locations. Repository pre-checks now cap the download size and guard against archive bombs. State
  writes are serialized with a lock.
- New: **allowlist** (always-trusted components/repositories), **periodic safety-net rescan**,
  optional **status sensor** (`sensor.hacs_guard`), and an **AI Task fallback** entity.
- Packaging: **multi-architecture** (amd64/aarch64/armv7), **pinned** scanner dependencies, an
  **AppArmor** profile, and an icon/logo.

## 1.2.0
- Publish-quality documentation and runtime text (English); localized configuration page (en/de).

## 1.1.0
- Optional **AI second opinion** via Home Assistant AI Tasks.
- Calibrated heuristics to avoid false positives on minified frontend bundles.

## 1.0.0
- Initial release: quarantine-on-write, repository pre-check, `bandit` + `pip-audit` + heuristics +
  the HACS critical/removed list.
