# Architecture Decision Records

Why Marketplace Guard is built the way it is. `marketplace_guard/DOCS.md` describes *what* it does; the ADRs here say *why*.
Format: [MADR 4.0](https://adr.github.io/madr/), in English.

## Rules

- One decision per ADR: `docs/adr/NNNN-title-in-kebab-case.md`, numbered from `0001` without gaps.
- Front matter: `status`, `date` (the day of the decision), `decision-makers` (a role such as `maintainer`, never a
  person's name; [ADR-0011](0011-the-repository-is-site-neutral.md)).
- Status: `proposed` → `accepted` or `rejected`; later `deprecated` or `superseded by ADR-NNNN`.
- Accepted ADRs are not rewritten. A changed decision gets a new ADR that supersedes the old one; the old one only
  changes its status. Both link to each other. Typos and links may be fixed, and personal or site details redacted
  (ADR-0011): the decision and its reasons stay.
- The ADR comes in the same pull request as the change, or before it as `proposed`. The pull request description
  names it, and the index below lists it. `tools/check.py` checks the index against the ADRs (number, title, status,
  date, no gaps).
- ADRs 0001–0010 were backfilled on 2026-11-02 from `DOCS.md`, `PUBLISHING.md`, the changelog and the maintainer's
  design conversations of 2026-06-07, 2026-06-08 and 2026-06-21. Each says when it was decided and from which source.

## Index

| No. | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-quarantine-on-write-and-a-repository-pre-check-instead-of-patching-hacs.md) | Quarantine on write and a repository pre-check instead of patching HACS | accepted | 2026-06-07 |
| [0002](0002-trusted-components-baseline-at-first-start-and-an-allowlist.md) | Trusted components: a baseline at first start and an allowlist | accepted | 2026-06-07 |
| [0003](0003-ai-second-opinion-through-home-assistant-ai-tasks.md) | AI second opinion through Home Assistant AI Tasks | superseded by ADR-0012 | 2026-06-07 |
| [0004](0004-operator-guidance-for-the-ai-in-a-file-read-on-every-scan.md) | Operator guidance for the AI in a file read on every scan | superseded by ADR-0033 | 2026-06-08 |
| [0005](0005-a-components-own-backend-is-not-a-finding.md) | A component's own backend is not a finding | accepted | 2026-06-08 |
| [0006](0006-comment-lines-are-not-scanned.md) | Comment lines are not scanned | superseded by ADR-0026 | 2026-06-21 |
| [0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md) | Downloaded repositories and manifests are hostile input | accepted | 2026-06-08 |
| [0008](0008-periodic-full-rescan-besides-the-file-watcher.md) | Periodic full rescan besides the file watcher | accepted | 2026-06-08 |
| [0009](0009-override-code-folder-takes-precedence-over-the-built-in-code.md) | Override code folder takes precedence over the built-in code | superseded by ADR-0033 | 2026-06-07 |
| [0010](0010-pinned-scanner-versions-and-an-apparmor-profile.md) | Pinned scanner versions and an AppArmor profile | superseded by ADR-0034 | 2026-06-08 |
| [0011](0011-the-repository-is-site-neutral.md) | The repository is site-neutral | accepted | 2026-11-02 |
| [0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md) | AI review is opt-in and uses the AI Task Home Assistant offers | accepted | 2026-11-02 |
| [0013](0013-publish-as-a-new-repository-with-one-start-commit.md) | Publish as a new repository with one start commit | accepted | 2026-11-02 |
| [0014](0014-everything-in-a-component-folder-is-scanned-test-code-included.md) | Everything in a component folder is scanned, test code included | accepted | 2026-11-02 |
| [0015](0015-compiled-code-that-cannot-be-reviewed-is-a-finding.md) | Compiled code that cannot be reviewed is a finding | accepted | 2026-11-02 |
| [0016](0016-the-pre-check-scans-what-hacs-would-install.md) | The pre-check scans what HACS would install | accepted | 2026-11-02 |
| [0017](0017-an-unreachable-ai-review-is-retried-within-a-bound.md) | An unreachable AI review is retried within a bound | accepted | 2026-11-05 |
| [0018](0018-unicode-that-hides-code-is-a-finding.md) | Unicode that hides code is a finding | accepted | 2026-11-05 |
| [0019](0019-the-base-image-follows-the-newest-stable-debian-release.md) | The base image follows the newest stable Debian release | accepted | 2026-11-05 |
| [0020](0020-drop-armv7.md) | Drop armv7 | rejected | 2026-11-05 |
| [0021](0021-pinned-requirements-are-audited-without-installing-anything.md) | Pinned requirements are audited without installing anything | accepted | 2026-11-05 |
| [0022](0022-the-static-verdict-is-acted-on-before-the-ai-review.md) | The static verdict is acted on before the AI review | accepted | 2026-11-06 |
| [0023](0023-one-worker-makes-every-scan-and-quarantine-decision.md) | One worker makes every scan and quarantine decision | accepted | 2026-11-06 |
| [0024](0024-home-assistants-marketplace-replaces-hacs.md) | Home Assistant's Marketplace replaces HACS | accepted | 2026-11-06 |
| [0025](0025-an-update-that-brings-a-new-risk-can-be-quarantined.md) | An update that brings a new risk can be quarantined | accepted | 2026-11-06 |
| [0026](0026-python-is-read-the-way-python-reads-it.md) | Python is read the way Python reads it | accepted | 2026-11-06 |
| [0027](0027-only-regular-files-are-read-within-a-size-limit.md) | Only regular files are read, within a size limit | superseded by ADR-0037 | 2026-11-06 |
| [0028](0028-compressed-copies-and-module-scripts-are-scanned.md) | Compressed copies and module scripts are scanned | accepted | 2026-11-06 |
| [0029](0029-archive-members-are-checked-one-at-a-time.md) | Archive members are checked one at a time | accepted | 2026-11-06 |
| [0030](0030-the-ai-reads-component-text-as-data-and-answers-on-its-first-line.md) | The AI reads component text as data and answers on its first line | accepted | 2026-11-06 |
| [0031](0031-repository-names-count-only-from-home-assistants-records.md) | Repository names count only from Home Assistant's records | accepted | 2026-11-06 |
| [0032](0032-component-text-is-shown-as-code-in-notifications.md) | Component text is shown as code in notifications | accepted | 2026-11-06 |
| [0033](0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md) | What steers HACS Guard lives out of Home Assistant's reach | accepted | 2026-11-06 |
| [0034](0034-hash-locked-scanners-and-no-execution-from-scanned-folders.md) | Hash-locked scanners and no execution from scanned folders | accepted | 2026-11-06 |
| [0035](0035-docstrings-are-read-as-text-unless-the-code-reads-them.md) | Docstrings are read as text unless the code reads them | accepted | 2026-11-07 |
| [0036](0036-the-add-on-is-renamed-to-marketplace-guard.md) | The add-on is renamed to Marketplace Guard | accepted | 2026-11-07 |
| [0037](0037-each-reader-gets-a-limit-that-fits-what-it-costs.md) | Each reader gets a limit that fits what it costs | accepted | 2026-11-07 |
| [0038](0038-the-published-readme-carries-a-one-click-install-button.md) | The published README carries a one-click install button | proposed | 2026-11-09 |
| [0039](0039-the-first-start-ends-with-one-summary.md) | The first start ends with one summary | proposed | 2026-11-09 |
| [0040](0040-pre-checks-can-be-asked-for-through-the-action-addon-stdin.md) | Pre-checks can be asked for through the action hassio.addon_stdin | proposed | 2026-11-09 |
| [0041](0041-a-web-page-in-the-sidebar-shows-pre-checks-and-restores.md) | A web page in the sidebar shows, pre-checks and restores | proposed | 2026-11-09 |
| [0042](0042-an-optional-gate-checks-marketplace-installs-before-they-load.md) | An optional gate checks Marketplace installs before they load | proposed | 2026-11-09 |
