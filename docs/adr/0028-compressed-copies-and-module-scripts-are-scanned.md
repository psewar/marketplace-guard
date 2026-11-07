---
status: accepted
date: 2026-11-06
decision-makers: maintainer
---

# Compressed copies and module scripts are scanned

## Context and Problem Statement

Dashboard cards live in `www/community` and reach the browser through Home Assistant's web server. Its static file
handler (aiohttp's `FileResponse`, `ENCODING_EXTENSIONS` = `.br`, `.gz`) sends `x.js.br` or `x.js.gz` instead of
`x.js` to a browser that accepts the encoding. The Marketplace writes a `.js.gz` next to every `.js` it installs
(`homeassistant/components/marketplace/base.py`, tag 2026.11.0), and HACS did the same. HACS Guard scanned and hashed
only `.js`: a copy with other content — shipped by the repository or written later — ran in the browser unseen, and
changing it did not even trigger a rescan. Scripts loaded as ES modules (`.mjs`, `.cjs`) were neither scanned nor
hashed either.

## Decision Drivers

* Scan what the browser receives, not only what the folder shows.
* The copy the Marketplace writes itself must not be a finding.
* Use the standard library only.

## Considered Options

* Scan `.gz` copies as JavaScript in every case.
* Compare each `.gz` copy with its script: an identical copy is fine; a different one is a finding and its content is
  scanned. Report `.br` copies, which the standard library cannot decompress and the Marketplace never writes.

## Decision Outcome

Chosen option: the second option.

* `precompressed_findings()` decompresses each `.js.gz`, `.mjs.gz` and `.cjs.gz` up to `MAX_SCAN_BYTES`. When it
  differs from the script next to it, that is a `high` finding `precompressed-differs`, and its content is scanned as
  JavaScript; without a script next to it, the content is only scanned. A copy that does not decompress is `info`.
* A `.js.br`, `.mjs.br` or `.cjs.br` is a `high` finding `precompressed-unreviewable`.
* `.mjs` and `.cjs` are scanned as JavaScript; the hash covers them, `.gz`, `.br` and HTML files.

### Consequences

* Good, because the browser cannot get code the scan did not see, and changing a copy triggers a rescan.
* Good, because the Marketplace's own copies stay quiet.
* Bad, because a card edited by hand without its `.gz` copy is reported as `high` until the copy is renewed — which is
  correct: the browser gets the old content.

### Confirmation

`TestPrecompressed` in `marketplace_guard/tests/test_marketplace_guard.py`: the Marketplace's copy is quiet; a different copy is
`high` and its content is scanned; `.br` and broken copies are reported; a `.mjs` script is scanned and changes the
hash.

Accepted by the maintainer on 2026-11-06; implemented in pull request #24.
