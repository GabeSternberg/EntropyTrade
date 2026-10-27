# EntropyTrade — current status

Updated 2026-10-26. R0 `c7ad278`, R1 `e2c1448`, R2 `b9cbaa8` and R3 `624d442`
remain recoverable on their original branches. R3 was integrated into main before R4.

## Objective and checkpoint

**V1 is incomplete. Finish acceptance of the existing milestone before new features.**
The starting checkout was clean on `supervisor/20261025-014400` at reviewed commit
`18be50cee17f03ae3dbfa198ed22e7a23635af1b`. It includes the local workbench, Bitcoin
forward adapter and committed SQLite acceptance repair. The earlier `99e2fbc` baseline
and uncommitted-candidate receipts describe historical states. Local `main` remains the
R4 checkpoint `30bed8e`; no remote freshness is claimed.
All Git mutations belong to the supervisor. No branch, index, commit, merge or push was changed.
Production trading remains disabled.

## Current acceptance continuation

**All four documented browser procedures passed** with isolated Playwright Chromium and
the real localhost backend on October 26, 20:42:33–20:43:23 UTC. No Computer Use or personal
Chrome was used. The [current bundle](data/workbench-review/20261026T203717Z/README.md)
retains the passing [browser receipt](data/workbench-review/20261026T203717Z/browser-attempt-2/browser-receipt.json),
26 screenshots, 24 checksummed browser downloads, JSON/JUnit results, a trace, actual source
captures/reviews and final SQLite snapshots. Supplemental readable UI screenshots and the
first failed harness attempt are preserved separately. The failure was a harness assumption
about null calibration timestamps; no application change or weakened safety rule was needed.

Recorded weather showed typed exact comparisons, real insufficiency, empty probabilities
and excluded holdout. Synthetic mode exposed 100 of 192 validation records, banners on
all result tabs and zero negative-control fills in all three scenarios. Public weather
returned 8 successful HTTP receipts, 24 contracts and 648 observations; Bitcoin returned
3 successful receipts, 210 contracts and one observation. All Bitcoin settlement gates
remained closed, verified sources empty and 420 authority mentions separately unverified.
A deliberately OS-denied backend run separately produced two clocked acquisition failures
and zero receipts/data; its incomplete summaries remained visible on all three tabs and in
the text report. Public capture provides no historical evaluation or real-data returns.

Active cancellation, subsequent worker-slot reuse, shutdown of an active run, interrupted
restart history and reopening all six completed reviews passed. Browser JSON and report
downloads match retained protected results, with identical checksums after restart. One
browser console resource 404 is retained; no JavaScript page errors or failed workflow
requests occurred. See the [reproducible harness](frontend/browser/README.md).

An isolated read-only export of reviewed commit `18be50c` passed locked setup, Ruff
lint/format, strict mypy across 477 files, **734 pytest tests in 184.91 seconds**, JavaScript
syntax and all **nine frontend tests**, with no skips. All 2,347 exported files remained
unchanged. All 275 pre-existing receipt checksums passed. Earlier source states, HTTP-only
evidence, browser denials and SQLite stall/repair receipts remain immutable historical records.
No application source, financial safety boundary or Git ref was changed.

The supervisor must review this evidence, complete independent final clean-checkout
verification and handle every commit, merge and push. **V1 remains incomplete** because
usable second-family history/semantics/evaluation and continuous paper/shadow remain open.
See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) and [the operating guide](docs/workbench.md).

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
