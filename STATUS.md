# EntropyTrade — Project Status

> **Single source of truth for "where are we?"** A fresh agent given only this
> file (plus the repo) should be able to resume. Update it at the end of every
> phase: mark the phase complete, link its checkpoint report, and move
> **Next steps** to the next phase.

Last updated: 2026-10-02 · Current phase: **Phase 4.88 — complete**. Next is Phase 4.89.

## What this project is

A private, single-user research, backtesting and (eventually) automated
trading platform for Kalshi prediction markets. It is not a SaaS product.
The full requirements live in [`docs/project-spec.md`](docs/project-spec.md)
(verbatim copy of the original spec; section numbers below refer to it).

Core rule: **LLMs research; deterministic systems control money.** Agents emit
typed `StrategySpec`s. Only the deterministic risk engine and execution engine
can turn an approved intent into an order, and only the execution process ever
holds trading credentials.

## Ground rules for every agent

1. Work **strictly phase by phase**. At the end of a phase: run all checks
   (`make check`), update docs, commit, write the checkpoint report, update
   this file, then **STOP** until the user explicitly says to continue.
   On 2026-10-02 the user authorized the agent on branch
   `cursor/phase-0-skeleton-e162` to continue from Phase 1 through later
   phases on that same branch without waiting between phases. Live and
   production orders stay forbidden. A later agent should follow the latest
   user instruction; this note does not by itself authorize a new session to
   skip the stop.
2. Off-plan work gets a sub-phase number (e.g. 1.50, 1.51) added to the table
   below, never silently folded into another phase.
3. If a finding makes the spec's architecture worse, flag it in the phase
   report rather than following the spec blindly.
4. Never add live trading, order submission or production credentials before
   the phase that explicitly calls for it (Phase 9, after explicit approval).
   Even then, live mode stays off unless `ENTROPYTRADE_LIVE_TRADING_ENABLED`
   is exactly `true`. Do not place a real-money or production order.

## Phase overview

| Phase | Name | Status | Report |
| --- | --- | --- | --- |
| 0 | Open-source audit + project skeleton | **complete** | [phase-0.md](docs/phase-reports/phase-0.md) |
| 1 | Read-only Kalshi gateway + market recorder | **complete** | [phase-1.md](docs/phase-reports/phase-1.md) |
| 2 | Accounting + paper broker + risk foundation | **complete** | [phase-2.md](docs/phase-reports/phase-2.md) |
| 3 | Point-in-time backtesting engine | **complete** | [phase-3.md](docs/phase-reports/phase-3.md) |
| 4 | First weather dataset + baseline models | **complete** | [phase-4.md](docs/phase-reports/phase-4.md) |
| 4.50 | One public Philadelphia daily-high pull | **complete** | [phase-4.50.md](docs/phase-reports/phase-4.50.md) |
| 4.51 | CLIPHL settlement observations from NWS CLI | **complete** | [phase-4.51.md](docs/phase-reports/phase-4.51.md) |
| 4.52 | Longer public KXHIGHPHIL tape | **complete** | [phase-4.52.md](docs/phase-reports/phase-4.52.md) |
| 4.53 | Rescore on CLI-aligned rows | **complete** | [phase-4.53.md](docs/phase-reports/phase-4.53.md) |
| 3.50 | Series fee fields in replay | **complete** | [phase-3.50.md](docs/phase-reports/phase-3.50.md) |
| 3.51 | Point-in-time revision leakage | **complete** | [phase-3.51.md](docs/phase-reports/phase-3.51.md) |
| 2.50 | Order reconciliation invariants | **complete** | [phase-2.50.md](docs/phase-reports/phase-2.50.md) |
| 2.51 | Named local HALT sentinel | **complete** | [phase-2.51.md](docs/phase-reports/phase-2.51.md) |
| 2.52 | Optional minimum net-edge check | **complete** | [phase-2.52.md](docs/phase-reports/phase-2.52.md) |
| 2.53 | Optional open-order cap | **complete** | [phase-2.53.md](docs/phase-reports/phase-2.53.md) |
| 2.54 | Optional order-rate cap | **complete** | [phase-2.54.md](docs/phase-reports/phase-2.54.md) |
| 2.55 | Optional slippage-reserve cap | **complete** | [phase-2.55.md](docs/phase-reports/phase-2.55.md) |
| 2.56 | Optional maximum model age | **complete** | [phase-2.56.md](docs/phase-reports/phase-2.56.md) |
| 2.57 | Reconciliation age, with the existing halt switches | **complete** | [phase-2.57.md](docs/phase-reports/phase-2.57.md) |
| 4.57 | Public trade prints, labeled as not a fill | **complete** | [phase-4.57.md](docs/phase-reports/phase-4.57.md) |
| 4.58 | Prediction records for the rescore decisions | **complete** | [phase-4.58.md](docs/phase-reports/phase-4.58.md) |
| 7.50 | Structural scan of stored strikes | **complete** | [phase-7.50.md](docs/phase-reports/phase-7.50.md) |
| 4.59 | Later books stay out of the CLI replay | **complete** | [phase-4.59.md](docs/phase-reports/phase-4.59.md) |
| 4.60 | Historical trade prints, not joined to the CLI replay | **complete** | [phase-4.60.md](docs/phase-reports/phase-4.60.md) |
| 4.61 | Pre-registered informational rules | **complete** | [phase-4.61.md](docs/phase-reports/phase-4.61.md) |
| 4.62 | Walk-forward of the registered rules | **complete** | [phase-4.62.md](docs/phase-reports/phase-4.62.md) |
| 4.63 | Net opposite intents on the 80-81 contract | **complete** | [phase-4.63.md](docs/phase-reports/phase-4.63.md) |
| 4.64 | Last historical print versus the stored result | **complete** | [phase-4.64.md](docs/phase-reports/phase-4.64.md) |
| 4.65 | Print before occurrence versus the stored result | **complete** | [phase-4.65.md](docs/phase-reports/phase-4.65.md) |
| 4.66 | Expiration value versus strike and result | **complete** | [phase-4.66.md](docs/phase-reports/phase-4.66.md) |
| 4.67 | Print size sum versus stored volume | **complete** | [phase-4.67.md](docs/phase-reports/phase-4.67.md) |
| 4.68 | Settlement dollars versus the stored result | **complete** | [phase-4.68.md](docs/phase-reports/phase-4.68.md) |
| 4.69 | Print before close versus the stored result | **complete** | [phase-4.69.md](docs/phase-reports/phase-4.69.md) |
| 4.70 | Second pull of the 18 markets short of volume | **complete** | [phase-4.70.md](docs/phase-reports/phase-4.70.md) |
| 4.71 | Live trades for the 18 markets short of volume | **complete** | [phase-4.71.md](docs/phase-reports/phase-4.71.md) |
| 4.72 | Pre-decision B80.5 print versus the CLI bracket | **complete** | [phase-4.72.md](docs/phase-reports/phase-4.72.md) |
| 4.73 | Walk-forward of the pre-decision print guess | **complete** | [phase-4.73.md](docs/phase-reports/phase-4.73.md) |
| 4.74 | Volume shortfall on the two trade routes | **deferred** | [phase-4.74.md](docs/phase-reports/phase-4.74.md) |
| 4.75 | Chicago daily high, same registered rules | **complete** | [phase-4.75.md](docs/phase-reports/phase-4.75.md) |
| 4.76 | Philadelphia daily-high research note | **complete** | [phase-4.76.md](docs/phase-reports/phase-4.76.md) |
| 4.77 | CLI day with no prediction record | **complete** | [phase-4.77.md](docs/phase-reports/phase-4.77.md) |
| 4.78 | Feature manifest versus spec section 27 | **complete** | [phase-4.78.md](docs/phase-reports/phase-4.78.md) |
| 4.79 | Feature hash omits two row keys | **complete** | [phase-4.79.md](docs/phase-reports/phase-4.79.md) |
| 4.80 | Chicago rule walk-forward, holdout unscored | **complete** | [phase-4.80.md](docs/phase-reports/phase-4.80.md) |
| 4.81 | Chicago days absent from the feature manifest | **complete** | [phase-4.81.md](docs/phase-reports/phase-4.81.md) |
| 4.82 | Empty calibration version on the rescore records | **complete** | [phase-4.82.md](docs/phase-reports/phase-4.82.md) |
| 4.83 | cli-aligned has no stored StrategySpec | **complete** | [phase-4.83.md](docs/phase-reports/phase-4.83.md) |
| 4.84 | Chicago pre-decision print versus the CLI bracket | **complete** | [phase-4.84.md](docs/phase-reports/phase-4.84.md) |
| 4.85 | Chicago print-guess walk-forward, holdout unscored | **complete** | [phase-4.85.md](docs/phase-reports/phase-4.85.md) |
| 4.86 | The Chicago print that misses the CLI bracket | **complete** | [phase-4.86.md](docs/phase-reports/phase-4.86.md) |
| 4.87 | Chicago listed results versus the CLI bracket | **complete** | [phase-4.87.md](docs/phase-reports/phase-4.87.md) |
| 4.88 | Chicago settlement dollars and expiration values | **complete** | [phase-4.88.md](docs/phase-reports/phase-4.88.md) |
| 8.50 | Shadow versus paper comparison records | **complete** | [phase-8.50.md](docs/phase-reports/phase-8.50.md) |
| 1.50 | Collector health flags | **complete** | [phase-1.50.md](docs/phase-reports/phase-1.50.md) |
| 4.54 | Published fee fractions, no invented coefficient | **complete** | [phase-4.54.md](docs/phase-reports/phase-4.54.md) |
| 4.55 | Broader public KXHIGHPHIL tape, no sized book | **complete** | [phase-4.55.md](docs/phase-reports/phase-4.55.md) |
| 4.56 | Rescore on the broader tape; equity stays 100 | **complete** | [phase-4.56.md](docs/phase-reports/phase-4.56.md) |
| 5.50 | Walk-forward on stored CLI days | **complete** | [phase-5.50.md](docs/phase-reports/phase-5.50.md) |
| 6.50 | Feature manifest and rescore prediction records | **complete** | [phase-6.50.md](docs/phase-reports/phase-6.50.md) |
| 6.51 | Registry pause writes the HALT sentinel | **complete** | [phase-6.51.md](docs/phase-reports/phase-6.51.md) |
| 5 | Agentic research pipeline (PydanticAI) | **complete** | [phase-5.md](docs/phase-reports/phase-5.md) |
| 6 | Strategy registry + experiment tracking + dashboard | **complete** | [phase-6.md](docs/phase-reports/phase-6.md) |
| 7 | Structural / arbitrage scanner | **complete** | [phase-7.md](docs/phase-reports/phase-7.md) |
| 8 | Live paper + shadow validation | **complete** | [phase-8.md](docs/phase-reports/phase-8.md) |
| 9 | Live-small execution (explicit approval required) | **complete** (gate only; no order sent) | [phase-9.md](docs/phase-reports/phase-9.md) |
| 10 | Live decay detection + automatic downsizing | **complete** (comparisons only; no order sent) | [phase-10.md](docs/phase-reports/phase-10.md) |
| 11 | Optional expansion (more markets, cross-venue, FIX, DL) | **deferred** | [phase-11.md](docs/phase-reports/phase-11.md) |

Phase definitions are in spec §40. Summary of each phase's acceptance bar:

- **Phase 0**: inspect the external repos and their licenses; reuse matrix
  (`docs/external-repositories.md`); `THIRD_PARTY_NOTICES.md`; Kalshi docs
  reference; uv/Ruff/mypy/pytest/Hypothesis/pre-commit; architecture docs;
  core domain types and interfaces. No trading logic.
- **Phase 1**: `ExchangeGateway` + `KalshiGateway` (READ_ONLY), discovery,
  rules storage, REST book snapshots, WebSocket deltas/trades, reconnect,
  sequence integrity, API limits, persisted raw + normalized data, health.
  Must run for hours in demo, survive restarts and replay recordings.
  The hours-long live run is unverified (no read-scoped key). Restart,
  replay, gap detection, and in-process reconnect are tested.
- **Phase 2**: account/positions/orders/fills/settlements/P&L, PaperBroker,
  deterministic risk engine, kill switch, reconciliation against demo.
- **Phase 3**: point-in-time replay engine, fees/spread/latency/slippage,
  partial fills where data permits, settlement, artifacts, splits and
  walk-forward; a deliberately leaky strategy must be blocked.
- **Phase 4**: first weather vertical (daily-high temperature), point-in-time
  forecasts, baseline models, forecasting *and* trading evaluation.
- **Phase 4.50**: one stored public pull (Open-Meteo previous runs and archive,
  plus demo-host Kalshi public REST). Baselines and replay run on those rows.
  The production host was not called.
- **Phase 4.51**: NWS CLI highs for CLIPHL from a stored IEM pull. Compared
  with the Open-Meteo archive and with Kalshi official results. Open-Meteo is
  not settlement. The contracts on these dates name The Weather Company.
- **Phase 4.52**: longer public KXHIGHPHIL tape. Unauthenticated production
  GETs returned markets, historical markets, candlesticks, and 12 order books
  with real sizes. Empty books are skipped. Candles are not given a touch size.
- **Phase 4.53**: baselines and replay on the CLI labels. Forecast MAE
  2.9925 °F. The forecast rule does not trade. No sized book is inside the
  label window. Equity stays 100. Nothing was fit or promoted.
- **Phase 3.50**: replay applies stored series fee fields. KXHIGHPHIL is
  quadratic and makers pay nothing. KXNHL makers pay. The run records
  fee-model version `series-fields-v1`. The quadratic coefficient is not in
  the series payload. The fee-schedule PDF returned HTTP 429.
- **Phase 3.51**: a revision timestamp after the decision cannot change
  `select_as_of` or a replay trade.
- **Phase 2.50**: reconciliation refuses a smaller fill, a conflicting
  exchange order id, or a different contract.
- **Phase 2.51**: the local sentinel path is `halt_sentinel(directory)`,
  named `HALT`. Presence still blocks new orders after `resume`. It does not
  cancel or liquidate.
- **Phase 2.52**: when `min_net_edge` is set, a missing edge estimate or a
  net edge below the floor rejects the intent. Unset leaves the check off.
- **Phase 2.53**: when `max_open_orders` is set, the caller-supplied count
  must be strictly below the cap. Unset leaves the check off.
- **Phase 2.54**: when `max_order_rate` is set, the caller-supplied count of
  orders already placed in the window must be strictly below the cap. Unset
  leaves the check off.
- **Phase 2.55**: when `max_slippage` is set, a missing edge estimate or a
  slippage reserve above the cap rejects the intent. Unset leaves the check
  off.
- **Phase 2.56**: when `max_model_age_seconds` is set, a missing model time
  or a model older than the cap rejects the intent. Age equal to the cap is
  still fresh. Unset leaves the check off.
- **Phase 2.57**: the HALT file and `trading_enabled` already block new
  orders. The missing check was time since reconciliation. When that cap is
  set, a missing or stale reconciliation time rejects the intent.
- **Phase 4.57**: 104,442 public trade prints for the 240 stored markets.
  A print is not a guaranteed fill. The forecast rule fires on 0 days under
  optimistic, base, and conservative. Equity stays 100.000000. No fee was
  applied.
- **Phase 4.58**: 39 prediction records. Bid, ask, and net edge are empty.
  A label whose `available_at` is after the decision cannot be included.
  2,617 B80.5 prints are counted only when they existed by 15:00 UTC.
- **Phase 7.50**: four stored threshold books have a size. Their YES asks
  do not break the ladder. The 240 CLI-window strikes are flagged
  non-executable because they have a candle or a trade and no sized book.
  No order was submitted.
- **Phase 4.59**: the twelve sized books are for 2 October and 3 October.
  The CLI window ends on 1 October, so they do not enter the replay. Equity
  stays 100.000000.
- **Phase 4.60**: 1,018,012 historical prints for 3,666 of the 3,720 stored
  pre-cutoff tickers. 54 tickers had no prints. Raw pages are gitignored.
  The prints are not fills and are not in the 2026 CLI replay.
- **Phase 4.61**: four tried hypotheses, none promoted. Inside does not fire.
  Above fires 19 times and below 21 times, with no print cheap enough to
  buy NO. The gap rule's optimistic case assumes 3 fills and equity
  99.900000. Base and conservative stay at 100. A print is not a fill.
- **Phase 4.62**: train 20, validation 10, holdout 10. The holdout is not
  scored. The gap rule assumes 2 optimistic fills in train (equity
  99.910000) and 1 in validation (equity 99.990000). Nothing is promoted.
- **Phase 4.63**: above and gap want opposite sides on 19 days. After
  netting, optimistic fills are 0 and equity stays 100.000000. Nothing is
  promoted.
- **Phase 4.64**: the last print on 3,666 historical markets agrees with
  the stored result 3,661 times. 621 of those prints are at or above 0.50
  and are counted as YES guesses. 54 markets have no print and no guess.
  Most last prints are within a cent of 0 or 1, so this is not a forecast.
  Nothing is promoted. CLI replay equity stays 100.
- **Phase 4.65**: 3,078 markets have no stored occurrence time, so they
  get no guess and no substitute cutoff. The other 642 all have a print
  strictly before occurrence. 75 are YES guesses. 544 match the result.
  Nothing is promoted. CLI replay equity stays 100.
- **Phase 4.66**: 2,887 markets have an expiration value and a strike.
  All 2,887 results match that strike. 808 expiration values are empty
  and 25 strikes are missing. Those stay unevaluable. Nothing is promoted.
- **Phase 4.67**: print sizes equal `volume_fp` on 3,702 markets. 18 are
  short. None are long. 54 markets have no prints and volume 0. The missing
  size is not invented. Nothing is promoted.
- **Phase 4.68**: settlement dollars are exactly 1 on every YES result and
  exactly 0 on every NO result. 3,720 agree. None are unevaluable. Nothing
  is promoted.
- **Phase 4.69**: every stored print is strictly before its market's close.
  The pre-close guess matches the last-print guess: 3,661 of 3,666 agree,
  and 621 are YES guesses. Nothing is promoted.
- **Phase 4.70**: a second pull of the 18 short markets returned the same
  size sums. All 18 cursors were empty. All 18 stay short of volume. The
  missing size is not invented. Nothing is promoted.
- **Phase 4.71**: `/markets/trades` returned an empty list for each of
  those 18 markets. The rows were not added to the historical table. The
  missing size is not invented. Nothing is promoted.
- **Phase 4.72**: 10 of 40 CLI days have a B80.5 print at or before 15:00
  UTC. None of those prints are at or above 0.50. 9 match the bracket.
  The miss is 25 August, print 0.1000, CLI high 80. Nothing is promoted.
  Replay equity stays 100.
- **Phase 4.73**: train has 5 eligible prints and 4 agreements. Validation
  has 3 eligible prints and 3 agreements. No YES guess in either split.
  The holdout is not scored. Nothing is promoted.
- **Phase 4.74**: deferred. Both public trade routes already returned no
  extra size for the 18 short markets. The missing size is not invented.
  0.50 and 15:00 stay put.
- **Phase 4.75**: the series list names Chicago before New York. Four more
  hypotheses on CLIMDW, none promoted. Optimistic equity is 100.750000,
  99.400000, 99.660000, and 102.430000. Base and conservative stay at 100.
  Philadelphia replay equity stays 100.
- **Phase 4.76**: the Philadelphia note records four tried rules, the
  stored optimistic, base, and conservative equities, and the train and
  validation walk-forward counts. The holdout is not in the note as a
  score. Nothing is promoted. No new model.
- **Phase 4.77**: 40 CLI days, 39 prediction records. The missing day is
  2026-08-23. The forecast is stored and available before the label. The
  15:00 decision has no prior CLI high, so climatology raises
  InsufficientHistoryError. No probability was stored for that day.
  Nothing is promoted.
- **Phase 4.78**: the manifest names forecast_high,
  point_in_time_climatology, and prints_at_decision. Previous-runs hourly
  fields are time and temperature_2m_previous_day1. All 27 spec section 27
  names are absent. Bid and ask are empty on all 39 records. Nothing is
  promoted. No model was fit.
- **Phase 4.79**: the feature-vector hash covers every manifest row key
  except market_ticker and sized_book. The stored hash was not rewritten.
  Nothing is promoted.
- **Phase 4.80**: Chicago uses the same 20/10/10 split. Train and
  validation are scored. The holdout is not scored. Optimistic train
  equity is 100.750000, 99.400000, 99.660000, and 102.510000. Optimistic
  validation equity is 100.000000, 100.000000, 100.000000, and 99.920000.
  Base and conservative stay at 100. Nothing is promoted. Thresholds
  stay 80, 81, 0.40, 80.5, and 15:00.
- **Phase 4.81**: Chicago has 40 CLI labels. The feature manifest has 39
  rows, all station CLIPHL. Zero prediction records name KXHIGHCHI. No
  Chicago probability was built. Nothing is promoted.
- **Phase 4.82**: all 39 prediction records leave calibration_version
  empty. No calibration version was invented. Nothing is promoted.
- **Phase 4.83**: the 39 records name strategy_id cli-aligned at version 1.
  The stored research specs do not include that id. No StrategySpec was
  written. Nothing is promoted.
- **Phase 4.84**: 11 of 40 Chicago days have a B80.5 print at or before
  15:00 UTC. 5 of those prints are at or above 0.50. 10 match the bracket.
  Philadelphia stays at 10 prints, 0 YES guesses, and 9 agreements. Nothing
  is promoted. 0.50 and 15:00 stay put.
- **Phase 4.85**: Chicago print-guess train has 8 eligible prints, 5 YES
  guesses, and 8 agreements. Validation has 2 eligible prints, 0 YES
  guesses, and 2 agreements. The holdout is not scored. Philadelphia
  walk-forward stays at train 5/4 and validation 3/3, with no YES guess.
  Nothing is promoted.
- **Phase 4.86**: the only Chicago miss is 2026-09-29. The print is 0.02
  at 14:42:56.655073 UTC, the CLI high is 80, and the 0.50 guess is NO
  while the bracket is YES. Philadelphia's only miss stays 2026-08-25 at
  0.1000. Nothing is promoted. 0.50 and 15:00 stay put.
- **Phase 4.87**: 11 listed Chicago B80.5 markets have a stored result,
  6 yes and 5 no. All 11 match the CLI bracket. The 29 missing markets
  have no result field. Nothing was invented for them. Nothing is
  promoted.
- **Phase 4.88**: a compact table of the 11 listed markets. Settlement
  dollars are exactly 1 on yes and exactly 0 on no. Expiration value and
  the between strike agree with the result on all 11. The 29 missing
  markets are not in the table. Nothing is promoted. No URL was retried.
- **Phase 8.50**: a record compares the paper fill price with the shadow
  price on the same book. Shadow still does not fill.
- **Phase 1.50**: health flags for connected, stale, gapped, and lagging.
  A disconnected feed with no messages is only disconnected.
- **Phase 4.54**: the vendored series docs state maker multipliers 0.25 and
  0.5. They do not state a taker coefficient. A second PDF fetch returned
  HTTP 429. The coefficient stays unset.
- **Phase 4.55**: 240 settled KXHIGHPHIL order books in the CLI window, 66
  strikes, all empty. 230 hourly candles stored. No touch size was invented.
  No sized book exists before a CLI label.
- **Phase 4.56**: rescore with CLI labels, that tape, and the stored fee
  model. The forecast rule still does not trade. Equity stays 100. Nothing
  was promoted. The taker coefficient stays unpublished.
- **Phase 5.50**: walk-forward on the 40 stored CLI days. Train 20, validation
  10, holdout 10. The holdout is not run. Fills stay 0. Equity stays 100.
- **Phase 6.50**: on-disk feature manifest and 39 prediction records for the
  rescore. Probability is 0. Bid, ask, and net edge are empty. Nine records
  name a stored B80.5 market. The other days name the series because that
  strike was not listed.
- **Phase 6.51**: the registry page can write the HALT sentinel with
  `POST /halt`. `POST /` stays refused. The page still cannot submit an order.
- **Phase 5**: Research → Hypothesis → Quant → Critic agents producing
  StrategySpecs, auto-backtested; no holdout access, no trading.
- **Phase 6**: lineage, versioning, MLflow, promotion states, approvals, dashboard.
- **Phase 7**: deterministic constraint/arbitrage detection, paper/shadow only.
- **Phase 8**: live paper + shadow validation against real books, no real orders.
- **Phase 9**: tiny live envelope for one approved strategy, only after approval.
- **Phase 10**: decay from paper and shadow comparisons, a downward lifecycle
  move, and a size cut that never increases a limit. Model drift, calibration,
  feature drift, and live-versus-backtest divergence are not scored.
- **Phase 11**: optional expansion. **Deferred.** pmxt, FIX, deep learning,
  cross-exchange execution, and automatic retraining were not added.

## Next steps

Phase 4.89 — compare the 11 stored Chicago expiration values with the
CLI high in degrees. A bracket match is not the same as an equal high.
Do not treat CLI as the settlement source. Do not invent values for the
29 missing markets. Do not promote. No live order.

## Checks

On 2026-10-02, `make check` passed for Phase 4.88: ruff clean, mypy strict
clean, pytest 225 passed. `uv sync` then `make check`. Default mode is
`read_only`.
`uv` is not on the default `PATH` in every shell; it lives at
`~/.local/bin/uv` (0.12.22) in the environment that built this.

Unverified for lack of credentials: a multi-hour demo or read-only production
session, a real Kalshi WebSocket handshake, reconciliation against a live demo
account, any live NWS or Weather Company request, and any live Anthropic or
OpenAI call. Provider model requests are blocked. The MLflow UI server is not
started. No production trading credentials are in the repo. Phase 4.50 did
call Open-Meteo and the Kalshi demo host without a key. One of those calls
returned HTTP 400; the body is in the Phase 4.50 report. Phase 4.51 stored an
IEM CLIPHL pull. Phase 4.52 used unauthenticated GETs on the production
market-data host. No order was sent. Phase 4.53 did not call the network.
The forecast rule does not trade on the CLI-aligned rows, and replay equity
stays 100. Phase 3.50 stored public series fee fields. The fee-schedule PDF
returned HTTP 429; the body is kept and no coefficient was invented.
Phase 4.55 stored 240 empty settled order books and 230 hourly candles for
the CLI window. No sized book was found before a CLI label. Phase 4.56
rescored those rows with the stored fee model. The rule still does not
trade, and equity stays 100. Phase 5.50 walk-forward on those days skips
the holdout and still does not trade. Phase 6.50 stored the feature manifest
and 39 prediction records for that rescore.

## How to resume (fresh agent)

1. Read this file, then `docs/project-spec.md`, then `docs/architecture.md`.
2. Read the latest phase report under `docs/phase-reports/`.
3. Set up: `uv sync` (Python 3.12+), then `make check` (lint + typecheck + tests).
4. Kalshi API reference: `.agents/skills/kalshi-docs/` (see `README.md`).
5. Continue with the phase listed under **Next steps**. If the user has said
   to continue across phases, stay on `cursor/phase-0-skeleton-e162`.
