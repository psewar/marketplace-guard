---
status: accepted
date: 2026-06-08
decision-makers: maintainer
---

# A component's own backend is not a finding

Backfilled on 2026-11-02, decided on 2026-06-08. Sources: the maintainer's question of 2026-06-08 whether a product-key
call to the vendor of a cloud integration can be recognised as legitimate, `marketplace_guard/DOCS.md` ("Scan layers").

## Context and Problem Statement

Most cloud integrations talk to their vendor, and many store the user's credentials for that vendor or activate a
product key there. Rated as outbound traffic or credential handling, every such integration looked suspicious. Weak
hashes such as MD5 used for non-security purposes raised the verdict in the same way.

## Decision Drivers

* Findings should drive the verdict only when they are malware signals.
* Fewer false positives keep notifications meaningful.

## Considered Options

* Rate every outbound host and credential use as a risk.
* Treat outbound hosts as informational; recognise the vendor's own backend; rate code-hygiene findings low.

## Decision Outcome

Chosen option: the second (the maintainer, 2026-06-08).

* Outbound hosts are informational and never raise the verdict.
* A host that matches the repository owner is relabelled `vendor-host` ("own backend").
* Crypto-hygiene findings of bandit (for example MD5) are `low`.
* The AI prompt says that calls to the component's own documented vendor API and storing credentials for that same
  vendor are normal; only unrelated third parties, telemetry, raw-IP or webhook destinations count.

### Consequences

* Good, because ordinary cloud integrations no longer trigger notifications.
* Bad, because a malicious author who sends data to their own domain is not caught by the host check; that is left to
  the other heuristics and the AI.
* Bad, because a vendor domain that does not contain the owner's name is not recognised; the operator can name it in
  `ai_prompt.txt` ([ADR-0004](0004-operator-guidance-for-the-ai-in-a-file-read-on-every-scan.md)).

### Confirmation

`TestVendorHostRelabel` in `marketplace_guard/tests/test_marketplace_guard.py`.
