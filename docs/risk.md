# Risk

The risk engine is Phase 2. The type system already refuses the failures that matter most:
a silent bypass, a strategy raising its own limits, and an unapproved increase in real
capital.

## The decision

`RiskDecision` lists every check it ran. It can be `approved` only when every check passed
and the approved quantity is positive. A rejection must name a failed check and approve
zero. Checks in one decision have unique names. Construction fails otherwise, so a caller
cannot assemble an approval that hides a failure.

The approved quantity cannot exceed the intent, and the decision cannot be timestamped
before the intent. `ApprovedOrderIntent` ties the two together and is what execution
accepts.

## What a strategy cannot do

`StrategySpec.risk_overrides_allowed` is the literal `"none"`. There is no other legal
value. Position sizing is `fixed_contracts`, `fixed_dollars`, or `fractional_kelly`, and a
Kelly fraction above one half is rejected by the type. That is the "no unrestricted Kelly"
rule. `RiskEngine` applies the caps: per trade, per event, total deployed, bankroll,
realized loss, realized drawdown, book age, spread, and displayed liquidity. A cap clips
the approved quantity. A failed check rejects the intent, and `seal` will not build an
`ApprovedOrderIntent` from that decision.

`CapitalEnvelope` on a `Deployment` is the money bound. A live deployment cannot be
`approved` or `active` without a human `approved_by`.

## Lifecycle

States: `draft`, `research`, `backtested`, `validated`, `paper`, `shadow_live`,
`live_small`, `live`, `degraded`, `paused`, `retired`. Transitions are an allow-list.
`retired` has none.

Moving up in real-capital rank (`live_small`, `live`, and `degraded` back to `live_small`)
requires a `HumanApproval` recorded before the transition, and an agent actor cannot apply
that transition even if an approval object is attached. Moving down (`live` to `degraded`,
anything to `paused` or `retired`) needs no approval, so a halt is not stuck waiting for a
person.

## Kill switches

`RiskEngine.halted` is true when any of these is on: the in-process kill switch
(`kill` / `resume`), `trading_enabled=False` (the flag a later database row will store),
a `HALT` file from `halt_sentinel` (the name is `HALT`), or `ENTROPYTRADE_TRADING_ENABLED` set to
anything other than `true` in the environ mapping passed in. A halt rejects new orders.
It does not cancel resting orders and it does not liquidate. `resume` clears only the
in-process switch. There is no dashboard button yet; that button will call `kill`.

## Limits the engine will enforce

Phase 2 enforces per-trade, per-event, total deployed, and bankroll caps, plus realized
loss, realized drawdown, book age, spread, and minimum displayed liquidity. Still open:
per series, correlated exposure, open-order count, order rate, maximum slippage, minimum
net edge, model age, and time since reconciliation. No martingale. The correlated-event
cap matters for weather: every strike of one city-day is the same bet.

`EdgeEstimate` keeps the pieces separate. `raw_edge` is model probability minus the
executable price of the outcome being bought. `net_edge` subtracts fee, expected slippage,
latency, fill uncertainty and model uncertainty. A 70% probability against a 69¢ ask is a
negative net edge once costs are included, and the type makes that arithmetic visible.

## Decay

`monitoring.decay` reads a sequence of `ShadowComparison` rows. The recent mean
of print minus fill price, skipping gaps, is decay when it is strictly below a
caller-supplied threshold. The flag proposes one allow-listed downward state
(`live` to `degraded`, `paper` to `paused`, `backtested` to `research`) and can
halve quantity on the 0.01 grid. It never proposes `live` or `live_small` and
never returns a larger quantity. An agent can apply the downward transition.
The same agent still cannot apply a capital increase. The module does not call
`attempt_submit` or `KalshiGateway`. Model drift, calibration, feature drift,
and live-versus-backtest divergence are not scored, because a comparison does
not carry those series.
