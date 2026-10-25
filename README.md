# EntropyTrade

Private, single-user Kalshi research and backtesting software, with eventual automated
trading under explicit approval and deterministic risk limits. Daily-high temperature
markets are the first vertical. The goal is a reproducible scientific workflow that can
reject weak strategies as reliably as it can find promising ones.

**Current state:** read-only market collection, generic point-in-time Parquet datasets,
real forward weather capture, versioned features and event-level probability models.
The real historical sample remains too small and lacks certified forecasts/scalar labels;
complete fitting/calibration is verified separately on synthetic data. Provider-backed agent research is configurable with bounded evidence tools; real provider
verification needs a dedicated research key. Automated experiments and continuous shadow
remain later work. Production trading
is disabled; the Kalshi gateway refuses orders.

## Setup and checks

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Make.

```bash
uv sync --locked
uv run entropytrade
make check                 # Ruff lint/format, strict mypy, pytest + Hypothesis
```

Without arguments the CLI prints the version and default mode (`read_only`).
See [data commands](docs/data-platform.md) for `collect`, `health`, `dataset` and `inspect`.
`.env.example` lists configuration names; no credentials are required
for the offline suite. [Weather/model commands](docs/weather-modeling.md) cover forward capture,
features, real-data insufficiency diagnostics and the explicitly synthetic full proof. In a workspace with a read-only home cache, set
`UV_CACHE_DIR=/tmp/entropytrade-uv`. The Compose services currently run the same version
command and exit. They are process placeholders.

See [agent research operations](docs/agent-research.md) for offline/live commands and limitations.

## Architecture

```text
research -> typed StrategySpec -> deterministic experiments -> review/approval
strategy -> OrderIntent -> deterministic risk -> paper execution
                                             -> future isolated execution worker
```

`backend/src/entropytrade/domain/` owns exact Decimal accounting, UTC timestamps, market
semantics and lifecycle types. `exchange/kalshi/` contains the pinned SDK boundary;
`storage/`, `portfolio/`, `risk/`, `backtest/` and `execution/` provide reusable primitives.
`data/` now builds generic point-in-time datasets; `collector/` runs the read-only feed.
`weather/` includes recorded-data research, including legacy exploratory helpers.
`features/` builds causal matrices; `ml/` fits/calibrates temperature distributions and
translates them to contract probabilities. `agents/` now runs configurable typed research; TestModel remains the explicit mock mode. `strategy_registry/` provides SQLite lineage and a small local HTML view;
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
