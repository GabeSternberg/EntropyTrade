# EntropyTrade project context

Updated 2026-10-26. **V1 is incomplete; this milestone remains in acceptance review.**
Finish the existing milestone before starting another feature phase. The current user
instruction reserves branches, commits, merges and pushes for the supervisor and forbids
changes to supervisor control files. The job-database repair and bounded concurrency
regression are now committed in `ff3bcc9`. This continuation rechecks browser access and
reconciles verification documentation; it adds no product scope. Production submission, real-money orders and live execution activation remain
disabled. No credential discovery or access is authorized.

## Verified baseline

The checkout was clean at the start of this acceptance attempt on
`supervisor/20261025-014400`, at reviewed commit
`ff3bcc9df40534396c774146405b4658f22f9753` (tree
`04ec1334c8f931dc5970582eebc6e074c1a1c3ba`). Local `main` is R4 commit
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

See the [current receipt](data/workbench-review/20261026T041240Z/README.md),
[historical baseline command clocks](data/workbench-review/20261025T191200Z/clean-root/checks.json)
and [rechecked retained evidence](data/workbench-review/20261025T191200Z/retained-evidence.json).
The historical baseline attempt used an immutable read-only source export of `99e2fbc` and
fresh locked dependencies. Its ordinary full check has five sandbox-denied listener failures;
the listener-approved baseline then stalled with two threads in native SQLite connection
close and was terminated. This is not a passing reviewed-commit gate.

The acceptance fix committed in `ff3bcc9` serializes each Jobs connection's open/use/close within a
process, across Jobs instances; separate workers retain SQLite transaction locking. A bounded
four-thread regression with 1,600 real connection cycles passes. The source overlay is limited
to `api/jobs.py` and its integration test. The [candidate checks](data/workbench-review/20261025T191200Z/candidate-checks.json)
and [code patch](data/workbench-review/20261025T191200Z/candidate.patch) identify the then-uncommitted
candidate separately from current commit verification. The [current source comparison](data/workbench-review/20261026T041240Z/source.json)
verifies that the exact repair patch and both Python files match those retained hashes.

The historical fixed candidate passed locked sync and full `make check`: Ruff lint/format, strict
mypy across 477 files and 734 pytest tests in 155.88 seconds. JavaScript syntax and all
nine frontend tests passed. No test was skipped or weakened. This source-export verification
does not replace the supervisor's final independent clean-checkout sign-off.

All 245 existing bundle checksums passed before this documentation update; the earlier
receipt verified 197 pre-existing checksums.
Five retained real/synthetic/failed-acquisition reviews, 51 workflow artifacts and their
public manifests were rechecked, including validation-only probability projections,
excluded final holdout, synthetic negative-control zero fills, closed Bitcoin settlement
gates, clocked acquisition failures and matching exported reports. Retained HTTP lifecycle
receipts verify active cancellation, worker reuse and interrupted restart history with
identical exports. These checks do not constitute new browser workflows.

## Concrete blocker and next action

Computer Use lists no connected browsers. Chrome access returns
`Computer Use was not approved to use Google Chrome`; creating an in-app tab returns
`Browser is not available: iab`. Automatic approval review rejected a repeat Chrome probe
because access had already been denied. No further browser attempts or workaround followed.
There are no new browser
job IDs, screenshots or browser downloads, and no visual acceptance is claimed.

Return for review with this blocker. Once an approved browser is available, execute every
step in [the browser procedure](docs/workbench.md#browser-acceptance-procedure), retaining
UTC clocks, job IDs, screenshots and checksummed browser downloads. Include visible failure
summaries and synthetic labeling on all tabs, protected holdout, active cancellation, worker
reuse and restart/history. The supervisor must verify the final reviewed commit from a clean
checkout with locked dependencies and full checks before integration. Do not start another
major milestone or enable trading as part of this acceptance repair.
