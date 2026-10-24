# Backtesting

R0 correction: this file mixes implemented replay primitives with intended design.
The complete artifact writer, realistic queue/capacity model and protected final evaluator
are not implemented. See [capabilities](capabilities.md#correctness-risks-that-gate-future-claims)
for fill chronology, split bounds, exposure and data-fidelity risks before using results.

`entropytrade.backtest.replay` walks recorded books in time order. A strategy receives a
`DecisionView`, which is `select_as_of` at the book's receive time, and nothing else.
Holdout windows are not passed to the strategy. A fill uses the book at
`decision_time + latency`, with prices clamped so the run cannot buy a better touch
than the one it saw. Settlement inside the split window goes through `Ledger.settle`.
The artifact hash covers the spec hash, the fill ids, and ending equity. Fees are
`trade_fee`. The audited backtester is still not imported.

## Rules already encoded

- A decision at time `t` may use a record only when `available_at <= t`, via
  `select_as_of`. Tests construct a future observation and show it cannot change the
  selection.
- Every run will be a `BacktestRun`: strategy spec hash, git SHA, config hash, dataset
  manifest hash, feature version, fee model, execution model version, fill scenario
  (`optimistic`, `base`, `conservative`), execution fidelity, seed, and
  train/validation/holdout windows that cannot overlap.
- Fidelity is explicit. A run on candles is `candles_only` and is not treated as a book
  replay. Last trade and midpoint are not executable prices; the domain's book type
  separates them from `best_price_to_buy`.
- Fees are a `FeeModelRef` (type, multiplier, whether the maker pays, effective date),
  not a constant. A replay that is given `series_fees` replaces the broker schedule
  with the stored series: KXHIGHPHIL is `quadratic` with multiplier 1, so makers pay
  nothing. `KXNHL` is `quadratic_with_maker_fees` (maker fraction 0.25). The quadratic
  coefficient is still the number already on the broker, because the series payload
  does not contain it and the fee-schedule PDF fetch returned HTTP 429. The run
  records fee-model version `series-fields-v1`. Flat series fees are not computed.
- Settlement pays the contract, and payouts are bounded by quantity. An open position
  marked at the last trade is not a settlement.

## What we will not adopt

`Quentin-Piot/prediction-market-backtester` has the right artifact idea and a useful
post-run coherence check (recompute metrics from the written files and require them to
match). Its execution core is not safe to port:

- cash-at-risk is inverted, and the tests assert the inverted numbers,
- cash can go negative and a short credits cash instead of locking collateral,
- `limit_price` is ignored,
- there is no settlement,
- fills use the bar's last trade, at the same bar by default,
- batch run directories collide when two markets finish in the same second,
- the vendored Kalshi indexer reads integer price fields Kalshi removed on 2026-03-12
  and does not call `/historical/*`.

`karshincheo/kalshi-trading` and `Viprasol-Tech/kalshi-trading-bot` are weaker still:
mid fills or fills at the order's own limit, missing or zero fees, and in one case a
walk-forward engine that never sees its data. Details and the reuse decision are in
[`external-repositories.md`](external-repositories.md).

## Phase 3 shape

Replay domain events in `available_at` order under a `SimulatedClock`. Strategies see a
book or a labelled lower-fidelity quote, never the future. Fills come from a versioned
execution model with optimistic, base and conservative scenarios. A strategy that passes
only the optimistic scenario does not get promoted. Each run writes an atomic directory
(`results.json`, config, trades, equity, manifest) and a coherence check recomputes the
totals from the files. The holdout window is not readable by the research agents.
