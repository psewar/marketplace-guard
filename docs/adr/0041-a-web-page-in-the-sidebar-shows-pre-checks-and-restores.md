---
status: accepted
date: 2026-11-09
decision-makers: maintainer
---

# A web page in the sidebar shows, pre-checks and restores

## Context and Problem Statement

Everything Marketplace Guard shows lives in notifications, report files and sensor attributes; a pre-check needs a file
or an action ([ADR-0040](0040-pre-checks-can-be-asked-for-through-the-action-addon-stdin.md)), and restoring a
quarantined component means editing the allowlist, moving a folder with Samba, the File editor or SSH, and restarting.
Home Assistant can show an app's own web page in its sidebar (ingress).

Restoring is the delicate part: it exempts a component from quarantine. What steers Marketplace Guard should be out of
reach of a component running in Home Assistant Core
([ADR-0033](0033-what-steers-hacs-guard-lives-out-of-home-assistants-reach.md)). A web page served through ingress is
not: Core proxies it, so code running in Core can send it requests too. But such code can already do what a restore
does: the quarantine folder is in the configuration folder, which Core can write, and the app's options (the
allowlist) can be changed through the Supervisor API that Core uses for the Configuration tab.

## Decision Drivers

* Status, reports, quarantine and pre-checks in one place, without files or actions.
* Restoring in a few clicks, but only on purpose, and never unnoticed.
* A restore should exempt as little as possible.
* No new package in the image ([ADR-0034](0034-hash-locked-scanners-and-no-execution-from-scanned-folders.md)), no
  port outside ingress, every decision with the one worker
  ([ADR-0023](0023-one-worker-makes-every-scan-and-quarantine-decision.md)).

## Considered Options

* No web page.
* A web page that shows and pre-checks, without restoring.
* A web page that also restores, protected by a confirmation file outside Home Assistant's reach.
* A web page that also restores, accepting the restored copy, with a typed confirmation and a notification.

## Decision Outcome

Chosen option: the fourth option; the maintainer chose to have restoring on the page.

* `config.yaml`: `ingress: true` on port 8099, a sidebar panel for administrators (`panel_admin`), no other port. The
  server is Python's `http.server` in a thread; it answers only the Supervisor's ingress proxy, whose address it
  resolves from the host name `supervisor` at start (without it, the page is not started), sends a strict Content
  Security Policy, and every form carries a token made at start. Requests are bounded (4 KiB).
* The page reads a view the worker builds after each pass; it never reads or changes the state itself. Pre-checks go
  into the worker's queue (ADR-0040); restores into a queue of their own (at most five).
* A restore needs the component's name typed. The worker checks again before it moves anything: the entry is
  quarantined, the name matches, the copy is a real folder directly in the quarantine folder, its place is a watched
  folder and free. Then it moves the copy back, removes the added `SCAN_REPORT.txt`, and records the copy's hash as
  accepted, like a baseline entry: it is not quarantined again for being back, and a later change is checked as an
  update. A notification and the log name the component and the user Home Assistant reports for the request.
* Text from a component is escaped; reports are shown only when their name is in the reports folder's listing. Notes
  after a form are kept on the server, so a link cannot put text on the page.

The second option leaves restoring as manual as before. The third needs a file outside Home Assistant for every
restore, which is the manual way again. Restoring by accepting the copy exempts less than the allowlist, which exempts
every later version too.

### Consequences

* Good, because status, pre-checks, quarantine and reports are one click away from the sidebar.
* Good, because a restore exempts only the copy that was read, and every restore is announced with its user.
* Bad, because code running in Home Assistant Core can send a restore request; it could restore a component by moving
  its folder and changing the allowlist already. The notification makes a restore visible either way.
* Bad, because the user name comes from headers Core sets; code in Core could set them as well.
* Bad, because the app now serves a web page, a new surface; it is kept small, read-mostly and behind ingress.

### Confirmation

`TestWebPage` in `marketplace_guard/tests/test_marketplace_guard.py`, against a real server on a local port: the page
shows status, quarantine and the form with its security policy; text from a component is escaped; only the ingress
proxy is answered, and without its address the page does not start; only listed reports are shown; a form without the token and an oversized request are refused; a
pre-check from the page is queued and its note shown; a restore needs the name; a restore puts the copy back, removes
the report file, accepts the copy, notifies with the user, is not undone by the watcher, and a later change is scanned
again; a restore is refused when the place is taken, the copy is outside the quarantine folder, or the place is not a
watched folder.

Accepted by the maintainer on 2026-11-09; implemented in pull request #44.
