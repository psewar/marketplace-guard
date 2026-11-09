---
status: proposed
date: 2026-11-09
decision-makers: maintainer
---

# Pre-checks can be asked for through the action hassio.addon_stdin

## Context and Problem Statement

A repository pre-check is asked for by writing `owner/repo` into a text file in the configuration folder. That needs a
file editor and a path, and it cannot be started from a script, an automation or a dashboard. Home Assistant has a
built-in action for exactly this kind of input: `hassio.addon_stdin` sends its `input` to the standard input of an app
whose `config.yaml` has `stdin: true`. Home Assistant Core sends the input as JSON (a string, or a mapping), and the
Supervisor writes it to stdin without a newline.

Anything that runs inside Home Assistant Core can run the action, also a component that should not be trusted. What
it reaches must therefore not be able to quarantine or exempt anything
([ADR-0033](0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md)), and it must not be able to tie the app
up.

## Decision Drivers

* A pre-check can be started from Home Assistant without editing a file: from Developer tools, a script, a dashboard.
* What Home Assistant can send asks for pre-checks only, and is bounded.
* Every decision stays with the one worker ([ADR-0023](0023-one-worker-makes-every-scan-and-quarantine-decision.md)).
* The user does not have to find out the app's slug.

## Considered Options

* Keep the request file as the only way.
* Poll an `input_text` helper that the user creates.
* The action `hassio.addon_stdin` (`stdin: true`), read by a thread that hands requests to the worker.

## Decision Outcome

Proposed: the third option.

* `config.yaml` has `stdin: true`. A thread reads stdin and splits it into requests: complete lines, and complete JSON
  values that came without a newline (also several in a row). A request is a repository (`owner/repo` or a GitHub
  URL), as a JSON string, a plain line or a JSON list of up to 10. A mapping, invalid JSON, a request over 512 bytes
  and input without an end over 4096 bytes are refused.
* The thread decides nothing: it asks the worker to queue the repository. The worker takes only what parses as a
  GitHub repository, normalised to `owner/repo`, not twice, and at most 20 waiting; it reports the outcome as a fact
  (`queued`, `invalid`, `full`). The worker runs the queued pre-checks in its loop, a fresh install first; on the first
  start, after the baseline. A request not taken is logged and notified.
* The pre-check itself is the one of the request file (`precheck_repo`): download, scan, report, notification;
  nothing is installed.
* The app derives its slug from its host name (the Supervisor names the container after the slug, with `-` for `_`)
  and names it in the log, the status sensor (`app_slug`) and the first-start summary, with the action to run.

The first option keeps a file editor as the only way. The second needs a helper the user creates, and polling.

### Consequences

* Good, because a pre-check is one action away, usable from scripts, automations and dashboards; the documentation
  gives a script with a field for a dashboard.
* Good, because what Home Assistant can send is bounded and can only ask for pre-checks, like the request file.
* Bad, because a component inside Home Assistant can start up to 20 downloads at a time (each bounded by the size
  limit); it can do the same with the request file today.
* Bad, because `stdin: true` keeps the app's standard input open.

### Confirmation

`TestPrecheckFromHomeAssistant` in `marketplace_guard/tests/test_marketplace_guard.py`: JSON with and without a
newline, several values in a row, a list, a plain line; an incomplete request waits for its rest; refusals for an
over-long request, a list of non-strings, invalid JSON, too many repositories, input without an end, a mapping (and it
does not block what follows); the queue normalises, does not take a repository twice, refuses what is not a
repository and is bounded; the worker runs the queue, on the first start after the baseline; a pipe carries a request
to the queue and a bad one is notified; the slug comes from the host name; the summary shows the action.
