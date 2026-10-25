# Backtesting

R4 repaired replay chronology and connected strategy experiments. See
[experiment operations](experiments.md) for commands, supported StrategySpecs, artifacts,
statistics and exact execution/fee assumptions.

`backtest/replay.py` runs a timestamp-ordered event queue: books update first, settlements
resolve exposure, eligible orders execute after latency, then decisions occur. A zero-latency
order executes before later decisions at that timestamp. `DecisionView` filters each feature
by actual availability and supplies the current ledger, fee schedule and pending quantities.
Only the latest already-received book can fill an order, within split/close/expiry/age bounds.
Final holdout runs refuse execution.

Existing `Ledger`, `PaperBroker` and `RiskEngine` own Decimal accounting, side complements,
netting, fees, collateral, approval and settlement. Pending orders reserve cash and contribute
to event/portfolio exposure; a fill appears only at execution time. Used depth cannot be
reused in the same snapshot state. Changed snapshots or advancing non-null sequence numbers
reset modeled capacity. This is a simulation assumption, not proof of liquidity replenishment.
Partial/unfilled immediate orders cancel, with an audit of risk and freshness rejections.

Optimistic permits observed price improvement; base clamps it to the decision touch;
conservative shifts prices adversely, halves size and (in experiments) stresses fees.
Unknown queues, order competition and venue fills are not modeled. At-cost equity/drawdown
between settlements must not be presented as market-marked risk. Unresolved positions
prevent final P&L claims. Candles/trade prints/size-free quotes never become executable books.

R4 real experiments require explicit historical fee certification, evidence hash and
information/effective clocks. The legacy `SeriesFeeTable` path retains supplied coefficients
and stored type/multiplier semantics for old studies; it does not establish real historical
fees. R4 defaults to no real fee policy. Unsupported fee formulas/spec semantics reject.
Legacy candle-volume pseudo-books remain preserved but are excluded from the new workflow.

The reuse audit remains applicable: external backtesters' artifact/coherence ideas are useful,
but their midpoint fills, incorrect cash-at-risk, ignored limits, obsolete indexers and missing
settlement are not adopted. R4 reuses our ledger/broker/risk and mature NumPy/scikit-learn,
PyArrow, SQLite and MLflow. No new dependency or external execution engine was introduced.
