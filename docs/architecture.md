# Architecture

EntropyTrade is one user's private research and trading system for Kalshi. The long-term
workflow is discover, formalize, collect, model, price, backtest, validate, approve, paper
trade, risk-check, execute, monitor, adapt. Phase 0 builds none of the engines. It fixes the
types and the boundaries those engines have to respect.

The full requirements are [`project-spec.md`](project-spec.md). This file records the
architecture as it stands after the open-source audit, including where the spec's plan was
adjusted. The audit itself is [`external-repositories.md`](external-repositories.md).

## Boundary

```text
research agents  ->  StrategySpec  ->  backtest / validation  ->  human approval
                                                                    |
                                                                    v
strategy evaluator  ->  OrderIntent  ->  risk engine  ->  ApprovedOrderIntent
                                                                    |
                                                                    v
                                          execution engine  ->  ExchangeGateway  ->  Kalshi
```

Agents never receive an order-placing tool and never see production credentials. The risk
engine is a deterministic gate: a `RiskDecision` cannot be approved while any check failed.
The execution engine is the only process that holds a trading key, and it accepts only an
`ApprovedOrderIntent`.

`TradingMode` defaults to `read_only`. Only `demo` and `live` may submit orders, and `live`
additionally requires the production environment plus
`ENTROPYTRADE_LIVE_TRADING_ENABLED=true` in that process.

## Packages

`backend/src/entropytrade/domain/` is venue-neutral. Money is `Decimal` on fixed grids
(prices 4 dp, contract counts 2 dp, money 6 dp, matching Kalshi's wire formats). Timestamps
are timezone-aware and stored as UTC. Identifiers that cross a process boundary are
client-generated UUIDs. Content hashes (`sha256:`) identify specs, rule texts and, later,
dataset manifests.

`exchange/gateway.py` defines `ExchangeGateway`. The Kalshi SDK is not a dependency yet.
When Phase 1 adds it, the import is allowed only under `exchange/kalshi/`, and SDK models
are converted to domain types before they leave that package. Ruff bans `kalshi` and
`pydantic_ai` imports everywhere else.

Other packages (`backtest`, `risk`, `execution`, `agents`, ...) exist as named boundaries
with a docstring and no behaviour. Their phases are listed in [`../STATUS.md`](../STATUS.md).

## What the audit changed

- **Transport.** `kalshi-sdk` 17.1.0 (import name `kalshi`) is the right dependency, pinned
  exactly, with its own retries turned off so a rate-limit budgeter can see every 429.
  Its WebSocket sequence tracking covers only the order book and order-group channels.
  Fills and user orders have no sequence numbers and are lossy by default, so REST
  reconciliation stays mandatory. FIX exists but is not a reason to adopt the SDK.
- **Credentials.** Kalshi authenticates every WebSocket, including public market data.
  "Only the execution process holds credentials" therefore means two keys: a read-scoped
  key for the collector and a trading key for execution. The SDK defaults to production
  and honours `KALSHI_ALLOW_UNKNOWN_HOST`; the gateway must construct the environment
  explicitly and refuse to start if that variable is set.
- **Order outcomes.** A successful order response that fails SDK validation raises a raw
  pydantic `ValidationError` after the order is live, and the SDK drops Kalshi's error
  `code`. Any submit that is not a definite 4xx is an unknown outcome and is resolved by
  `client_order_id`.
- **Weather settlement.** KXHIGH* markets, including Philadelphia (`KXHIGHPHIL`, station
  CLIPHL), settle on The Weather Company as of the 2026-08-14 contracts, not the NWS
  Daily Climate Report the spec assumed. Rules text is versioned data. A strategy does
  not trade a contract whose resolution source it cannot parse.
- **Nothing audited is our backtester, paper broker, or risk engine.** Those repos are
  references for loop shape, reconciliation posture and run artifacts. Their accounting
  and fill models have correctness bugs (see the audit). We reimplement behind our types.
- **PydanticAI** is the agent layer, as the slim package with Anthropic and OpenAI, and
  only inside `agents/`. It is not a dependency until Phase 5. The application is ordinary
  Python orchestration, not an agent graph.
- **pmxt** is not a dependency. Its Kalshi trading adapter is wrong, money is float, and
  credentials would cross a Node sidecar. A few schema ideas (venue field, outcome as its
  own entity, build-then-submit) are already reflected in the domain types.

## Processes

Docker Compose names four processes that share one image: `api`, `collector`, `research`,
`execution`. Phase 0 runs the same version command in each. Later, the collector and the
execution worker are the only processes with Kalshi keys, and they are different keys.
No Kubernetes, Kafka, or Redis.

## Clocks and replay

Code that needs the current time takes a `Clock`. `SystemClock` is wall time.
`SimulatedClock` only moves forward and is what the backtester will use. A backtest must
not call `datetime.now`.
