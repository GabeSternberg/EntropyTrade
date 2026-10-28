# EntropyTrade

Private, single-user Kalshi research and backtesting software, with eventual automated
trading under explicit approval and deterministic risk limits. Daily-high temperature
markets are the first vertical. The goal is a reproducible scientific workflow that can
reject weak strategies as reliably as it can find promising ones.

**Current state:** read-only market collection, generic point-in-time Parquet datasets,
real forward weather capture, versioned features and event-level probability models.
The real historical sample remains too small and lacks certified forecasts/scalar labels;
complete fitting/calibration is verified separately on synthetic data. Provider-backed agent research is configurable with bounded evidence tools; real provider
verification needs a dedicated research key. The integrated `research-and-test` command now connects candidates, models, replay and
ranked diagnostics. A template-only local research website and Bitcoin forward adapter are implemented
in `99e2fbc`; reviewed commit `18be50c` includes the SQLite acceptance repair and retained evidence.
The October 26 browser run passed all four then-documented website workflows through
isolated Playwright Chromium against the real backend, including public captures,
incomplete acquisition, downloads, cancellation and restart persistence. See the
[browser evidence](data/workbench-review/20261026T203717Z/README.md)
and [operation and exact limitations](docs/workbench.md). V1 is incomplete; see
[project context](PROJECT_CONTEXT.md). The [retained Bitcoin workflow](docs/bitcoin-history.md)
now replays original receipts, reconciles later official binary results and conditionally
fits temporal binary models through the same experiment engine. Actual inputs remain
sparse and current browser/network acceptance is blocked; empirical second-family evaluation
and continuous shadow remain incomplete. Production trading
is disabled; the Kalshi gateway refuses orders.

## Setup and checks

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Make.

```bash
uv sync --locked
uv run entropytrade
uv run entropytrade-web    # private localhost website; requires provisioned dependencies
make check                 # Ruff lint/format, strict mypy, pytest + Hypothesis
```

Without arguments the CLI prints the version and default mode (`read_only`).
See [data commands](docs/data-platform.md) for `collect`, `health`, `dataset` and `inspect`.
`.env.example` lists configuration names; no credentials are required
for the offline suite. [Weather/model commands](docs/weather-modeling.md) cover forward capture,
features, real-data insufficiency diagnostics and the explicitly synthetic full proof. In a workspace with a read-only home cache, set
`UV_CACHE_DIR=/tmp/entropytrade-uv`. The Compose services currently run the same version
command and exit. They are process placeholders.

See [agent research operations](docs/agent-research.md) and the
[research-to-experiment guide](docs/experiments.md) for one-command real/offline/synthetic runs.

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
translates them to contract probabilities. `agents/` now runs configurable typed research; TestModel remains the explicit mock mode. `experiments/` connects family-neutral adapters,
model predictions, replay and statistical comparison. `strategy_registry/` provides SQLite lineage and a small local HTML view;
`frontend/` contains the local research workbench.

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
