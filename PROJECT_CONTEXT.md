# EntropyTrade project context

Updated 2026-10-26. **V1 is incomplete; this milestone remains in acceptance review.**
Finish the existing milestone before starting another feature phase. The current user
instruction reserves branches, commits, merges and pushes for the supervisor and forbids
changes to supervisor control files. The job-database repair and bounded concurrency
regression are now committed in `ff3bcc9`. This continuation executes the documented browser
acceptance with isolated Playwright Chromium, preserves real evidence and reconciles
documentation; it adds no product scope. Production submission, real-money orders and live
execution activation remain disabled. No credential discovery or access is authorized.

## Verified baseline

The checkout was clean at the start of this acceptance attempt on
`supervisor/20261025-014400`, at reviewed commit
`18be50cee17f03ae3dbfa198ed22e7a23635af1b` (tree
`529aaaa9802045b1dcf9dc6a99235c6634b7fd28`). Local `main` is R4 commit
`30bed8e30cf07201124deee609a21f7f01e47735`. No remote freshness is claimed.
The reviewed commit includes the local workbench, Bitcoin forward adapter and SQLite
acceptance repair. The earlier `99e2fbc` baseline and uncommitted-candidate receipts remain
unchanged records of their own source state and UTC clocks.

## Product gates

The user's current V1 sequence takes precedence over older milestone numbering in
`docs/roadmap.md` (which labels the website R5 and second family R6).

| User-directed gate | Evidence-backed status |
| --- | --- |
| R5: research → typed strategy → model/experiment → honest result | Implemented in R4's `research-and-test` CLI. Real weather returns explicit insufficiency; synthetic inputs separately exercise fitting, calibration and replay. No empirical advantage established. |
| R6: minimal private web interface and jobs | Implemented at the reviewed commit: localhost-only templates, queue/progress/history, protected reviews and downloads. All four documented browser workflows passed with Playwright Chromium against the real backend: results/tabs, public success/failure, downloads, cancellation, worker reuse and restart persistence. Supervisor review remains required. |
| R7: second materially distinct family | Bitcoin has actual retained KXBTC rules/receipts and Coinbase spot covariates through shared adapters. Forward ingestion only: settlement basis unresolved, `rules_known=false`, verified settlement sources empty, no historical outcomes or fitted/evaluated model. This is partial second-family coverage, not complete empirical integration. Real mentions ingestion is absent. |
| R8: continuous paper/shadow tracking | Not delivered as an integrated continuous workflow. Existing paper execution/ledger primitives do not satisfy this gate. Deferred beyond the current acceptance scope. |
| V1 complete | **No.** Documented website browser acceptance has passed; supervisor sign-off, usable second-family history/semantics/evaluation and continuous paper/shadow remain open. No strategy is approved or validated on real data. |

The real historical weather evidence contains 36 contracts across six city/day events and
three dates, with zero eligible historical forecast/scalar-label pairs. Forward source
receipts cannot backfill earlier decisions. Weather Company settlement cannot be replaced
by NWS CLI, and Coinbase spot cannot become a Bitcoin settlement label. Final holdout is
excluded from research and review projections; synthetic performance is software evidence.

## Current acceptance evidence

The [latest bundle](data/workbench-review/20261026T203717Z/README.md) binds the reviewed
commit to a clean initial working tree and a read-only 2,347-file source export. Locked
setup, Ruff lint/format, strict mypy across 477 files, **734 pytest tests in 184.91 seconds**,
JavaScript syntax and all **nine frontend tests** passed without skips. Exported source
remained unchanged. All 275 prior evidence checksums passed before documentation updates.
Application source and financial safety boundaries were not changed.

The [passing browser receipt](data/workbench-review/20261026T203717Z/browser-attempt-2/browser-receipt.json)
records all four procedures on October 26, 20:42:33–20:43:23 UTC. Playwright 1.56.1 explicitly
launches its own Chromium 141.0.7390.37 with a fresh context; Computer Use and personal Chrome
were not used. Evidence includes 26 full-page screenshots, 24 checksummed browser downloads,
JSON/JUnit results, a trace, real workflow/public artifacts and final SQLite snapshots.
Readable screenshots supplement the full pages. The first failed harness attempt is
retained separately: an invalid non-null calibration-clock assumption prevented synthetic
verification/downloads and then its restart comparison. It is not counted as a pass. The
corrected harness permits null calibration for uncalibrated outputs and checks every
present calibration clock, all fit clocks and validation-only prediction splits.

Recorded weather visibly returned insufficiency and exact Decimal comparisons with no
eligible historical features/labels or probabilities. Synthetic software evidence exposed
100 of 192 validation records and zero negative-control fills in three scenarios, with the
synthetic banner on every tab. Final holdout remained excluded. Fresh public weather
returned 8 successful HTTP receipts, 24 contracts and 648 observations. Fresh Bitcoin
returned 3 successful receipts, 210 contracts and one observation. Its 210 rule gates
remained false, verified settlement sources empty, basis unresolved and 420 authority
mentions separately unverified. Neither capture established historical model performance.

A separately labeled real backend under OS outbound-network denial produced two timestamped
Bitcoin failures and zero HTTP receipts/contracts/observations. All three tabs and downloaded
text exposed the incomplete heading, counts, clocks, failures and limitations. This is
failure-path evidence, not successful ingestion. Active synthetic cancellation, recorded-run
worker reuse, shutdown interruption, restarted history and reopening all six completed runs
passed. Parsed downloaded JSON and report bytes match retained reviews; all 12 downloads
repeated after restart match the 12 originals. One browser console resource 404 is retained;
there were no JavaScript page errors or failed workflow requests.

Earlier receipts and their original browser denials remain immutable historical evidence.
The source export is additional verification, not the supervisor's independent final
clean-checkout sign-off. The [reproducible harness](frontend/browser/README.md) performs no
Git writes and preserves previous workspaces/receipts.

## Remaining review and V1 gates

Return the concrete browser evidence and full checks to the supervisor for review,
independent final clean-checkout verification and all Git integration. No commit, merge,
push or branch/index mutation was performed in this continuation. Do not start another
major milestone or enable trading as part of website acceptance.

V1 remains incomplete: verified Bitcoin settlement semantics, official outcomes and usable
point-in-time historical evaluation remain absent, as does integrated continuous paper/shadow
tracking. Synthetic results and forward public ingestion do not validate a real strategy.
