# Security

Phase 0 has no credentials and no network client. The rules below are what later phases
have to keep true.

## Secrets

`.env.example` has names only. `.env`, `*.pem` and `*.key` are gitignored. A production
Kalshi private key is never committed, logged, sent to a model, or mounted into a research
container. The execution process is the only process that receives the trading key. The
collector, because Kalshi requires a key even for public WebSocket market data, gets a
separate read-scoped key.

The SDK can load a key from the environment and defaults to the production host. The
gateway will not call `from_env()`. It will refuse to start when `KALSHI_ALLOW_UNKNOWN_HOST`
is set, because that variable redirects signed requests at the process level.

## Modes

`TradingMode` defaults to `read_only`. `resolve_trading_mode` rejects `live` unless the
environment is production and `ENTROPYTRADE_LIVE_TRADING_ENABLED` is exactly `true`.
`demo` mode must target the demo host. `configs/live/config.yaml` is not the default
config, and selecting it is still not enough without the environment flag.

`require_order_submission` is the choke point on the gateway. Read-only, backtest, paper
and shadow cannot submit or cancel. Paper trading simulates; it does not mean "log and
drop" (that pattern, in one of the audited bots, was also controlled by a flag the
settings object never read).

## Agents

PydanticAI is confined to `entropytrade.agents` and is not installed yet. Agents return
pydantic models. Tools added in Phase 5 are read-only data accessors. No agent is given a
tool that calls `submit_order`. Output validators enforce universe and price bounds;
`RiskDecision` remains the authority. Tests set `ALLOW_MODEL_REQUESTS = False`.
Instrumentation stays off unless it points at a local collector with content excluded.

Generated Python is out of scope until a real container exists. See
[`strategy-spec.md`](strategy-spec.md).

## Supply chain

`kalshi-sdk` is pinned at `17.1.0`. It had 17 major versions in
about five months from one maintainer, and response models mark fields required, so an
unchanged pin can start failing when Kalshi removes a field. Upgrades are deliberate and
go through the gateway's contract tests. `uv.lock` is committed.

No third-party source is vendored. If that changes, the file lands in `vendor/` with its
licence and the commit it came from, and [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)
is updated in the same change.

## Logging

Not built yet. When it is, logs are structured JSON and must not include key material,
request signatures, or raw order payloads that fail validation (the SDK's WebSocket parser
currently logs those). Correlation ids are `run_id`, `strategy_id`, `deployment_id`,
`market_ticker`, `intent_id`, `client_order_id`, `agent_run_id`.
