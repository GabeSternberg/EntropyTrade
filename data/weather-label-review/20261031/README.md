# Integrated forward weather-label acquisition — October 31, 2026

Implemented in place on `supervisor/20261031-050653`, starting at `a473758`.
Git operations and independent approval belong to the supervisor. **V1 remains incomplete.**

The existing retained-weather website now queues bounded, credential-free public settlement
source acquisition, persists raw source bytes and partial progress, shows label clocks,
rule bindings and refusals, and freezes compatible observations into a new immutable
research dataset. Loading that dataset reparses source receipts and checks the original
contract/rule bindings, audit and observations offline. Protected labels remain excluded.
Original source receipts, forecast clocks, holdout boundaries and risk/submission limits
are preserved. The website now remembers the selected weather dataset across reloads.

## New authentic evidence

The final [managed-Chromium browser receipt](browser-verified/weather-label-browser-receipt.json)
records **2026-10-31 09:21:46–09:22:06 UTC** actual localhost interactions and new public
acquisition, with **7 screenshots, 6 downloads and zero page errors**. It imports two original
forward forecast receipts unchanged, freezes the initial dataset, clicks acquisition,
inspects status/provenance/refusals, downloads the label batch, freezes the updated dataset,
executes normal local-template research, inspects all result tabs, and restarts the listener.
All three reopened label/review/report downloads are byte-identical. No HTTP interception,
controlled source response, browser profile, research credential or exchange credential is
used in this procedure. Chromium 141.0.7390.37 is Playwright-managed in the repository cache.

| Retained event | New official source evidence | Disposition |
|---|---|---|
| KXHIGHCHI-26OCT29 | CLIMDW → MDW/KMDW, official `maxTemp=69` °F | Verified scalar observation; available only at 2026-10-31T09:21:51.917194Z receipt |
| KXHIGHPHIL-26OCT29 | CLIPHL → PHL/KPHL, official `maxTemp=70` °F | Verified scalar observation; same new receipt |
| KXHIGHCHI-26OCT30 | Matching station, provider `status=preliminary`, `isOfficial=false` | Refused; exact response retained at 2026-10-31T09:21:51.970218Z |
| KXHIGHPHIL-26OCT30 | Matching station, provider `status=preliminary`, `isOfficial=false` | Refused; same new receipt |

These responses come from the official portal's public
`https://weather.com/kalshi/api/climate/primary?date=YYYY-MM-DD` endpoint.
Provider issue/revision timestamps are absent for these records and remain null. No
availability is inferred from target dates or HTTP headers. The downloaded
[label batch](browser-verified/weather-labels.json) retains full exact response bytes as
base64, HTTP metadata, source dataset, target rule hashes and parser identifier. Its
receipt hashes differ legitimately from earlier discovery probes when other station
reports change; earlier bytes/clocks remain untouched in [probe](probe/).

The updated dataset contains **2 source-matched scalar-label events**, 4 independent
weather events on 2 dates, and **0 binary-label events**. Its fixed model minimums and
independent-date requirements still refuse fitting. The [actual review](browser-verified/weather-review.json)
has no model probabilities, no tested/scenario candidates and no final-holdout evaluation.
**No fitted empirical model, return, trading fill or profitability is claimed.**

## Executed verification

- [Ruff lint](ruff.log), [Ruff format](format.log): pass; 542 backend files formatted.
- [Strict mypy](mypy.log): pass, 542 source/test files.
- [Frontend regressions](frontend.log): all 22 named checks pass using direct Node execution.
- [Focused label/listener tests](label-tests.log): **28 passed in 12.69s**. Tests include authentic-byte offline parsing plus explicitly controlled malformed/preliminary/wrong-source/wrong-station/date/unit, late/corrected/protected labels, per-cutoff revision selection, HTTP/network/redirect/byte-budget refusals, active shutdown, restart/idempotency, CSRF/scope, semantic-audit tampering and portable restore.
- [Earlier history/cohort focus](focused.log): 42 passed in 72.39s before the final replay/shutdown additions. It retains its original scope; it is not a second current full-suite pass.
- Final [browser log](browser-verified.log), [Playwright report](browser-verified/playwright-results.json), [screenshot/download hashes](browser-hashes.json): pass, 13 hashes verified and 3 identical reopened-download pairs.
- [Authentic offline snapshot/restore](offline-replay.json): pass. The stopped final browser workspace restores without network; its acquisition request, batch hashes and both immutable datasets match exactly, with scalar-label counts 0 and 2. Source bytes and rule bindings reparse offline. This is file/store verification, not another browser session.
- [Safety hashes](safety-receipt.json): all **68 original receipt files and 5 Bitcoin boundary files** unchanged against the earlier verified operating baseline.
- [Source fingerprints](source-hashes.json): 558 implementation/test/frontend source files recorded for this verification.
- [Complete pytest suite](full-suite.log), [JUnit](full-suite.xml): **1,255 passed in 609.09s**, zero failures/errors/skips. The [scoped acceptance receipt](acceptance.json) records this result while keeping V1 `complete=false` and independent supervisor approval pending.

The first [browser attempt](browser-attempt-1/weather-label-browser-receipt.json) failed on
dataset selection after restart. It had acquired authentic labels successfully, and its
failure/trace/screenshots remain failed and unchanged. The UI now persists a valid selected
dataset; [the next run](browser-final/weather-label-browser-receipt.json) passed. Final
`browser-verified` also exercises the subsequent stronger offline label/rule/audit replay
and active-shutdown implementation. No passing receipt replaces an earlier failure.

The restricted environment denies both localhost sockets and socketpair sends, recorded in
[restricted-capabilities.json](restricted-capabilities.json). An initial restricted unit run
passed 26 cases but could not wake the active cancellation thread and raised
`RuntimeError: weather acquisition did not stop; workspace lease retained` in the new
shutdown test. The unchanged test passes in the standard approved socket-capable execution,
including the focused result above. Browser/listener/full-suite execution uses that normal
approval path; no sandbox setting, launch security flag, deadline, assertion or risk limit
is weakened. Supported Chromium provisioning succeeds in the repository cache. One initial
provisioning command omitted the cache environment variable and was interrupted at 0%; the
correct repository-scoped supported command is the one used for browser acceptance.

## Reproduction and retention

Use a fresh workspace/evidence path for every browser run:

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
env -u NODE_TEST_CONTEXT node frontend/tests/acquisition.test.cjs
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -vv
cd frontend/browser
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" npm run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE=/absolute/repo/data/weather-label-review/NEW \
ENTROPYTRADE_BROWSER_WORKSPACE=/absolute/repo/data/cache/NEW \
ENTROPYTRADE_BROWSER_PYTHON=/absolute/repo/.venv/bin/python \
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" npm test -- weather-labels.spec.cjs --max-failures=1
```

Future source reports may change; the immutable receipts here preserve precisely what was
available during this execution. Browser provisioning/launch and localhost listener access
must be permitted. A fresh installation is **not** claimed by this milestone; the existing
locked environment is reused, and prior clean-install acceptance keeps its earlier scope.

[retained-artifacts.json](retained-artifacts.json) records **108 original generated files,
30,823,291 bytes**, including the 16,353,420-byte authentic workspace archive and all three
attempts' trace trees. These bytes remain at their original local repository paths and are
excluded from staging by the narrowly scoped parent `.gitignore`. Reports, screenshots,
source receipts and downloads remain reviewable. A checkout alone cannot open these local
traces or restore the archive; independent review must obtain and hash-verify the listed
bytes. No archive/trace is deleted, retimed or represented as remotely available.

```bash
.venv/bin/python data/weather-label-review/20261031/verify_evidence.py
```

The read-only verifier checks current source hashes, original receipts/Bitcoin boundaries,
all final screenshot/download hashes, reopened equality and every retained local byte.
Hash verification does not itself execute browser acceptance or establish source authenticity.

All user-facing acceptance steps for this scoped acquisition milestone executed. Independent
supervisor review remains required. More authentic independent dates, realistic empirical
validation, certified effective fees, separately authorized provider verification, a second
meaningfully distinct validated family and final V1 release review remain open. Another
major family requires user approval. No Git mutations, credentials, real orders or execution
activation are part of this work.
