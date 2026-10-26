# EntropyTrade project context

Updated 2026-10-26. **V1 is incomplete; this milestone remains in acceptance review.**
Finish the existing milestone before starting another feature phase. The current user
instruction reserves branches, commits, merges and pushes for the supervisor and forbids
changes to supervisor control files. This continuation repairs an acceptance-discovered job-database deadlock, adds a bounded
concurrency regression and reconciles verification documentation; it adds no product scope. Production submission, real-money orders and live execution activation remain
disabled. No credential discovery or access is authorized.

## Verified baseline

The checkout was clean at the start of this acceptance attempt on
`supervisor/20261025-014400`, at reviewed commit
`99e2fbc1b54d6af426496b3effbe7c47255650bd` (tree
`9c0cb3a82666def58d75594a13e3bd62fe906b63`). Local `main` is R4 commit
`30bed8e30cf07201124deee609a21f7f01e47735`. No remote freshness is claimed.
The reviewed commit already includes the local workbench and Bitcoin forward adapter;
earlier documentation describing them as uncommitted is stale. Historical receipts remain
unchanged records of their own source state and UTC clocks.

## Product gates

The user's current V1 sequence takes precedence over older milestone numbering in
`docs/roadmap.md` (which labels the website R5 and second family R6).

| User-directed gate | Evidence-backed status |
| --- | --- |
| R5: research → typed strategy → model/experiment → honest result | Implemented in R4's `research-and-test` CLI. Real weather returns explicit insufficiency; synthetic inputs separately exercise fitting, calibration and replay. No empirical advantage established. |
| R6: minimal private web interface and jobs | Implemented at the reviewed commit: localhost-only templates, queue/progress/history, protected reviews and downloads. Actual HTTP/worker evidence exists. All documented browser workflows remain unexecuted because browser access is unavailable. |
| R7: second materially distinct family | Bitcoin has actual retained KXBTC rules/receipts and Coinbase spot covariates through shared adapters. Forward ingestion only: settlement basis unresolved, `rules_known=false`, verified settlement sources empty, no historical outcomes or fitted/evaluated model. This is partial second-family coverage, not complete empirical integration. Real mentions ingestion is absent. |
| R8: continuous paper/shadow tracking | Not delivered as an integrated continuous workflow. Existing paper execution/ledger primitives do not satisfy this gate. Deferred beyond the current acceptance scope. |
| V1 complete | **No.** Browser usability acceptance, usable second-family history/semantics/evaluation and continuous paper/shadow remain open. No strategy is approved or validated on real data. |

The real historical weather evidence contains 36 contracts across six city/day events and
three dates, with zero eligible historical forecast/scalar-label pairs. Forward source
receipts cannot backfill earlier decisions. Weather Company settlement cannot be replaced
by NWS CLI, and Coinbase spot cannot become a Bitcoin settlement label. Final holdout is
excluded from research and review projections; synthetic performance is software evidence.

## Current acceptance evidence

See the [current receipt](data/workbench-review/20261025T191200Z/README.md),
[command clocks and commit identity](data/workbench-review/20261025T191200Z/clean-root/checks.json)
and [rechecked retained evidence](data/workbench-review/20261025T191200Z/retained-evidence.json).
The baseline attempt uses an immutable read-only source export of the reviewed commit and
fresh locked dependencies. Its ordinary full check has five sandbox-denied listener failures;
the listener-approved baseline then stalled with two threads in native SQLite connection
close and was terminated. This is not a passing reviewed-commit gate.

The uncommitted acceptance fix serializes each Jobs connection's open/use/close within a
process, across Jobs instances; separate workers retain SQLite transaction locking. A bounded
four-thread regression with 1,600 real connection cycles passes. The source overlay is limited
to `api/jobs.py` and its integration test. The [candidate checks](data/workbench-review/20261025T191200Z/candidate-checks.json)
and [code patch](data/workbench-review/20261025T191200Z/candidate.patch) identify this candidate
separately from the reviewed commit.

The fixed candidate passes locked sync and full `make check`: Ruff lint/format, strict
mypy across 477 files and 734 pytest tests in 155.88 seconds. JavaScript syntax and all
nine frontend tests pass. No test was skipped or weakened. This source-export verification
does not replace the supervisor's final independent clean-checkout sign-off.

All 197 pre-existing bundle checksums were verified before documentation reconciliation.
Five retained real/synthetic/failed-acquisition reviews, 51 workflow artifacts and their
public manifests were rechecked, including validation-only probability projections,
excluded final holdout, synthetic negative-control zero fills, closed Bitcoin settlement
gates, clocked acquisition failures and matching exported reports. Retained HTTP lifecycle
receipts verify active cancellation, worker reuse and interrupted restart history with
identical exports. These checks do not constitute new browser workflows.

## Concrete blocker and next action

Computer Use lists no connected browsers. Chrome access returns
`Computer Use was not approved to use Google Chrome`; creating an in-app tab returns
`Browser is not available: iab`. No approval bypass was attempted. There are no new browser
job IDs, screenshots or browser downloads, and no visual acceptance is claimed.

Return for review with this blocker. Once an approved browser is available, execute every
step in [the browser procedure](docs/workbench.md#browser-acceptance-procedure), retaining
UTC clocks, job IDs, screenshots and checksummed browser downloads. Include visible failure
summaries and synthetic labeling on all tabs, protected holdout, active cancellation, worker
reuse and restart/history. The supervisor must verify the final reviewed commit from a clean
checkout with locked dependencies and full checks before integration. Do not start another
major milestone or enable trading as part of this acceptance repair.
