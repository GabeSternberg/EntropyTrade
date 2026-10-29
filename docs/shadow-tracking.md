# Continuous read-only shadow monitoring

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

The current forward adapter **has no fitted forward probabilities, certified fees or
sized books**. Authentic captures therefore record blocked decisions with null predictions
and intentions. Empty or failed acquisition remains visible and is not a successful model
run. An explicit model reference without a forward scorer records a model refusal.
The deterministic evaluator accepts shared typed samples/predictions/fee evidence, and
controlled tests exercise its eligible/rejected intentions; those fixtures are software
evidence only. Wiring a certified trained model and sized live data into this collector
remains future work. There are no fills, balances, P&L estimates or profitability claims.

Every completed collection saves `decision-inputs.json`, with targets removed and protected
records excluded. Verify its artifact hashes and recompute decisions without any network
access using the local command below. This reproduces the recorded decision computation;
it does not authenticate a source or establish empirical performance. Interrupted cycles
without input/result artifacts cannot be replayed and report that limitation explicitly.

```bash
uv run python -m entropytrade.tracking.replay data/cache/workbench/shadow/MONITOR_ID/CYCLE_ID
```

The evaluator reuses the replay `DecisionView`, bounded DSL and `RiskEngine`. It gates
receipt-time features, model fit/calibration and feature identity, protected events,
sources, rules, sized quotes and certified fee information/effective clocks. Fixed shadow
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

Verification is recorded in [the milestone evidence](../data/shadow-review/20261029/README.md).
The executable [Playwright procedure](../frontend/browser/shadow.spec.cjs) uses managed
Chromium and the real localhost app, submits research, starts/pauses/resumes tracking,
compares downloads across restart and preserves screenshots when page interaction runs.
Here Chromium failed before page interaction with `setsockopt: Operation not permitted`
and `SIGTRAP`; no screenshot or browser pass is claimed. Run the procedure in an environment
permitting browser sockets before browser acceptance. HTTP/unit tests do not replace it.

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
