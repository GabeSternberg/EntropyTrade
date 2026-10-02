# EntropyTrade — Project Status

> **Single source of truth for "where are we?"** A fresh agent given only this
> file (plus the repo) should be able to resume. Update it at the end of every
> phase: mark the phase complete, link its checkpoint report, and move
> **Next steps** to the next phase.

Last updated: 2026-10-02 · Current phase: **Phase 0 — complete**. Next is Phase 1, and it has not been started.

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
2. Off-plan work gets a sub-phase number (e.g. 5.50, 5.51) added to the table
   below, never silently folded into another phase.
3. If a finding makes the spec's architecture worse, flag it in the phase
   report rather than following the spec blindly.
4. Never add live trading, order submission or production credentials before
   the phase that explicitly calls for it (Phase 9, after explicit approval).

## Phase overview

| Phase | Name | Status | Report |
| --- | --- | --- | --- |
| 0 | Open-source audit + project skeleton | **complete** | [phase-0.md](docs/phase-reports/phase-0.md) |
| 1 | Read-only Kalshi gateway + market recorder | planned | — |
| 2 | Accounting + paper broker + risk foundation | planned | — |
| 3 | Point-in-time backtesting engine | planned | — |
| 4 | First weather dataset + baseline models | planned | — |
| 5 | Agentic research pipeline (PydanticAI) | planned | — |
| 6 | Strategy registry + experiment tracking + dashboard | planned | — |
| 7 | Structural / arbitrage scanner | planned | — |
| 8 | Live paper + shadow validation | planned | — |
| 9 | Live-small execution (explicit approval required) | planned | — |
| 10 | Live decay detection + automatic downsizing | planned | — |
| 11 | Optional expansion (more markets, cross-venue, FIX, DL) | planned | — |

Phase definitions are in spec §40. Summary of each phase's acceptance bar:

- **Phase 0**: inspect the external repos and their licenses; reuse matrix
  (`docs/external-repositories.md`); `THIRD_PARTY_NOTICES.md`; Kalshi docs
  reference; uv/Ruff/mypy/pytest/Hypothesis/pre-commit; architecture docs;
  core domain types and interfaces. No trading logic.
- **Phase 1**: `ExchangeGateway` + `KalshiGateway` (READ_ONLY), discovery,
  rules storage, REST book snapshots, WebSocket deltas/trades, reconnect,
  sequence integrity, API limits, persisted raw + normalized data, health.
  Must run for hours in demo, survive restarts and replay recordings.
- **Phase 2**: account/positions/orders/fills/settlements/P&L, PaperBroker,
  deterministic risk engine, kill switch, reconciliation against demo.
- **Phase 3**: point-in-time replay engine, fees/spread/latency/slippage,
  partial fills where data permits, settlement, artifacts, splits and
  walk-forward; a deliberately leaky strategy must be blocked.
- **Phase 4**: first weather vertical (daily-high temperature), point-in-time
  forecasts, baseline models, forecasting *and* trading evaluation.
- **Phase 5**: Research → Hypothesis → Quant → Critic agents producing
  StrategySpecs, auto-backtested; no holdout access, no trading.
- **Phase 6**: lineage, versioning, MLflow, promotion states, approvals, dashboard.
- **Phase 7**: deterministic constraint/arbitrage detection, paper/shadow only.
- **Phase 8**: live paper + shadow validation against real books, no real orders.
- **Phase 9**: tiny live envelope for one approved strategy, only after approval.
- **Phase 10**: drift/decay detection and automatic downsizing.
- **Phase 11**: optional expansion.

## Next steps

Phase 1 — read-only Kalshi gateway and market recorder. Do not start it until
the user explicitly says to continue.

Scope, and only this scope: pin `kalshi-sdk==17.1.0`; `KalshiGateway` behind
`ExchangeGateway` in `READ_ONLY` (explicit `KalshiConfig.demo()` /
`.production()`, never `from_env()`, refuse `KALSHI_ALLOW_UNKNOWN_HOST`,
`max_retries=0`); market, event and series discovery; rules storage with
`rules_hash` and settlement-source-by-date; REST books from `orderbook_fp`;
WebSocket connect, book deltas and the trade feed; reconnect; our own sequence
checks for trade and lifecycle on top of the SDK's book-gap handling; API
limits from `GET /account/limits` via a wrapping transport; persist metadata,
rule versions, trades, book snapshots and deltas, and lifecycle events; health.
No order submission. A read-scoped key for the collector, separate from any
trading key. Recorded data must be replayable.

Acceptance from spec §40: hours on demo or read-only production, restart
without corruption, reconnect after a dropped socket, and a detected sequence
gap.

Read [`docs/external-repositories.md`](docs/external-repositories.md) and the
Phase 0 report before writing the adapter. The audit changed several spec
assumptions (Weather Company settlement, two API keys, no vendored bot code,
exact SDK pin). Those are decisions waiting on the user; do not silently
revert them.

## Checks

On 2026-10-02, `make check` passed: ruff clean, mypy strict clean (48 source
files), pytest 57 passed. `uv sync` then `make check`. Default mode is
`read_only`. `uv` is not on the default `PATH` in every shell; it lives at
`~/.local/bin/uv` (0.12.22) in the environment that built this.

## How to resume (fresh agent)

1. Read this file, then `docs/project-spec.md`, then `docs/architecture.md`.
2. Read the latest phase report under `docs/phase-reports/`.
3. Set up: `uv sync` (Python 3.12+), then `make check` (lint + typecheck + tests).
4. Kalshi API reference: `.agents/skills/kalshi-docs/` (see `README.md`).
5. Continue with the phase listed under **Next steps**, and only that phase, and only after the user explicitly says to continue.
