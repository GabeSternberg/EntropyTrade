# Architecture

EntropyTrade is a private single-user research system. The intended workflow and safety
principles remain in [project-spec.md](project-spec.md). [Capabilities](capabilities.md)
records implemented/tested/external/operational status; [roadmap](roadmap.md) governs work.

## Boundaries

```text
research agents -> StrategySpec -> deterministic experiments -> human approval
strategy evaluator -> OrderIntent -> risk gate -> ApprovedOrderIntent -> paper broker
                                                                    -> future executor
```

Agents have no order tool. Production keys belong only in an eventual isolated execution
process. Authenticated public WebSockets require a separate read-scoped collector key.
`KalshiGateway` always reports `read_only` and refuses submit/cancel. The mock submit gate
only accepts demo mode; production submission is unwired even when a live flag is present.
Mode types and approval records are safeguards, not evidence of a working live executor.

## Implemented package seams

- `backend/src/entropytrade/domain/` owns venue-neutral Pydantic models, exact Decimal
  grids (price 4 dp, quantity 2 dp, money 6 dp), UTC timestamps, orders, rules, StrategySpecs,
  run provenance and lifecycle approvals. Content hashes identify versioned records.
- `exchange/gateway.py` defines the protocol. SDK objects stay in `exchange/kalshi/` and
  are mapped to domain types. The pin is `kalshi-sdk==17.1.0`, retries are disabled, and
  environment/host selection is explicit. Portfolio/order/fill reads remain unimplemented.
- `exchange/{feed,book,sequence}.py` maintain replayable state; `kalshi/{wire,stream}.py`
  decode envelopes and integrate SDK book sequence checks. `session.run_connections`
  accepts supplied iterators. R1 `collector/service.py` and `kalshi/socket.py` add the live SDK connection/raw-receipt
  service with recovery, freshness, rate pacing and bounded resources.
- `storage/recorder.py` writes SQLite WAL raw bodies, metadata/rules and frames/trades.
  R1 adds session-aware receipts/facts, unsequenced persistence, atomic integrity evidence
  and an explicit v1→v2 migration; authenticated sustained operation still needs verification.
- `portfolio/`, `execution/paper.py` and `risk/` implement the ledger, simulated fills,
  caps and kill/HALT gate. Reconciliation compares supplied snapshots, not a real account.
- `backtest/replay.py` offers as-of decision views and paper replay; its chronology,
  capacity and split-bound limitations are recorded in capabilities. Holdout is refused
  at this interface; there is no final holdout evaluator yet.
- `weather/` contains recorded-source parsers and studies. Ten legacy metadata loaders
  now share `nws_metadata.py`; other exploratory families await consumer-driven consolidation.
  `data/` now provides generic point-in-time Parquet datasets and a consistent collector
  snapshot reader. R2 `features/` and `ml/` provide a versioned causal matrix and fitted probability/calibration
  pipeline; real empirical fitting is still data-blocked.
- `agents/` owns all PydanticAI imports. Operational research uses configurable providers, restricted evidence projections,
  typed multi-hypothesis/spec/critic output and independent gates. Explicit opt-in scopes
  provider calls in one isolated worker; tests retain TestModel and default refusal. `strategy_registry/` stores local lineage and exports MLflow parameters;
  its simple HTML registry/HALT endpoint is not the intended dashboard.

Ruff and architecture tests enforce SDK/agent import boundaries. These are code-level
boundaries, not OS credential isolation. No arbitrary generated Python is accepted.

## Data and time

Immutable raw receipts should feed normalized datasets, versioned features, fitted models
and experiment artifacts. This is the target architecture; currently the public study tree
is the main committed data source. SQLite serves transactional local state; bulk analytics
may use Parquet/DuckDB/Polars after a concrete R1 need. Do not add distributed infrastructure.

`select_as_of` filters availability and revisions, and `Clock` supports injected/system/
simulated time. A provider clock must first be verified: legacy rules assigning midnight
availability do not become factual because they satisfy the type. Prints/candles must retain
lower execution fidelity and cannot imply displayed size. Preserve settlement source and
rules versions; CLI weather observations do not override a Weather Company contract.

## Processes and operations

The eventual local processes are API/dashboard, read-only collector, research/backtest
worker and isolated executor. Compose names these but currently runs the CLI version
command in all four and exits. No persistent service is established by that configuration.
R1 builds the dataset command and collector; later milestones add models/agents/experiments,
shadow operation and a private FastAPI/React UI. No SaaS, Kafka, Redis or Kubernetes needed.

The historical [reuse audit](external-repositories.md) explains package/reference choices.
Recheck current API, license and compatibility before substantial new reuse or upgrades.
