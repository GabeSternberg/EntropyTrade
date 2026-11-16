# EntropyTrade

Private, single-user Kalshi research, modeling, backtesting and paper/shadow software.
V1 has no real-money execution. Daily-high temperature
markets are the first vertical. The goal is a reproducible scientific workflow that can
reject weak strategies as reliably as it can find promising ones.

**Current state:** read-only market collection, generic point-in-time Parquet datasets,
real forward weather capture, versioned features and event-level probability models.
The real historical sample remains too small and lacks certified forecasts/scalar labels;
complete fitting/calibration is verified separately on synthetic data. Provider-backed agent research is configurable with bounded evidence tools; real provider
verification needs a dedicated research key. The integrated `research-and-test` command now connects candidates, models, replay and
ranked diagnostics. The local research website and Bitcoin forward adapter were first implemented
in `99e2fbc`; reviewed commit `18be50c` includes the SQLite acceptance repair and retained evidence.
The October 26 browser run passed all four then-documented website workflows through
isolated Playwright Chromium against the real backend, including public captures,
incomplete acquisition, downloads, cancellation and restart persistence. See the
[browser evidence](data/workbench-review/20261026T203717Z/README.md)
and [operation and exact limitations](docs/workbench.md). V1 is incomplete; see
[project context](PROJECT_CONTEXT.md). The [retained Bitcoin workflow](docs/bitcoin-history.md)
now replays original receipts, reconciles later official binary results and conditionally
fits temporal binary models through the same experiment engine. Actual retained contracts now reconcile to four finalized official results; real-receipt
browser interaction, downloads and restart acceptance pass. History remains insufficient
(4 fitting events on 3 dates, only NO targets, no validation dates); empirical second-family
evaluation remains incomplete. Bitcoin is optional, not the mandatory second family;
future major family selection requires user approval. A continuous read-only shadow
monitor now connects frozen research candidates to durable forward capture, decisions,
risk evidence, later official outcomes and browser inspection. Authentic fitted forward
models and certified fees remain unavailable, so actual intentions block.
Sized public books are retained with explicit collection bounds. Earlier shadow browser acceptance passed. The website now offers bounded provider-backed
research with server configuration and fresh per-run consent; typed candidates, deterministic
gates and downloadable provider failures use durable isolated jobs. Controlled provider
HTTP plus real-browser cancellation/restart evidence passes; external verification remains
blocked without separately authorized research credentials. The fresh locked-install and
broader recovery results are recorded in [current evidence](data/provider-review/20261029/README.md).
Offline workspace recovery preserves original receipts and model/holdout boundaries. See [local operation and recovery](docs/local-recovery.md), the incomplete
[V1 acceptance matrix](docs/v1_acceptance.md), the
[shadow operating guide](docs/shadow-tracking.md) and the earlier
[executed evidence and collection decision](data/bitcoin-history-review/20261029T001500Z/README.md). Authentic read-only forward collection can now run headlessly on GitHub-hosted runners;
see [forward operator](docs/forward-operator.md). Production trading
is disabled; the Kalshi gateway refuses orders.

## Setup and checks

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Make.

```bash
uv sync --locked
uv run entropytrade
uv run entropytrade-web    # private localhost website at http://127.0.0.1:43128
make check                 # Ruff lint/format, strict mypy, pytest + Hypothesis
```

Without arguments the CLI prints the version and default mode (`read_only`).
See [data commands](docs/data-platform.md) for `collect`, `health`, `dataset` and `inspect`,
and [family screening](docs/family-selection.md) for `family-screen`.
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
`frontend/` contains the local website: an application shell (Overview, Market Explorer,
Strategy Lab, Backtesting, Paper Trading, Data & Operations, Settings) around the research
workbench, with a clearly labeled browser-only Demo Mode. See [frontend/src/README.md](frontend/src/README.md).

LLMs never control money. Historical information requires verified availability at the
decision time. Candles and prints never establish executable liquidity. No profitable
strategy has been validated.

## Start here

1. [Status and exact next action](STATUS.md)
1. [Autonomous research lifecycle and readiness dashboard](docs/autonomous-research.md)
2. [Capability inventory and correctness risks](docs/capabilities.md)
3. [Research results and limitations](docs/results.md)
4. [Active capability roadmap](docs/roadmap.md)
5. [Phase 4 thematic summary](docs/phase-reports/phase-4-consolidated.md)

The [original specification](docs/project-spec.md) remains authoritative for product
principles; the new roadmap supersedes its historical phase sequence.
[Architecture](docs/architecture.md), [reuse audit](docs/external-repositories.md) and
[specialist docs](docs/backtesting.md) provide deeper context.
[Legacy index](docs/phase-reports/README.md) retains all original reports and snapshots.
