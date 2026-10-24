# EntropyTrade

Private, single-user Kalshi research and backtesting software, with eventual automated
trading under explicit approval and deterministic risk limits. Daily-high temperature
markets are the first vertical. The goal is a reproducible scientific workflow that can
reject weak strategies as reliably as it can find promising ones.

**Current state:** tested foundations and stored-data studies; no operational end-to-end
research system, fitted probability models, continuous collector, or continuous shadow
trading. The Kalshi gateway refuses order submission. Production trading remains disabled.

## Setup and checks

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Make.

```bash
uv sync --locked
uv run entropytrade
make check                 # Ruff lint/format, strict mypy, pytest + Hypothesis
```

The CLI prints the version and default mode (`read_only`); it does not start a collector
or research run. `.env.example` lists configuration names; no credentials are required
for the offline suite. In a workspace with a read-only home cache, set
`UV_CACHE_DIR=/tmp/entropytrade-uv`. The Compose services currently run the same version
command and exit. They are process placeholders.

## Architecture

```text
research -> typed StrategySpec -> deterministic experiments -> review/approval
strategy -> OrderIntent -> deterministic risk -> paper execution
                                             -> future isolated execution worker
```

`backend/src/entropytrade/domain/` owns exact Decimal accounting, UTC timestamps, market
semantics and lifecycle types. `exchange/kalshi/` contains the pinned SDK boundary;
`storage/`, `portfolio/`, `risk/`, `backtest/` and `execution/` provide reusable primitives.
`weather/` includes recorded-data research, including legacy exploratory helpers.
`agents/` currently uses scripted PydanticAI TestModel outputs. `features/` and `ml/` are
placeholders. `strategy_registry/` provides SQLite lineage and a small local HTML view;
`frontend/` is a placeholder.

LLMs never control money. Historical information requires verified availability at the
decision time. Candles and prints never establish executable liquidity. No profitable
strategy has been validated.

## Start here

1. [Status and exact next action](STATUS.md)
2. [Capability inventory and correctness risks](docs/capabilities.md)
3. [Research results and limitations](docs/results.md)
4. [Active capability roadmap](docs/roadmap.md)
5. [Phase 4 thematic summary](docs/phase-reports/phase-4-consolidated.md)

The [original specification](docs/project-spec.md) remains authoritative for product
principles; the new roadmap supersedes its historical phase sequence.
[Architecture](docs/architecture.md), [reuse audit](docs/external-repositories.md) and
[specialist docs](docs/backtesting.md) provide deeper context.
[Legacy index](docs/phase-reports/README.md) retains all original reports and snapshots.
