# EntropyTrade — current status

Updated 2026-10-26. R0 `c7ad278`, R1 `e2c1448`, R2 `b9cbaa8` and R3 `624d442`
remain recoverable on their original branches. R3 was integrated into main before R4.

## Objective and checkpoint

**V1 is incomplete. Finish acceptance of the existing milestone before new features.**
The starting checkout was clean on `supervisor/20261025-014400` at reviewed commit
`99e2fbc1b54d6af426496b3effbe7c47255650bd`. That commit includes the local workbench and
Bitcoin forward adapter; earlier statements that the implementation was uncommitted are
obsolete. Local `main` remains the R4 checkpoint `30bed8e`; no remote freshness is claimed.
All Git mutations belong to the supervisor. No branch, index, commit, merge or push was changed.
Production trading remains disabled.

## Current acceptance continuation

The [current receipt](data/workbench-review/20261025T191200Z/README.md) binds checks to the
reviewed commit, tree, UTC clocks and a manifest of 2,268 exported files. A fresh read-only
source export and new virtual environment use the unchanged lockfile. No independent Git
checkout was created; the supervisor's final clean-checkout sign-off remains required.
The uncommitted acceptance repair serializes job-database connections across in-process
threads and Jobs instances. An approved baseline run stalled with main and queue threads
blocked in native SQLite connection close; the [stack sample](data/workbench-review/20261025T191200Z/pytest-sample.txt)
and terminated-run receipt preserve that failure. A bounded four-thread regression with
1,600 real connection cycles passes. The [candidate checks](data/workbench-review/20261025T191200Z/candidate-checks.json)
and hashed two-file code patch are separate from the frozen reviewed commit. No baseline
full-check success is inferred from the older passing suite.

The fixed candidate passes the full unchanged `make check`: Ruff lint/format, strict mypy
across 477 files and **734 pytest tests in 155.88 seconds**, with no skips or weakened tests.
JavaScript syntax and all nine frontend presentation tests also pass. Locked sync passes;
the candidate patch and source manifest are retained separately from the reviewed commit.

The [restored project context](PROJECT_CONTEXT.md) maps implemented capability to the user's
V1 gates rather than older milestone numbering.

Browser acceptance remains **blocked**: Computer Use lists no connected browsers,
Chrome returns “Computer Use was not approved to use Google Chrome,” and the in-app
browser returns “Browser is not available: iab.” No new browser job IDs, screenshots,
visual inspections or browser downloads exist. Every documented browser workflow remains
pending, including visible acquisition failures and synthetic labeling on every result tab,
protected holdout, active cancellation, worker reuse and restart/history. HTTP and DOM-double
checks do not satisfy that requirement. No approval bypass was attempted.

All 197 pre-existing receipt checksums passed before documentation reconciliation. Five
retained reviews and 51 workflow artifacts were rechecked, including public manifests,
validation-only probabilities, excluded holdout, synthetic negative-control zero fills,
closed Bitcoin settlement gates, clocked failures and matching reports. Retained HTTP
lifecycle evidence verifies active cancellation, worker reuse and interrupted restart
history with identical exports. These are rechecked historical HTTP/worker results, not
new browser workflows.

The committed interface supports local signal templates or complete AND-only comparisons,
recorded/public/synthetic modes, bounded isolated workers, durable history/cancellation,
protected reviews and same-origin downloads. All result tabs and text reports expose public
acquisition completeness, receipt/contract/observation counts and clocked failure summaries.
Bitcoin remains forward-only: authority mentions are unverified provenance, settlement
sources stay empty, settlement basis unresolved and every `rules_known` gate false.
No real-data model performance or returns follow from either family's forward ingestion.

See [operation and browser acceptance](docs/workbench.md), the
[check receipt](data/workbench-review/20261025T191200Z/clean-root/checks.json) and
[retained evidence](data/workbench-review/20261025T191200Z/retained-evidence.json).

## Delivered capabilities

- Read-only Kalshi collection, restart-safe recording, integrity/freshness health,
  generic actual-contract discovery and reproducible Parquet datasets remain intact.
- Forward Open-Meteo/NWS capture, causal feature matrices and event-level temperature
  distributions feed contract probabilities through the existing R2 modeling pipeline.
- Configurable PydanticAI research uses bounded, read-only evidence and full-spec criticism,
  followed by independent validation. Real providers require explicit opt-in and a dedicated key.
- `research-and-test` joins research → typed candidates → feature/model selection → temporal
  predictions → deterministic replay → forecast/trading validation → comparison and artifacts.
  Explicit offline and synthetic modes never masquerade as provider-backed empirical research.
- The bounded interpreter supports actual ticker/event/series selection, UTC/date entry
  windows, YES/NO, comparisons, versioned features/models, net edge, price/spread/size limits,
  fixed contracts/dollars, position caps, settlement and simple predicate exits. Hedging,
  Kelly, resting orders and holding-duration exits are rejected explicitly.
- Replay processes books, decisions, latency, fills and settlements chronologically. It
  bounds book age/split/close/expiry, consumes shared depth, reserves pending capital and
  passes actual event exposure to risk. Partial/unfilled remainders cancel; all fills are
  simulations. Optimistic/base/conservative scenarios expose execution sensitivity.
- Experiments preserve date/event grouping, separate calibration/validation, pre-holdout
  walk-forward diagnostics, protected final holdout, minimum evidence gates, date-block
  intervals and search counts. Rankings use validation Brier, with tied scores sharing rank;
  synthetic P&L never ranks or promotes candidates. No lifecycle promotion occurs.
- The existing SQLite Registry, local MLflow and Parquet/JSON artifacts retain prompt,
  hypothesis/spec, model/feature/data/code/config identities, predictions, orders/fills,
  equity, fees, criticisms and rejections. Identical inputs replay the same experiment ID.
- Family-neutral samples/prediction-provider registration and evidence projections are
  tested with a controlled non-weather mentions fixture; real mentions ingestion is absent.

## Evidence and checks

R4 final `make check`: **626 tests passed in 233.31s**, Ruff lint/format clean and
strict mypy clean (463 files). All 595 R3 tests remain, with 31 new R4 cases covering
chronology/capacity/risk, execution semantics, provenance/cutoffs, family adapters,
artifact accounting and end-to-end replay. Two old expectations now supply explicit
fixture fees and recognize supported spread limits; no invariant was weakened.
Frozen CLI reports are in [data/r4-demo](data/r4-demo/README.md) and the
[experiment guide](docs/experiments.md).

- **Real historical integration:** 36 contracts/six Philadelphia+Chicago city/day events
  across three dates. Zero eligible historical forecasts/scalar-temperature labels, no
  sized books or certified historical fees/rules. The integrated offline research run
  returns insufficient-data/unsupported candidates, without fitted empirical models,
  forecasting metrics, fills, P&L or a profitable-strategy claim.
- **Synthetic integration:** 240 date blocks/480 city-day events exercise R2 fitting,
  predictions, four mock research candidates, execution scenarios, statistical diagnostics,
  rankings, negative-control rejection and persisted artifacts. This verifies software;
  it does not establish an empirical Kalshi advantage. Final holdout remains untouched.
- **Provider/feed status:** no dedicated research or Kalshi read key is configured here.
  Live LLM research and authenticated sustained WebSocket collection remain unverified.
- **Forward weather evidence unchanged:** three real polls/restart on October 24 retained
  18 receipts, four provider/location vintages and 648 hourly points. October captures
  cannot backfill September features. This is not a multi-day operating deployment.

## Remaining limitations

Actual aligned forecast vintages, historical rule evidence, source-matched scalar highs,
independent events, sized books and effective fee evidence are still required for real
strategy evaluation. Weather Company settlement cannot be replaced by NWS CLI.
Snapshot simulation does not model queues, exchange competition or observed fills. Capacity
resets on a changed snapshot/advancing sequence are explicit assumptions. Equity between
settlements uses cost basis; reported drawdown is not a market-marked drawdown. Selection
intervals are descriptive after repeated searches, not a corrected discovery guarantee.

No production order transport or trading credentials were added. Legacy artifacts and
previous recovery branches are preserved. No real strategy is approved or validated.

## Exact next action

Return for review with the concrete browser-access blocker. Once an approved browser is
available, execute every step in `docs/workbench.md`, retaining UTC clocks, job IDs,
screenshots and checksummed browser downloads. The supervisor must verify the final
reviewed commit from a clean checkout with locked dependencies and full backend/frontend
checks before integration. Do not create branches, stage, commit, merge or push in this
continuation. Official Bitcoin outcomes/history and continuous paper/shadow are later work;
V1 cannot be declared complete without its remaining product gates.
