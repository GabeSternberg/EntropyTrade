# EntropyTrade — current status

Updated 2026-10-25. R0 `c7ad278`, R1 `e2c1448`, R2 `b9cbaa8` and R3 `624d442`
remain recoverable on their original branches. R3 was integrated into main before R4.

## Objective and checkpoint

**R4 is the last fully verified checkpoint.** The current continuation adds a template-only
local research website and an explicit Bitcoin family extension, reusing R2–R4 engines and completing the
partial API/public-capture scaffold already present in the working tree. This implementation
has **passing full checks, real listener/worker coverage and successful weather/Bitcoin public
ingestion**. Browser acceptance is blocked by unavailable browser access. It is not a completed
empirical research product. The current instruction reserves all Git mutations for the supervisor;
no branch, staging, commit, merge or push was attempted.
Production trading remains disabled.

## Current local workbench continuation

- Buildless localhost interface: idea submission, explicit real recorded/public/synthetic
  modes, durable queue/progress/history, cancellation, candidate gates/specs, validation
  probabilities, simulated scenario diagnostics, exact rules and lineage/report downloads.
- Credential-free local formulation recognizes documented signal words and exact feature
  AND-only comparisons with an optional Test/Research prefix. The complete expression
  must match; XOR, unless, unsupported connectors, grouping and surrounding comparison
  prose are rejected. Arbitrary prose is not fully interpreted. Unsupported requests remain
  proposals with reasons. Synthetic mode retains fixed mock proposals and negative control.
  Complete numeric tokens are checked before Decimal construction; excess precision,
  scientific notation and thousands separators cannot silently become prefix thresholds.
- Weather public capture reuses forecast archives/full-local-day features. Bitcoin adds
  KXBTC rules and receipt-clock Coinbase spot/strike covariates through the same registered
  sample/provider/experiment boundary. Spot never becomes a settlement label. Authority mentions
  preserve their exact rule text/field separately from verified settlement sources, including
  negated or ambiguous mentions. All Bitcoin settlement sources and settlement basis stay
  unresolved; forward-only data cannot fit a model or create backtest returns.
  Bitcoin always keeps `rules_known=false` until complete resolution semantics are verified.
  Partial weather captures expose source response/failure clocks and stay incomplete.
- HTTP assets/jobs/reviews use a fixed route allowlist, loopback binding, same-origin and
  CSRF checks. One bounded isolated worker receives an environment allowlist. No credential
  or trading endpoints were added; no risk limits or existing tests were loosened.
- Acquisition completeness, HTTP receipt/contract/observation counts and clocked failure
  summaries now appear prominently on every result tab and in downloaded text reports.
  Empty listings and failed/partial captures cannot be presented as complete ingestion.
- **Latest verification (`20261025T163400Z`):** locked setup passes. The complete unchanged
  `make check` passes: Ruff lint/format, strict mypy across 477 files, **733 pytest tests
  passed in 154.68 seconds**. All listener cases pass with normal per-command approval.
  Five new public-worker cases verify HTTP/connection failures, partial/complete/empty
  acquisition and persisted report/settlement/evaluation boundaries. Nine Node presentation
  regressions pass across all tabs. No tests, risk limits or policies were weakened.
- Actual localhost HTTP submissions saved recorded insufficiency and synthetic replay
  (192 permitted validation records; negative control zero fills in three scenarios).
  Successful public weather ingestion retained 8 HTTP receipts, 24 contracts and 648
  observations; Bitcoin retained 3 receipts, 318 contracts and one spot observation.
  Neither family has historical evaluation or fitted empirical probabilities. Every Bitcoin
  rule gate remains false and verified settlement sources remain empty.
- Actual HTTP cancellation during modeling, worker-slot reuse, shutdown with active/pending
  jobs, interrupted restart history and identical exported review/report bytes all pass.
  A separate ordinary-sandbox Bitcoin attempt retained two clocked acquisition failures,
  zero responses/data and the new incomplete report. All 51 workflow artifact hashes and
  protected projections are rechecked. These are HTTP/worker checks, not browser acceptance.
- **Remaining gate:** Computer Use rejected Chrome access, no connected browser sessions
  were listed and the in-app browser was unavailable. Chrome access was requested. No
  browser observations, screenshots or browser downloads are claimed. All documented
  browser steps remain pending. Commit-based reproduction is reserved for the supervisor;
  HEAD remains `30bed8e`. [Receipts and checksums](data/workbench-review/README.md) retain
  precise results. No Git write, permission bypass or supervisor-control change occurred.

See [workbench operation and verification limits](docs/workbench.md).

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

Enable an approved browser and execute every browser acceptance step in `docs/workbench.md`:
recorded insufficiency, synthetic replay/negative control, both public ingestions, visible
acquisition summaries/failures on every tab, active cancellation, restart/history and
checksummed browser downloads. The automated suite and actual successful ingestion now pass.
The supervisor must commit the reviewed implementation and receipts and verify reproduction
from that commit before integration. Do not create branches, stage, commit, merge or push in
this continuation. Official Bitcoin outcomes/history and continuous shadow remain later work.
