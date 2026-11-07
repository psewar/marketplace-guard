---
status: accepted
date: 2026-11-05
decision-makers: maintainer
---

# Pinned requirements are audited without installing anything

Redacted on 2026-11-07: details of the development installation were removed from the context; the decision is
unchanged ([ADR-0011](0011-the-repository-is-site-neutral.md)).

## Context and Problem Statement

The CVE layer runs `pip-audit` on the `requirements` of a component's `manifest.json`. It called
`pip-audit -r <file> --no-deps`. In that mode pip-audit creates a virtual environment and lets pip install the
requirements into it, to learn their versions. The add-on image has no `python3-venv`, so this failed for every
component: pip-audit exited 1 without a report, and the scanner kept only an `info` `tool-note` with the last line of
pip-audit's log, which was a warning. On a running installation, no report contained a pip-audit finding and many
carried that note: the layer has not worked since it was added.

Installing `python3-venv` would make it run, but then pip downloads and builds the packages a manifest names, inside a
container that can write the whole Home Assistant configuration. Building a source distribution runs its setup code; a
hostile manifest would choose that code ([ADR-0007](0007-downloaded-repositories-and-manifests-are-hostile-input.md)).

## Decision Drivers

* The scan must not install, build or run anything the scanned component chooses (ADR-0007).
* Known vulnerabilities of declared dependencies should be found where that is possible without installing.
* What is not audited is reported as a fact with its reason, not as a log line.
* Outcomes are decided by exit code and report fields, never by log text.

## Considered Options

* Install `python3-venv` and keep the resolving mode.
* Query a vulnerability database directly from the add-on (PyPI JSON API or OSV) instead of pip-audit.
* Run pip-audit with `--no-deps --disable-pip` on the requirements pinned to an exact version, and report the rest as
  not audited.

## Decision Outcome

Chosen option: the third option.

* The sanitizer stays: URL, VCS, editable and option lines are dropped and reported (`suspicious-requirement`).
* `split_pinned()` keeps the specs with exactly one `==` clause and a plain PEP 440 version (no wildcard, no range);
  a second pin of the same package with another version counts as not pinned. Only the pinned specs are written to
  the requirements file.
* `pip-audit --no-deps --disable-pip --format json --progress-spinner off -r <file>`.
* `pip_audit_findings()` reads the outcome from the exit code and the JSON report: exit 0 or 1 with a report holding a
  `dependencies` list is an audit (each `vulns` entry is a `high` `cve` finding, an advisory listed twice counts once;
  `skip_reason` is an `info` `not-audited` finding); anything else is an `info` `tool-error` that names the exit code
  and the requirements that were not audited. pip-audit's log is not read.
* Requirements that are not pinned to an exact version are an `info` `not-audited` finding that names them.

**How "installs nothing" was verified** (pip-audit 2.10.1 as installed in the add-on image):

* Source: in `pip_audit/_dependency_source/requirement.py`, `RequirementSource._collect_from_files()` parses the file
  with `pip_requirements_parser.RequirementsFile` and, when `disable_pip` is set together with `no_deps` (or hashes),
  returns `_collect_preresolved_deps()` before the `VirtualEnv` is created. `_collect_preresolved_deps()` only reads
  each requirement's specifier: it takes the version from an `==` pin and raises "not pinned to an exact version"
  otherwise. A search of the package for process starts and installs finds three places: `VirtualEnv`
  (`pip_audit/_virtual_env.py`, `pip install` into a new environment), the `pip install` of `PipSource`
  (`_dependency_source/pip.py`, used to fix the running environment when no `-r` is given), and `_cache.py`, which
  runs `python -m pip cache dir`; the `pip_api` library it imports runs `python -m pip --version`. With `-r`,
  `--no-deps` and `--disable-pip` only the last two run, and both only ask pip about itself. The PyPI service sends
  `GET https://pypi.org/pypi/<name>/<version>/json` and reads its `vulnerabilities`.
* Run: in the amd64 image (trixie base), a component pinning `requests==2.19.0` and `django==3.2.0` gave 43 `cve`
  findings; afterwards `django` was not importable, and the only file written outside caches and the test folder was
  the add-on's own bytecode cache. Unpinned requirements gave the `not-audited` fact; without network the outcome was a
  `tool-error` naming exit 1.
* Documentation: `--disable-pip` is described as "don't use `pip` for dependency resolution", allowed only with
  hashed requirements or `--no-deps`.

The first option was not chosen because it runs code chosen by the scanned component. The second was not chosen
because pip-audit already does that query, with its caching and its JSON report, and the add-on would have to keep a
second client in step with the service.

### Consequences

* Good, because the CVE layer works: exactly pinned requirements with known vulnerabilities are `high`, so a new
  component that pins one is quarantined and a known one is reported.
* Good, because nothing a manifest names is installed or built.
* Bad, because most Home Assistant manifests pin exactly, but those that give a range or no version are not audited;
  the finding says which.
* Bad, because only the declared requirements are audited, not what they depend on (as before with `--no-deps`).
* Bad, because components installed before the update are not rescanned by it (their content hash is unchanged); their
  dependencies are audited when they change.

### Confirmation

`TestPipAudit` in `marketplace_guard/tests/test_marketplace_guard.py`: the split into pinned and not pinned, the mapping of a report
(duplicates, skipped dependencies), a missing report whatever the log says, and that only pinned specs reach pip-audit,
with `--no-deps` and `--disable-pip`.

Accepted by the maintainer on 2026-11-07; implemented in pull request #10.
