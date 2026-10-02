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
rule, encoded early; Phase 2 still applies the real caps, fees and shrinkage.

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

## Kill switches, later

Phase 2 implements the five stops from the spec: dashboard pause, a database flag, a
`HALT` sentinel file, the environment flag, and an automatic risk halt. Tripping one
rejects new orders immediately. Cancelling resting orders is a separate, explicit action.
Resuming after an automatic halt is also explicit. None of this exists yet; the mode gate
above is the only stop in Phase 0.

## Limits the engine will enforce

Per order, per contract, per event, per series, total deployed capital, correlated
exposure, daily and weekly loss, drawdown, open-order count, order rate, minimum
liquidity, maximum spread, maximum slippage, minimum net edge, data age, model age, time
since reconciliation, and unresolved `unknown` orders. No martingale. The correlated-event
cap matters for weather: every strike of one city-day is the same bet.

`EdgeEstimate` keeps the pieces separate. `raw_edge` is model probability minus the
executable price of the outcome being bought. `net_edge` subtracts fee, expected slippage,
latency, fill uncertainty and model uncertainty. A 70% probability against a 69¢ ask is a
negative net edge once costs are included, and the type makes that arithmetic visible.
