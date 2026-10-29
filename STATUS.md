# EntropyTrade — current status

Updated 2026-10-28. R0 `c7ad278`, R1 `e2c1448`, R2 `b9cbaa8` and R3 `624d442`
remain recoverable on their original branches. R3 was integrated into main before R4.

## Objective and checkpoint

**V1 and second-family empirical acceptance remain incomplete. Actual Bitcoin result
reconciliation and retained-real-receipt browser acceptance now pass.** This continuation
started clean on `supervisor/20261028-201233` at `97074a3`. Local `main` also points to
that supervisor checkpoint and contains the earlier R4/website/history work; no remote
freshness is claimed. No Git mutation or credential access was performed.

The [current evidence](data/bitcoin-history-review/20261029T001500Z/README.md) retains
four successful exact official result GETs, all finalized NO with matching payouts,
settlement clocks and frozen contract terms. Inventorying all eight original workbench
Bitcoin captures still yields four independent events across three dates. The new labels
became available at their October 29 receipt times; earlier decisions remain unchanged.
The [history workflow](docs/bitcoin-history.md) now shows the exact fitting/validation
counts, shortages, classes and fixed windows on every tab and in both downloads.

An actual Playwright-managed Chromium check passed against the real localhost server
and unmodified worker using imported **real retained receipts**, with no response stubs
or simulated clocks. Form submission, all three tabs, four screenshots, four checksummed
downloads, server restart and identical reopened bytes passed; zero page errors. Two
independent experiment replays produced the original identity and serialized refusal
results. This verifies honest insufficiency, not fitted empirical performance. The
[October 28 controlled continuation](data/bitcoin-history-review/20261028T235347Z/README.md)
also remains valid: 752 pytest tests and two controlled/empty browser procedures passed
there with permitted sockets. Older sandbox-denial logs are historical failed attempts.

The evaluated snapshot has 4/40 fitting events on 3/20 dates, only NO outcomes and
0/20 validation events on 0/10 dates. Frozen validation is December 24, 2026 through
January 22, 2027; ten validation dates cannot exist before January 2. A separate one-shot
source probe succeeded (three HTTP 200 receipts, 318 contracts, one spot observation,
three pending forward samples). Current public access is feasible, but today's downloads
cannot manufacture earlier receipt history or future validation. Longitudinal capture or
a separately reviewed archive requires a user decision. No partition boundary was moved.

Current `make check` passed: Ruff lint/format, strict mypy across 483 files and
**754 pytest tests in 269.06 seconds**, with no skips. All 12 frontend checks passed.
The real browser procedure passed in 19.1 seconds; the independent receipt/determinism
verifier passed. These are working-checkout checks; no clean install is claimed.

Continuous paper/shadow, final V1 acceptance and clean-install release evidence remain
deferred. Trading scenarios and P&L remain closed without certified rules, depth and fees.
The supervisor owns independent review, clean-checkout verification and every Git write.
No production submission or real order was enabled.

## October 26 acceptance record

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

Review [the executed real-data evidence and concrete blocker](data/bitcoin-history-review/20261029T001500Z/README.md).
Choose whether to operate original forward capture and official-result reconciliation
through the frozen fit/validation windows, or supply an independently retained archive
for separate provenance review. Missing events/dates and the single outcome class cannot
be repaired by later receipt backdating or moving protected boundaries. Stop here for
that decision; further abstractions do not close the elapsed-history gap. Continuous
paper/shadow and the final V1 matrix remain subsequent reviewed work.
