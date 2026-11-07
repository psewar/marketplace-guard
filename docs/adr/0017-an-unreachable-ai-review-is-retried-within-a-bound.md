---
status: accepted
date: 2026-11-05
decision-makers: maintainer
---

# An unreachable AI review is retried within a bound

## Context and Problem Statement

The AI review ([ADR-0012](0012-ai-review-is-opt-in-and-uses-the-ai-task-home-assistant-offers.md)) runs once, when a
new or changed component is scanned. When Home Assistant or the AI Task did not answer, the component got an `info`
finding `ai-review-error`, and because its content hash did not change it was never reviewed again. This was seen on a
running installation: the review of a new component failed with HTTP 502 while Home Assistant Core restarted, and the
component kept its static verdict without a second opinion. `_ha_post()` already retries a 502, 503 or 504 twice after
two seconds, which does not cover a restart or a model that is loading or switched off for a while.

## Decision Drivers

* A review that failed for a passing reason gets another chance, without the operator doing anything.
* A review that cannot work until the operator acts (no AI Task entity, review turned off, refused request) is not
  repeated: waiting does not fix it, and every call sends component code to a model.
* Whether to retry is decided from facts: the exception class and the HTTP status at the network boundary and the
  state of `ai_plan()`, never from the text of an error.
* A verdict reached later is acted on exactly as it would have been at the scan: same decision path, same
  notification.
* Bounded: a few attempts, further apart each time, so a permanent fault costs little.

## Considered Options

* Keep it as it is: one attempt, the failure stays in the report.
* Retry inside the scan: wait and call again before the scan finishes.
* Forget the content hash after a failed review, so the next periodic rescan scans and reviews the component again.
* Record the pending review as a fact in the component's state and retry it with the status heartbeat, with backoff
  and a bound.

## Decision Outcome

Chosen option: the fourth option.

* `run_ai_review()` returns its outcome as a fact besides the finding: `done`, `skipped` (no entity to try according
  to `ai_plan()`, or no token), `unreachable` or `failed`. `ai_call_failure()` sorts a failed call by exception class
  and HTTP status: HTTP 500, 502, 503 and 504, time-outs and connection errors are `unreachable`; any other HTTP
  status (400, 401, 403, 404) and an answer that is not JSON are `failed`. HTTP 500 is included because Home
  Assistant answers with it when the service fails, and a model that is down fails the service; a permanent server
  error is therefore retried too, within the bound.
* After an `unreachable` review the scan acts on the static verdict as before and stores
  `ai_pending = {attempts, next_at, reason, is_new}` in the component's state. A component that was quarantined gets
  no such fact: it is out of Home Assistant's reach and the AI cannot lower a verdict.
* With every status heartbeat (every 15 minutes), after asking Home Assistant what it offers, `retry_ai_reviews()`
  goes through the pending reviews; `ai_retry_action()` decides: `drop` when the component is gone or quarantined or
  when `ai_plan()` is `off`, `no_ai_task_entity` or `entity_missing`; `wait` before `next_at`, and while Home
  Assistant did not answer the heartbeat (`unknown`, so no attempt is used up); otherwise `retry`.
* A retry scans the component again and runs the review. With an answer, the result goes through
  `act_on_verdict()`, the same `decide_action()` path and notifications as a scan, with `is_new` as the scan found
  it: a component that was new is quarantined when the AI's verdict reaches the threshold. If the content changed in
  the meantime, the fact is dropped and the component is scanned like any change.
* Backoff and bound: the next attempt comes 15 minutes, 1, 4 and 12 hours after the 1st to 4th failed attempt; after
  the 5th failed attempt the review is given up and logged, and the static verdict stands.
* The status sensor lists the components waiting in `ai_review_pending`.
* Repository pre-checks are not retried: the download is deleted after the scan, and the operator can ask again.

The second option was not chosen because the scan would block the watcher for as long as Home Assistant restarts,
while the new component waits unscanned. The third option was not chosen because it is unbounded, repeats the whole
scan on every rescan, and loses whether the component was new, so a later verdict would only notify.

### Consequences

* Good, because a review lost to a restart or a model that was briefly away is made up for, and the verdict then
  counts as it would have at the scan.
* Good, because a missing entity, a turned-off review and a refused request are not repeated.
* Bad, because until the retry answers, a new component below the quarantine threshold is in place without the AI's
  opinion; Home Assistant may load it before the retry.
* Bad, because HTTP 500 cannot tell a model that is down from a configuration that never works (for example no
  preferred AI Task entity); the latter costs up to four more calls before it is given up.
* Bad, because a retry repeats the static scan (bandit, pip-audit) to build the prompt, since findings are not
  stored in the state.
* Bad, because a review given up after the fifth attempt is only in the log and the report; nothing tries again until
  the content changes.

### Confirmation

`TestAiRetryPolicy` and `TestAiRetryFlow` in `marketplace_guard/tests/test_marketplace_guard.py`: failure kinds from status and
class only, backoff and bound, `drop`/`wait`/`retry`, no retry for `no_ai_task_entity` or HTTP 400, and a 502 at the
scan followed by a retry whose malicious verdict quarantines the new component and notifies.

Accepted by the maintainer on 2026-11-07; implemented in pull request #7.
