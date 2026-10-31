# Continuous read-only shadow monitoring

October 31: cycles also maintain an isolated simulated paper account. See
[paper accounting](paper-accounting.md) for execution semantics, persistence, browser
downloads and outstanding acceptance. The historical shadow-intention layer described below
remains separate from simulated fills and balances. No exchange submissions are enabled.

Run `uv run entropytrade-web` and open `http://127.0.0.1:43128`. Complete a real
weather research run, for example `Test forecast_high_f > 70` in Recorded mode. Select
its typed candidate under **Continuous shadow tracking**, choose a poll interval, and
click **Start shadow monitor**. Inspect the frozen spec before interpreting any decision.
Insufficient research candidates may be monitored to collect evidence; monitoring never
approves or promotes a strategy. Synthetic candidates and unsupported execution semantics
are rejected. Existing Bitcoin candidates are optional; no new family is selected here.

The server runs one isolated shadow subprocess at a time, independently of the research
worker. Each cycle captures public market/source evidence through the existing bounded
GET adapters. It retains original response bytes, receipt clocks, normalized features,
listing quotes, source versions, model refusals or probabilities, intended orders,
precondition gates, risk decisions, code/dependency hashes and an immutable result digest.
Listing quotes are explicitly unsized and never treated as executable depth. See each
cycle's evidence details and **Shadow evidence JSON**. The normal view shows 20 cycles;
the download includes the full bounded history and lifecycle events. It exposes no
arbitrary filesystem reads or writes. Raw artifacts remain in the local workspace.

New weather modeling runs export data-only snapshots for climatology, raw forecast and
forecast-error models, including supported Platt/isotonic calibrators. At monitor creation,
the resolved experiment spec/model identity selects a unique checksummed export from that
server-produced research run. The snapshot freezes fit/calibration clocks, training series,
feature schema, data classification and protected events. The website shows **Frozen model
binding** and its refusal when unavailable. No live fitting or executable model deserialization
occurs. Legacy runs without exports, ridge/boosting and Bitcoin forward scoring remain blocked.
A real candidate currently has no sufficient fitted model; software tests do not establish one.

Each cycle captures up to ten public sized books and ten series fee responses through exact
GET allowlists, without exchange credentials. Fractional-strike tickers are supported. Books
use actual YES/NO bids and sizes; listing quotes remain separately labeled unsized. Decisions
follow all receipts, original feature availability stays unchanged and hours-to-close is
recomputed. The first ten lexicographically sorted contracts receive books each cycle; others
are explicitly listed as deferred. Broader/fair depth scheduling remains a limitation.
Raw source capture is bounded at 120 seconds, execution capture at 60 seconds and later
outcome lookup at 90 seconds, all within the existing four-minute worker deadline; a slow
combined cycle can therefore be interrupted and retained as a failure by that deadline.

Series fee metadata retains its raw hash, receipt clock, metadata-update time and version,
but **does not certify the coefficient or effective interval**. Fees remain uncertified and
intentions remain blocked even if a compatible frozen model can score. Missing models,
features, semantics or books also fail closed. Original shadow intentions have no observed
fills or performance claims. The separate paper account reports only simulated accounting;
authentic missing-evidence cases still have no fills. No UI endpoint imports models or
loosens risk caps. Server-reviewed fee versions are described in [fee evidence](fee-evidence.md).

Every completed collection saves `decision-inputs.json`, with targets removed and protected
records excluded using the union of dataset protection and model-metadata holdout events.
The combined boundary is retained in replay data before model metadata is replaced by its
hash, so offline replay keeps the same exclusions. Verify its artifact hashes and recompute
decisions without any network access using the local command below. This reproduces the
recorded decision computation; it does not authenticate a source or establish empirical
performance. The supplied model metadata `data_kind` is also retained; missing or invalid
values are never replaced with the dataset's classification. Legacy replay inputs that
removed this field now block on missing provenance and cannot verify their prior decision
hashes under the corrected policy. Keep those original artifacts unchanged; new cycles
retain the required field. Interrupted cycles
without input/result artifacts cannot be replayed and report that limitation explicitly.

The compiler and shadow evaluator share one probability-name resolver: an explicit
`probability_feature` must occur in the entry predicates; otherwise exactly one distinct
`*_probability` predicate name is required. `yes_bid` and `yes_ask` are reserved quote
names and cannot be probability bindings; they can still appear as quote predicates
with a separate probability binding. The validated prediction is inserted under
that exact name. A raw feature with the same name remains in `features` and its original
hash/version audit but cannot replace the model value in entry predicates or edge
calculation, even at an identical availability timestamp. Other required features keep
their existing availability/version gates. Legacy decisions affected by the former binding
bug cannot reproduce their old decision hashes under the corrected evaluator; preserve
their original artifacts rather than changing receipts or replay inputs to make them pass.

```bash
uv run python -m entropytrade.tracking.replay data/cache/workbench/shadow/MONITOR_ID/CYCLE_ID
```

The evaluator reuses the replay `DecisionView`, bounded DSL and `RiskEngine`. It gates
receipt-time features, model fit/calibration and feature identity, protected events,
sources, rules, sized quotes and certified fee information/effective clocks. Shadow
intentions also require the StrategySpec's calibration method: `platt` and `isotonic`
must match exactly; `none` accepts `none` or the existing `uncalibrated baseline` label.
A mismatch records `requested_calibration` with no intent or risk evaluation. Decisions
using Platt/isotonic also require a non-null `calibrated_before` at or before the decision;
missing clocks record `calibration_availability`, and future clocks fail the existing
`point_in_time_prediction` gate. Uncalibrated outputs may omit that clock. Model metadata
must explicitly classify its data as `real` or `synthetic`, matching the dataset;
missing, invalid or mismatched classification records `model_dataset_provenance` before
the interpreter or risk evaluation runs. Decisions unaffected by these corrections keep
their prior replay hashes. Fixed shadow
caps use the experiment defaults: $1,000 hypothetical bankroll, $25 per intention, $100
per event, $500 reserved total; maximum spread $0.10 and book age 60 seconds. They cannot
be changed by the UI or strategy. Eligible intentions reserve quantity and fee-inclusive
collateral across cycles and restarts; repeated polls cannot replenish position room.
Each monitor has an independent hypothetical portfolio; these are not account-wide
execution permissions or a combined live allocation.
Reservations are conservative intentions, not positions or evidence of fills. They release
only after a later verified official result. Hold-to-settlement exits are the supported
shadow subset; predicate exits are refused rather than interpreted as observed positions.

Later cycles reconcile up to ten closed tracked contracts through exact unauthenticated
Kalshi market GETs (historical endpoint only on a live endpoint 404). Original event,
strike, close and rule text must match; a finalized non-provisional binary result needs
the matching payout and a settlement clock between original close and HTTP receipt.
Unresolved, changed and exceptional contracts remain pending or failed with their receipts.
Official binary outcomes are not scalar weather/index labels and do not certify broader
settlement semantics. Outcome availability is the new receipt time; earlier decisions,
model partitions and historical holdout boundaries are never rewritten. Pending lookups
rotate by oldest attempt, so a large set does not starve later contracts.
The first accepted finalized result freezes that contract's outcome; monitoring later
corrections to finalized outcomes remains a release limitation.

Pause interrupts an active cycle atomically and prevents its late result from committing.
Resume starts a fresh collection; completed cycles remain unchanged. Restart marks any
running cycle interrupted and resumes active schedules with fresh receipts, without
backfilling missed polls. Partial artifacts remain at the cycle's `artifact_root` in the
workspace. Paused monitors remain paused after restart. Worker crashes/timeouts are durable
failures; retries back off up to one hour and five consecutive acquisition/reconciliation/
worker failures pause a monitor for inspection. Shutdown kills and waits for the child.

Operating budgets: four active monitors, 100 monitors per workspace, 128 unique contracts
per monitor, 1,000 cycles per monitor, poll intervals 60–3,600 seconds and a four-minute
worker deadline. Capture itself retains its existing request/byte/time caps. Contract-budget
errors fail visibly and eventually pause; the cycle budget pauses directly. Start a
separate, reviewed monitor to continue beyond a budget; evidence is never deleted or
silently truncated. Collection runs only while the local server runs. This is a bounded
single-user local monitor, not a deployment supervisor or long-running hosted service.

The localhost/same-origin/CSRF boundary and credential-free subprocess environment are
shared with the research workbench. There is no broker invocation, order transport,
execution activation, credential input or risk-override endpoint. `submission_enabled`
remains false in all exported evidence. A shadow risk decision never becomes an
`ApprovedOrderIntent` or an exchange request.

Current [model-to-shadow evidence](../data/shadow-review/20261029-model-integration/README.md)
retains executed checks, authentic source/book/fee receipts, offline replay verification and
actual Playwright-managed Chromium page interactions against the real localhost server.
The strengthened [procedure](../frontend/browser/shadow.spec.cjs) exercises research, start,
pause, restart, identical downloads, resume and a second cycle, without mocked responses or
clock overrides. Both real cycles completed with ten sized books; all probabilities and
intentions remained absent for honest model/fee blockers. This is lifecycle/source evidence,
not fitted empirical model or release acceptance. The original decimal-ticker failure and
historical socket denials remain preserved separately. No human browser step remains for
this scoped procedure; final release and empirical acceptance remain outstanding.

Earlier [tracking](../data/shadow-review/20261029/README.md),
[calibration/holdout](../data/shadow-review/20261029-boundaries/README.md),
[availability/provenance](../data/shadow-review/20261029-availability-provenance/README.md),
[probability binding](../data/shadow-review/20261029-probability-binding/README.md) and
[reserved quote](../data/shadow-review/20261029-reserved-quote-bindings/README.md)
evidence keeps its original scope and outcomes. Reproduce with new absolute paths:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/shadow-review/NEW/browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/shadow-browser-NEW" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs --grep 'continuous shadow'
```

Use new absolute evidence/workspace directories. The procedure labels actual source
access separately from capture failure and never imports controlled responses, overrides
the worker, fakes clocks or intercepts requests. It needs provisioned Python dependencies
and npm dependencies (`npm ci --prefix frontend/browser --ignore-scripts --no-audit --no-fund`).
