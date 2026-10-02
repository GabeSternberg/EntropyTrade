# Kalshi Agentic Research & Automated Trading Platform

We are building a private, single-user prediction-market research, backtesting, and automated trading platform initially focused on Kalshi.

This is **not a SaaS product**. It can run locally or on a private server and only needs to support one user. Optimize for correctness, robustness, reproducibility, and reuse of existing open-source work rather than multi-user scaling, distributed infrastructure, or unnecessary enterprise complexity.

The long-term workflow should be:

**Discover → Formalize → Collect → Model → Price → Backtest → Validate → Approve → Paper Trade → Risk Check → Execute → Monitor → Adapt**

The user should eventually be able to do something like:

> "Look at Philadelphia daily-high temperature markets. I think forecast revisions in the last 12 hours may contain useful information. Research that and also search for other potentially useful signals."

The system should then:

1. Research the market and available information.
2. Generate multiple explicit, testable strategy hypotheses.
3. Identify required datasets.
4. Build point-in-time features.
5. Optionally train statistical/ML/DL models.
6. Turn predictions into trade rules.
7. Backtest every candidate realistically.
8. Reject bad or overfit strategies automatically.
9. Present successful candidates to the user.
10. Allow the user to promote one into paper trading.
11. Allow later promotion into limited live trading.
12. Automatically trade within a pre-approved risk envelope.
13. Continuously monitor whether live performance still resembles backtest expectations.
14. Reduce exposure or halt strategies that deteriorate.
15. Maintain a complete audit trail explaining where every strategy came from and why every trade occurred.

Do not assume this system will be profitable. A fundamental design goal is being able to determine reliably that an apparently promising strategy **does not work**.

---

# 1. NON-NEGOTIABLE ARCHITECTURAL PRINCIPLES

## 1.1 LLMs research; deterministic systems control money

LLM agents must never directly send orders to Kalshi.

The flow must be:

`Agent/research → StrategySpec → validation/backtest → approval → strategy intent → deterministic risk engine → execution engine → Kalshi`

The execution process should be the only component with access to production Kalshi credentials.

The research/LLM process should ideally have **no production trading credentials at all**.

An agent cannot override:

- account exposure limits,
- strategy exposure limits,
- loss limits,
- liquidity requirements,
- stale-data checks,
- spread limits,
- market-rule checks,
- kill switches,
- live-capital approvals.

No natural-language instruction should bypass those controls.

---

# 2. DO NOT REINVENT THE WHEEL

Before implementing anything substantial, inspect the projects below.

Do not blindly copy an entire repository. Determine which components are mature enough to depend on directly, which code should be adapted/vendor-copied, and which ideas should simply be recreated behind our interfaces.

When code is copied from an external repository, preserve its license requirements and document the source in `THIRD_PARTY_NOTICES.md`.

Prefer using a package dependency over copied code when practical.

## Primary external dependencies/references

### A. `TexasCoding/kalshi-python-sdk`

**Plan: USE DIRECTLY as our primary Kalshi transport library, but hide it behind our own `ExchangeGateway` interface.**

Reasons:

- Current typed Kalshi REST API coverage.
- Async support.
- WebSocket subscriptions.
- Sequence-gap detection/reconnection.
- In-memory order-book support.
- Decimal-based pricing instead of unsafe floating-point monetary values.
- Record/replay testing utilities.
- Support for current order APIs.
- FIX support if we eventually require lower latency.
- MIT licensed.

Do NOT leak SDK-specific objects throughout the codebase.

Build:

`KalshiGateway(ExchangeGateway)`

so we can replace the SDK later without rewriting strategy/risk/backtest code.

The official Kalshi API specification/documentation remains the source of truth if the SDK and exchange ever disagree.

### B. `ammario/kalshi-docs`

**Plan: USE AS CODING/REFERENCE DOCUMENTATION.**

Install the Kalshi documentation skill for Codex if possible:

`npx add-skill ammario/kalshi-docs`

This repository mirrors current Kalshi documentation and is useful for keeping Codex from implementing against stale examples.

Official/current docs expose market data, trades, candlesticks, order books, order management, order groups, queue information, weather indexes, API-limit information, and historical endpoints.

### C. `karshincheo/kalshi-trading`

**Plan: STUDY AND REUSE SELECTED COMPONENTS/PATTERNS. Do not make it our entire foundation.**

This project is extremely relevant because it already implements:

- FastAPI backend.
- paper broker.
- strategies.
- portfolio/risk utilities.
- LLM autonomous strategy-research loop.
- temperature-market research.
- agent-generated code.
- backtesting.
- train/validation/hidden holdout concept.
- Brier/Sharpe evaluation.
- strategy accept/reject loop.
- git audit history.

Especially inspect:

- `autoresearch/loop.py`
- `autoresearch/evaluate.py`
- `autoresearch/prepare.py`
- `autoresearch/sandbox.py`
- `autoresearch/program.md`
- `services/trading_engine.py`
- `services/backtest_engine.py`
- `broker/paper_broker.py`
- risk/math utilities

However, improve its generated-code safety. AST validation plus a subprocess is not enough security if model-generated Python is considered hostile.

Our preferred solution is:

**Strategy DSL / structured StrategySpec first. Arbitrary generated Python only when necessary and only inside a real restricted worker/container.**

The repo is useful as a reference for the exact agentic loop we want.

### D. `mifisher/kalshi-weather-bot`

**Plan: REUSE/ADAPT its risk, reconciliation, weather-data, and validation ideas.**

Especially inspect:

- account-state reconciliation,
- market-rule/station parsing,
- fee-aware edge calculation,
- passive order handling,
- journaling,
- deterministic guardrails,
- walk-forward testing,
- calibration gates,
- climatology benchmark,
- historical weather ingestion,
- kill switch implementation.

The project is demo-first and heavily tested.

Important lesson from this project: its forecasting model showed predictive skill yet historical simulation did not produce positive returns after fees. That is exactly why our architecture must distinguish **predictive accuracy** from **tradable edge**.

### E. `Quentin-Piot/prediction-market-backtester`

**Plan: STUDY/ADAPT its reproducibility and backtesting engine architecture.**

Useful concepts:

- explicit execution assumptions,
- prediction-market-specific backtesting,
- reproducible run directories,
- `results.json`,
- git commit hashes,
- configs,
- timing metadata,
- `equity.csv`,
- `trades.csv`,
- fee/slippage/latency modeling,
- resumable batch backtests,
- data-quality gates.

Its current execution model does not fully solve order-book depth/partial fills, so extend rather than blindly adopting it.

### F. `Viprasol-Tech/kalshi-trading-bot`

**Plan: REFERENCE generic strategy-plugin, async, risk, Docker, testing, and dry-run patterns.**

Do not use its simplified backtester as our final backtesting foundation because realistic execution is especially important for prediction markets.

### G. `pydantic/pydantic-ai`

**Plan: USE DIRECTLY for the LLM/agent layer.**

We want:

- strongly typed agent outputs,
- model-provider independence,
- structured tools,
- structured strategy proposals,
- explicit dependencies,
- multi-agent workflows without putting critical business logic inside opaque prompts.

Use normal Python orchestration/state machines around PydanticAI rather than making the entire application an agent graph.

Agents should return Pydantic models rather than free-form prose whenever downstream code consumes their output.

### H. MLflow

**Plan: USE LOCALLY for experiment/model/agent-run tracking.**

Track:

- model training runs,
- datasets,
- hyperparameters,
- calibration results,
- metrics,
- artifacts,
- strategy identifiers,
- git hashes,
- agent research runs,
- prompts/model metadata where appropriate.

Do not rely on MLflow as the trading database.

### I. DuckDB + Parquet + Polars

**Plan: USE for analytical/time-series research data.**

Prefer immutable Parquet datasets queried through DuckDB.

Polars can be used for feature pipelines and heavy dataframe processing.

### J. SQLite

**Plan: USE for small transactional/local state.**

Examples:

- strategy registry,
- orders,
- fills,
- deployments,
- approvals,
- account snapshots,
- risk events,
- application state,
- audit records.

Enable WAL mode.

Do not store enormous historical tick/order-book data exclusively in SQLite.

### K. FastAPI

Use for the local/private control-plane API.

### L. Minimal React/Vite frontend

Build the proper dashboard only after core research/backtesting/trading logic works.

The frontend must never contain strategy logic or exchange secrets.

### M. `pmxt-dev/pmxt`

**Plan: DO NOT make this a dependency for Kalshi-only V1. Revisit when adding cross-exchange arbitrage.**

PMXT provides a CCXT-like unified API across prediction-market venues including Kalshi and Polymarket and supports self-hosted operation.

This can save significant effort later if we expand beyond Kalshi.

### N. Weather data

Our first vertical should probably be daily high-temperature markets.

Use:

- Kalshi market/rules data.
- National Weather Service for live forecasts where appropriate.
- Open-Meteo historical forecast/previous-run APIs for point-in-time model forecasts.
- settlement/observation sources specified in each Kalshi contract.
- Iowa Mesonet or equivalent archived station observations when useful.

Open-Meteo provides archived model/previous-run data, which is particularly useful because normal historical weather observations are **not equivalent** to knowing what the forecast said at the time a trade would have occurred.

Never assume a weather source determines settlement simply because it is convenient. Parse and store the Kalshi contract's actual resolution source. Kalshi explicitly defines verification sources and settlement criteria in individual market rules.

---

# 3. REPOSITORY STRUCTURE

Create a clean monorepo approximately like:

```text
/
  backend/
    src/
      app/
        api/
        agents/
        backtest/
        data/
        exchange/
        execution/
        features/
        ml/
        monitoring/
        portfolio/
        research/
        risk/
        strategies/
        strategy_registry/
        storage/
        weather/
    tests/

  frontend/
    src/

  configs/
    dev/
    paper/
    live/

  data/
    raw/
    normalized/
    features/
    backtests/
    cache/

  research/
    notebooks/
    reports/

  vendor/
    README.md

  docs/
    architecture.md
    data-model.md
    backtesting.md
    execution.md
    risk.md
    strategy-spec.md
    external-repositories.md
    security.md

  THIRD_PARTY_NOTICES.md
  pyproject.toml
  docker-compose.yml
  .env.example
  README.md
```

Use Python 3.12+ and `uv`.

Keep formatting/type/lint/test configuration from the beginning.

Suggested:

- Ruff
- mypy or pyright
- pytest
- Hypothesis for critical accounting/risk properties
- pre-commit

---

# 4. CORE DOMAIN TYPES

Create our own types independent of third-party SDKs.

Examples:

```python
Market
Event
Contract
OrderBook
OrderBookLevel
MarketSnapshot
TradePrint
OrderIntent
OrderRequest
Order
Fill
Position
PortfolioSnapshot
Settlement
FeatureObservation
Forecast
Signal
StrategySpec
StrategyVersion
BacktestRun
Deployment
RiskDecision
RiskEvent
AgentResearchRun
```

Use:

- UTC-aware timestamps everywhere internally.
- `Decimal` or fixed-point integer representation for money/prices.
- UUID/client-generated IDs for idempotency.
- immutable IDs/version hashes for datasets and strategies.

Never casually compare naive timestamps.

---

# 5. DATA ARCHITECTURE

This is one of the most important parts of the entire project.

## 5.1 Point-in-time correctness

For every piece of external information, preserve relevant timestamps such as:

```text
event_time
published_at
available_at
ingested_at
revised_at
source_id
revision_id
```

The backtester may only use information satisfying:

`available_at <= decision_time`

Do not perform historical joins based merely on date.

This must have dedicated tests designed to intentionally catch look-ahead leakage.

## 5.2 Immutable raw layer

Raw market data/external information should be append-only whenever possible.

Never overwrite historical forecast vintages with newer revisions.

Store:

```text
raw/
  kalshi/
  weather/
  news/
  economic/
  social/
```

Partition appropriately by source/date/market.

## 5.3 Normalized layer

Transform raw provider formats into internal schemas.

Every normalized record retains provenance back to raw source.

## 5.4 Feature layer

Each feature dataset must record:

- feature schema/version,
- generation code/git hash,
- raw input manifest,
- generated timestamp,
- allowed information cutoff,
- market universe,
- strategy/model version.

## 5.5 Record live market data immediately

Historical candlesticks alone will not be sufficient to reproduce all execution behavior.

Start collecting:

- order-book snapshots/deltas,
- trades,
- quotes,
- market metadata,
- lifecycle events,
- market-rule text,
- order/fill events,

as early as possible so our future research dataset becomes richer over time.

---

# 6. MARKET RULES ARE FIRST-CLASS DATA

Before allowing a strategy to trade a contract, snapshot:

- title,
- ticker,
- event,
- strike,
- close time,
- settlement time if known,
- full rules,
- rules summary,
- settlement source,
- relevant definitions,
- payout semantics,
- mutually-exclusive relationships,
- structured-target relationships where available.

Do not trade a market whose resolution semantics cannot be confidently parsed.

If rules change, create a new rules version.

A rules change should be capable of automatically invalidating or pausing a strategy.

Kalshi itself emphasizes that each market's rules specify the measured outcome and verification source.

---

# 7. STRATEGY MODEL

There are two fundamentally different classes of strategies.

## A. Informational strategies

These try to estimate reality better than the market.

Example:

`P(PHL high temperature > 74.5°F | forecasts, revisions, weather variables)`

Then compare the estimate with the actual executable price.

## B. Structural/arbitrage strategies

These exploit inconsistent prices across contracts without necessarily forecasting the underlying event better.

Examples:

- mutually exclusive outcomes,
- collectively exhaustive outcomes,
- monotonic threshold contracts,
- YES/NO parity,
- related strikes,
- duplicate/near-duplicate markets,
- eventually cross-exchange equivalent contracts.

Keep these strategy families separate because they need different validation.

---

# 8. STRATEGYSPEC

The research agent should not simply output:

> "Buy weather markets when NOAA differs from Kalshi."

It should generate structured specifications.

Create a Pydantic `StrategySpec` containing something like:

```text
strategy_id
name
version
description
hypothesis
strategy_family
market_universe
required_sources
features
model_definition
probability_calibration
entry_rules
exit_rules
minimum_edge
position_sizing
maximum_holding_period
hedging_rules
execution_preferences
risk_overrides_allowed = NONE
invalidation_conditions
assumptions
evidence
citations
generated_by
generation_run_id
created_at
```

Also retain the natural-language research report that generated it.

Where possible, translate `StrategySpec` into a constrained strategy DSL rather than arbitrary Python.

---

# 9. AGENT ARCHITECTURE

Implement logically separate roles.

They can initially be separate PydanticAI agents coordinated by normal Python.

## Research Agent

Goal:

Find relevant information and potential predictive mechanisms.

It may consume:

- user's idea,
- market rules,
- news,
- official releases,
- domain-specific APIs,
- related markets,
- historical market behavior.

Output:

`ResearchReport`

including evidence, source timestamps, hypotheses, uncertainties, and suggested data.

## Hypothesis Agent

Converts research into falsifiable statements.

Example:

> "For Philadelphia daily-high contracts 12–36 hours before settlement, upward HRRR forecast revisions greater than X°F relative to the previous run are followed by underpricing of upper temperature buckets."

Not:

> "Weather forecasts are useful."

## Quant Agent

Turns hypotheses into:

- feature definitions,
- statistical models,
- thresholds,
- entry/exit logic,
- calibration procedures,
- candidate StrategySpecs.

## Critic / Red-Team Agent

Actively looks for:

- look-ahead leakage,
- survivorship bias,
- revised-data leakage,
- ambiguous market rules,
- invalid probability assumptions,
- duplicated signals,
- data snooping,
- overfitting,
- execution assumptions,
- impossible fills,
- tiny sample sizes,
- inconsistent settlement sources,
- causal stories contradicted by timing.

This agent should try to kill strategies, not sell them.

## Backtest Analyst

Takes deterministic backtest results and summarizes why performance occurred.

It may suggest new experiments.

It may NOT alter holdout data or execution assumptions to make results prettier.

## Optional Data Scout Agent

Identifies missing data sources and proposes adapters.

---

# 10. AGENT SECURITY

Agent-generated code must never execute directly inside the live trading process.

Preferred progression:

### V1
Agent generates only typed StrategySpecs and feature/model configurations.

### V2
Allow agent-generated feature/model Python in an isolated research worker.

If arbitrary Python is eventually allowed:

- isolated Docker container/process,
- no Kalshi production credentials,
- no production database credentials,
- no unrestricted network access,
- read-only mounted dataset,
- writable temporary directory only,
- CPU limit,
- memory limit,
- timeout,
- process limit,
- artifact-size limit.

Generated code must never share a process with live execution.

---

# 11. ML / STATISTICAL MODELING

Do not add deep learning merely so the project has deep learning.

Start with appropriate baselines:

- logistic regression,
- regularized generalized linear models,
- calibrated classifiers,
- gradient-boosted trees,
- XGBoost/LightGBM if useful,
- Bayesian/hierarchical models,
- domain-specific statistical models,
- ensembles.

Calibrate probabilities using methods such as:

- isotonic regression,
- Platt/logistic calibration,

where statistically justified.

Deep learning is appropriate later if the data justifies it, for example:

- large text/news datasets,
- document embeddings,
- order-book sequences,
- multimodal sources,
- sufficiently large temporal datasets.

PyTorch can be introduced later if necessary.

The goal is accurate, calibrated probabilities and profitable executable decisions, not model complexity.

---

# 12. PREDICTION IS NOT TRADING

Every strategy must distinguish:

`model probability`

from

`executable price`

from

`expected trading value`.

Conceptually:

```text
raw_edge =
    estimated_probability
    - executable_market_probability

net_expected_edge =
    raw_edge
    - fees
    - expected_slippage
    - latency_cost
    - fill_uncertainty_reserve
    - model_uncertainty_reserve
```

A 70% prediction against a 69¢ ask may be useless.

A 70% prediction against a 55¢ ask may be interesting.

Do not evaluate models only with classification accuracy.

---

# 13. BACKTEST ENGINE

The backtester is a critical system, not a plotting utility.

It must support replay without access to future information.

## Backtest execution model

Eventually model:

- bid/ask,
- depth,
- spread,
- maker/taker behavior,
- current Kalshi fee schedule,
- maker fees where applicable,
- limit orders,
- marketable orders,
- partial fills,
- order cancellations,
- stale orders,
- execution latency,
- data latency,
- exchange rejects,
- rate limiting,
- position limits,
- settlement,
- capital lockup,
- simultaneous strategy competition,
- leg risk for arbitrage.

For data periods where only candles/trades exist, explicitly label the backtest as lower execution fidelity.

Do not silently treat last-traded price as guaranteed executable price.

Provide configurable scenarios:

- optimistic fills,
- base fills,
- conservative fills.

A strategy that only works under optimistic fills should not pass promotion.

## Reproducibility

Every run should record:

```text
run_id
strategy_id/version
StrategySpec hash
git SHA
config
dataset manifest/hash
feature version
model artifact/version
fee model/version
execution model/version
random seeds
start/end time
train/validation/holdout ranges
runtime
metrics
trades
equity curve
environment metadata
```

Adopt/adapt the reproducible artifact philosophy from `prediction-market-backtester`.

---

# 14. VALIDATION AND ANTI-OVERFITTING

This is mandatory because an automated agent can cheaply generate hundreds or thousands of hypotheses.

Without strong controls it will inevitably "discover" nonsense.

Use time-based splits:

```text
TRAIN
VALIDATION
FINAL HOLDOUT
```

The research agent can iterate using train/validation.

The final holdout should be inaccessible during hypothesis generation.

Ideally keep the final holdout evaluation behind a separate interface.

Also perform walk-forward testing.

Example:

```text
train Jan-Mar → validate Apr
train Jan-Apr → validate May
train Jan-May → validate Jun
...
```

Hyperparameter optimization must occur inside training/validation only.

A new agent-generated variant counts as another tested hypothesis.

Track the number of attempted strategies.

Implement multiple-testing protections where practical:

- Benjamini-Hochberg/FDR for large experiment families,
- bootstrap confidence intervals,
- Deflated Sharpe / comparable selection-bias diagnostics where appropriate,
- minimum observation count,
- minimum independent event count.

Do not accept:

> "Sharpe > 2"

without considering that the agents tried 2,000 strategies.

---

# 15. MODEL METRICS

Prediction metrics should include appropriate metrics such as:

- Brier score,
- log loss,
- calibration curves,
- calibration intercept/slope,
- Expected Calibration Error where appropriate,
- reliability by probability bucket.

Trading metrics:

- P&L after fees,
- return on deployed capital,
- maximum drawdown,
- CVaR / tail loss,
- Sharpe-like metrics where statistically meaningful,
- turnover,
- number of independent events,
- win/loss distribution,
- average quoted edge,
- realized edge,
- edge captured,
- fill rate,
- maker/taker mix,
- slippage,
- holding time,
- capital utilization,
- profit factor,
- P&L concentration.

Always compare against useful baselines.

For weather:

- climatology,
- raw weather forecast,
- Kalshi implied probability,
- simple calibration model.

A model can be a good forecaster and still be a bad trading strategy.

---

# 16. STRATEGY PROMOTION LIFECYCLE

Strategies should have explicit lifecycle states:

```text
DRAFT
RESEARCH
BACKTESTED
VALIDATED
PAPER
SHADOW_LIVE
LIVE_SMALL
LIVE
DEGRADED
PAUSED
RETIRED
```

Transitions should be recorded.

Agents may propose transitions but should not independently increase permitted real-capital limits.

Human approval is required when moving to a new live-capital tier.

Once approved, the system may trade autonomously inside the tier's deterministic limits.

---

# 17. PAPER TRADING VS SHADOW LIVE

Support both.

## Paper trading

Simulated fills based on live market feeds.

Useful but potentially optimistic.

## Shadow live

Generate live orders/intents as though they would be executed, but do not actually submit them.

Record:

- intended price,
- order-book state,
- expected fill,
- subsequent market events,
- whether it likely would have filled,
- realized outcome.

This provides a bridge between historical testing and funded trading.

---

# 18. EXECUTION ENGINE

The execution engine must be completely independent of research agents.

Input:

`ApprovedOrderIntent`

Output:

actual orders/fills.

Implement an explicit order state machine such as:

```text
CREATED
RISK_APPROVED
SUBMITTING
ACKNOWLEDGED
RESTING
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELLED
REJECTED
UNKNOWN
```

Use idempotent client order IDs.

On crashes/restarts:

**never assume local state is correct.**

Reconcile against Kalshi:

- balance,
- positions,
- resting orders,
- recent fills,
- settlements,
- order groups.

Borrow the reconciliation-first philosophy from the weather bot.

---

# 19. REAL-TIME DATA AND SPEED

"As fast as necessary" does not mean putting LLM calls in the execution loop.

The latency-sensitive path should be:

```text
Kalshi WebSocket
        ↓
in-memory normalized state
        ↓
deterministic strategy/arbitrage evaluator
        ↓
risk engine
        ↓
execution engine
        ↓
Kalshi order API
```

No LLM belongs there.

LLM research can run seconds/minutes/hours earlier.

Use WebSockets for live market/order data.

Use REST for:

- snapshots,
- metadata,
- recovery,
- reconciliation,
- non-latency-sensitive operations.

The Kalshi API uses account-specific read/write rate limits and exposes limit/cost information. Build a central rate-limit budgeter instead of firing requests until 429s occur.

Query account limits at startup.

Prioritize requests:

1. cancel/risk emergency,
2. order state,
3. execution,
4. live market data recovery,
5. research/background.

REST + WebSocket is enough initially.

Do **not** build FIX immediately.

If profiling later shows REST order placement is genuinely limiting profitable strategies, the chosen SDK already supports persistent FIX sessions and can be evaluated then.

---

# 20. ARBITRAGE ENGINE

Create a separate structural strategy subsystem.

Represent relationships between contracts as constraints.

Examples:

### Monotonic thresholds

For the same underlying measurement:

`P(T > 80) <= P(T > 75)`

If executable market prices violate this relationship enough to cover all costs, create an arbitrage candidate.

### Mutually exclusive outcomes

For exhaustive outcomes:

`Σ P(outcome_i) = 1`

But use **executable bid/ask prices**, not displayed midpoints.

### Complement constraints

Where contracts are exact logical complements, pricing should obey complement relationships after costs.

### Nested events

Certain markets imply logical bounds on related markets.

Before labeling anything "arbitrage", validate:

- identical settlement semantics,
- timing,
- resolution sources,
- fees,
- spread,
- available size,
- leg execution risk.

Because multiple Kalshi orders may not be atomic, an apparently risk-free arbitrage can become risky if one leg fills and another does not.

Implement:

- simultaneous-intent planning,
- minimum executable quantity,
- partial-fill handling,
- cancellation plan,
- maximum permitted leg exposure,
- timeout,
- emergency hedge/flatten behavior.

Do not describe a trade as risk-free unless the economics and execution truly lock it in.

---

# 21. PORTFOLIO MANAGER

Strategies do not receive independent wallets.

All intents flow into a portfolio layer first.

The portfolio manager should:

- combine same-direction intents,
- net opposite intents,
- recognize shared events,
- recognize logically related contracts,
- recognize common settlement drivers,
- estimate correlated exposure,
- prevent many strategies from accidentally making the same bet.

Example:

Five "different" weather strategies may all actually be:

> Philadelphia will be hotter than market expectations.

They should not each receive their full individual risk budget.

---

# 22. RISK ENGINE

This is a deterministic hard gate between strategies and execution.

Create configurable controls including:

- maximum dollars per order,
- maximum contracts per order,
- maximum exposure per contract,
- maximum exposure per event,
- maximum exposure per series/category,
- maximum total capital deployed,
- maximum correlated exposure,
- maximum daily loss,
- maximum weekly loss,
- peak-to-current drawdown limit,
- maximum open orders,
- maximum order rate,
- minimum liquidity,
- maximum spread,
- maximum acceptable slippage,
- minimum net estimated edge,
- maximum data staleness,
- maximum model age,
- maximum time since successful reconciliation,
- maximum unresolved execution state,
- maximum agent-generated strategy capital tier.

Also:

- no martingale,
- no automatic "double after a loss",
- no unrestricted Kelly sizing,
- no strategy may increase its own risk limits.

If Kelly sizing is used, use conservative fractional Kelly and shrink estimates based on model/calibration uncertainty.

During initial live deployment prefer tiny fixed/fractional risk budgets.

---

# 23. KILL SWITCHES

Provide several independent ways to stop live trading:

1. dashboard global PAUSE button,
2. database `trading_enabled=false`,
3. local `HALT` sentinel file,
4. environment-level live-trading flag,
5. automatic risk-engine halt.

Emergency halt should:

- prevent new orders immediately,
- optionally cancel resting orders,
- preserve logs,
- not automatically liquidate positions unless configured because forced liquidation can itself be harmful.

Require explicit action to resume after a serious risk halt.

---

# 24. AUTOMATIC HALT CONDITIONS

Examples:

- daily loss limit exceeded,
- drawdown exceeded,
- exchange state cannot be reconciled,
- WebSocket sequence corruption cannot be recovered,
- market data stale,
- repeated authentication errors,
- repeated order rejects,
- local/exchange positions differ,
- rules changed,
- resolution source unclear,
- model artifact missing,
- feature pipeline failed,
- live calibration deteriorates,
- live realized edge significantly deviates from backtest expectations,
- abnormal slippage,
- abnormal fill behavior,
- input distribution drift,
- strategy's sample window no longer resembles training regime.

---

# 25. LIVE DRIFT / STRATEGY DECAY

Once live, continually compare behavior against validation expectations.

Monitor:

- prediction distribution,
- calibration,
- Brier/log loss,
- quoted edge,
- realized edge,
- win rate where meaningful,
- slippage,
- spread,
- fill rate,
- holding period,
- feature distributions,
- model confidence,
- P&L distribution,
- drawdown.

Use rolling windows plus minimum samples.

Do not overreact to three losing trades.

But allow deterministic downgrade:

```text
LIVE
→ DEGRADED
→ smaller sizing
→ PAUSED
```

Require revalidation before a materially changed model becomes live again.

---

# 26. MARKET-DATA HEALTH

Create independent health indicators for:

- WebSocket connection,
- REST API,
- collector heartbeat,
- data freshness,
- order-book sequence integrity,
- latest successful snapshot,
- strategy worker,
- execution worker,
- database,
- disk capacity,
- external data APIs,
- time synchronization.

A profitable-looking strategy using stale data is dangerous.

---

# 27. INITIAL WEATHER VERTICAL

Do not attempt "all prediction markets" first.

Our first end-to-end vertical should be a small family such as:

**daily maximum temperature contracts for one or a few cities.**

Philadelphia is a reasonable test example.

Potential features:

```text
NWS forecast
GFS ensemble
HRRR where available
ECMWF where available
forecast mean
forecast dispersion
forecast changes/revisions
hours until resolution
hour of day
recent observed temperature
dew point
humidity
cloud cover
wind
precipitation
seasonality
historical station/model bias
previous day's errors
Kalshi bid
Kalshi ask
spread
market probability
market price change
trade volume
open interest
order-book imbalance
related temperature strikes
```

Do not use all features automatically.

Research whether each feature would actually have been known at decision time.

For each forecast model, archive the exact run/vintage.

Open-Meteo's historical forecast/previous-runs APIs make point-in-time forecast reconstruction possible for at least portions of the available model history.

---

# 28. FEATURE PROVENANCE

For every model prediction, it should eventually be possible to answer:

> "Why did the model believe this?"

and:

> "Exactly which data values were available to it at 2:31 PM?"

Store a prediction record:

```text
prediction_id
strategy/model version
market
decision_time
feature vector/hash
probability
uncertainty
calibration version
market bid/ask
net edge estimate
source data manifest
```

---

# 29. RESEARCH SOURCES BEYOND WEATHER

Do not build all of these now, but design adapters for:

- official government/economic data,
- point-in-time/vintage economic data,
- news,
- social media,
- sports statistics,
- financial markets,
- polls,
- prediction-market prices,
- related contracts,
- user-provided datasets.

For revised economic series, point-in-time vintage values are essential.

For news/documents capture at least:

- URL/source identifier,
- publication time,
- first observed time,
- ingestion time,
- title,
- parsed text,
- content hash.

Historical research must not use an article that was published after the simulated trade.

---

# 30. STRATEGY LINEAGE

Every strategy should have a complete family tree.

Example:

```text
user prompt
↓
research run #218
↓
hypothesis H-55
↓
StrategySpec S-41 v1
↓
feature dataset D-102
↓
model M-88
↓
backtest BT-902
↓
revision S-41 v2
↓
walk-forward WF-71
↓
holdout H-19
↓
paper deployment P-8
↓
live-small deployment L-4
```

Everything should be clickable/eventually inspectable.

Never overwrite old strategy versions.

---

# 31. EXPERIMENT TRACKING

Use MLflow locally for:

- ML training experiments,
- calibration experiments,
- metrics,
- artifacts,
- feature sets,
- model versions,
- LLM/agent run metadata where useful.

Each MLflow experiment should link back to our own strategy/dataset IDs.

Our application database remains authoritative for trading state.

---

# 32. DASHBOARD

The dashboard is for one user.

No multi-user permission system is needed initially.

Eventually provide pages for:

## Overview
- account value,
- available balance,
- deployed capital,
- open positions,
- current P&L,
- daily/weekly P&L,
- active strategies,
- risk status,
- system health,
- giant global pause button.

## Markets
- markets being monitored,
- bid/ask,
- liquidity,
- rules,
- settlement source,
- related markets.

## Research
- user research prompt,
- active/completed agent runs,
- discovered evidence,
- hypotheses,
- rejected ideas,
- candidate strategies.

## Strategies
For each:
- lifecycle state,
- thesis,
- model,
- features,
- validation,
- backtests,
- live performance,
- current risk allowance,
- lineage,
- pause/retire controls.

## Backtests
- metrics,
- equity curve,
- calibration plots,
- trades,
- drawdown,
- walk-forward results,
- cost sensitivity,
- fill sensitivity,
- benchmark comparison.

## Portfolio/Risk
- exposures,
- correlated clusters,
- remaining risk budget,
- loss limits,
- current risk warnings.

## Orders
- submitted,
- resting,
- partial,
- filled,
- cancelled,
- rejected.

## Data health
- collectors,
- freshness,
- missing data,
- API status,
- sequence integrity.

## System log
- strategy transitions,
- risk decisions,
- agent actions,
- execution events,
- errors.

---

# 33. OBSERVABILITY

Use structured JSON logging.

Every important event should include correlation identifiers such as:

```text
run_id
strategy_id
deployment_id
market_id
intent_id
order_id
agent_run_id
```

Metrics should include:

- API latency,
- WS reconnects,
- sequence gaps,
- collector lag,
- order submit latency,
- order acknowledgements,
- cancel latency,
- fill latency,
- rejects,
- 429s,
- slippage,
- strategy evaluation latency,
- research job duration.

Keep observability local/simple initially.

Do not introduce Kubernetes, Kafka, or a distributed observability cluster.

---

# 34. SECRETS / SECURITY

Production private key must never:

- enter source control,
- appear in logs,
- be sent to an LLM,
- be accessible by agent-generated code,
- be mounted into research containers.

Have distinct:

- demo credentials,
- production credentials.

Prefer filesystem/OS-secret storage with restricted permissions.

Execution service receives the production key.

Research service does not.

`.env.example` contains names only, never real secrets.

---

# 35. TRADING-MODE SAFETY

Support:

```text
READ_ONLY
BACKTEST
PAPER
SHADOW
DEMO
LIVE
```

Default must never be `LIVE`.

Entering live mode should require explicit configuration.

A code checkout should be safe to run without accidentally submitting orders.

---

# 36. FEES

Do not hardcode one universal formula forever.

Kalshi notes that fees can differ by market and some markets can have maker fees. Maintain a versioned fee model and retrieve/apply current relevant fee information where possible.

Each backtest records the fee-model version used.

---

# 37. API LIMITS

Implement centralized rate-limit management.

Current Kalshi API limits use separate read/write token budgets and endpoint costs, so model this explicitly rather than treating all requests equally.

Execution/risk operations take priority over research polling.

A research collector should never starve the ability to cancel an order.

---

# 38. TESTING REQUIREMENTS

Tests are not optional.

## Unit tests

For:

- probability math,
- prices,
- fees,
- payout accounting,
- position accounting,
- order state machine,
- risk rules,
- market relationships,
- feature timing.

## Property-based tests

Especially for invariants:

- balance conservation,
- exposure limits,
- order accounting,
- payout bounds,
- probability bounds,
- complement transformations.

## Point-in-time tests

Construct intentionally dangerous fixtures where future data would improve the strategy.

Assert the engine cannot access it.

## Backtest regression tests

Known fixture → exact known trades/results.

## Exchange adapter tests

Use record/replay and demo API.

## Reconnect tests

Simulate:

- socket drop,
- duplicate event,
- skipped sequence,
- process restart.

## Risk tests

Attempt to submit orders violating every risk rule.

Verify all are rejected.

## Kill-switch tests

Verify no new order can reach gateway after halt.

## Chaos/failure tests

Examples:

- DB temporarily unavailable,
- partial fill then crash,
- submit timeout with unknown server result,
- duplicate client order ID,
- stale book,
- external weather API failure.

---

# 39. DEPLOYMENT MODEL

Keep deployment simple.

Use Docker Compose or normal local processes.

Logical processes:

```text
api/dashboard
market-data collector
research/backtest worker
live execution worker
```

Research/backtests may consume heavy CPU without blocking execution.

The execution worker should remain lightweight and isolated.

No Kubernetes.

No Redis/Celery unless there is a demonstrated need.

Simple subprocess/job management or a lightweight local queue is sufficient initially.

---

# 40. DEVELOPMENT PHASES

**CRITICAL INSTRUCTION: DO NOT BUILD THE WHOLE PROJECT IN ONE PASS.**

At the end of every phase:

1. run all tests,
2. update documentation,
3. commit the working code,
4. provide me:
   - what was built,
   - relevant architecture,
   - files added/changed,
   - tests/results,
   - external code/dependencies reused,
   - known weaknesses,
   - decisions that need reconsideration,
   - exact plan for next phase,
5. STOP.
6. Do not start the next phase until I explicitly tell you to continue.

If something discovered during a phase makes the original architecture worse, tell me instead of blindly following this document.

---

# PHASE 0 — OPEN-SOURCE AUDIT + PROJECT SKELETON

Before implementing trading logic:

1. Inspect all external projects named above.
2. Inspect their licenses.
3. Identify exact modules/functions worth reusing.
4. Decide dependency vs vendor vs reimplementation.
5. Create `docs/external-repositories.md`.
6. Create `THIRD_PARTY_NOTICES.md`.
7. Install/use current Kalshi docs/reference.
8. Set up repo, Python environment, linting, typing, tests.
9. Create high-level architecture docs.
10. Define the internal core interfaces/types.

Do NOT add live trading.

### Deliverable

A working skeleton plus a concrete reuse matrix:

```text
component | project | reuse method | license | reason | modifications
```

### Phase-0 checkpoint

STOP AND REPORT.

---

# PHASE 1 — READ-ONLY KALSHI + MARKET RECORDER

Implement:

- `ExchangeGateway`,
- `KalshiGateway`,
- demo/prod config but READ_ONLY only,
- market/event discovery,
- market details,
- rules retrieval/storage,
- order-book REST snapshots,
- WebSocket connection,
- book delta handling,
- trade feed,
- reconnect logic,
- sequence integrity,
- current API limits,
- local normalized schemas.

Persist:

- market metadata,
- rule versions,
- trades,
- book snapshots/deltas,
- lifecycle events.

Create health monitoring.

No order submission yet.

### Acceptance tests

- Can run for hours in demo/read-only.
- Restarts without corrupting state.
- Reconnects after dropped WS.
- Detects gaps.
- Money uses Decimal/fixed-point.
- Recorded data can be replayed.

### Phase-1 checkpoint

STOP AND REPORT.

---

# PHASE 2 — ACCOUNTING + PAPER BROKER + RISK FOUNDATION

Implement internal:

- account model,
- positions,
- orders,
- fills,
- settlements,
- P&L,
- capital-at-risk,
- execution intents.

Implement PaperBroker.

Adapt strong patterns from existing Kalshi bots where useful.

Build deterministic risk engine including:

- bankroll cap,
- per-trade cap,
- contract/event cap,
- total deployed cap,
- loss limits,
- drawdown limits,
- stale-data guard,
- minimum liquidity,
- maximum spread,
- kill switch.

Build state reconciliation against demo exchange state.

No production trading.

### Acceptance tests

Property tests prove accounting invariants.

Risk tests prove strategies cannot bypass controls.

Crash/restart tests prove reconciliation works.

### Phase-2 checkpoint

STOP AND REPORT.

---

# PHASE 3 — POINT-IN-TIME BACKTESTING ENGINE

Build robust replay engine.

Use/adapt relevant parts of `prediction-market-backtester` and other reviewed repos where appropriate instead of rewriting everything.

Implement:

- immutable datasets,
- available-at semantics,
- temporal replay,
- strategy interface,
- fees,
- spread,
- latency,
- configurable slippage,
- partial-fill modeling where data permits,
- settlement,
- capital accounting,
- trade/equity artifacts,
- deterministic seeds,
- dataset manifests,
- git/config hashes.

Implement train/validation/holdout and walk-forward primitives.

### Required experiment

Write a deliberately leaky strategy and verify that point-in-time protections prevent the leak.

### Phase-3 checkpoint

STOP AND REPORT.

---

# PHASE 4 — FIRST WEATHER DATASET + BASELINE MODELS

Build the first real vertical.

Start with one or a few daily-high temperature market series.

Implement weather adapters.

Construct historical point-in-time forecast datasets.

Implement baseline probability models.

At minimum compare:

1. market-implied probability,
2. climatology/simple historical baseline,
3. raw forecast model,
4. calibrated statistical model,
5. simple ML model if enough data exists.

Evaluate both forecasting and trading.

Do not advance a model merely because its Brier score improved.

### Output

A documented report answering:

- What signals have predictive value?
- What signals add incremental value?
- Is there net edge after costs?
- How stable is it over time?
- How sensitive is profitability to execution assumptions?

### Phase-4 checkpoint

STOP AND REPORT.

If there is no trading edge, that is a successful research result, not a software failure.

---

# PHASE 5 — AGENTIC RESEARCH PIPELINE

Now implement the user's primary interface.

Input:

```text
market/event selection
+
optional strategy idea
+
optional relevant events/signals
+
optional free-form instructions
```

Run:

```text
Research Agent
→ Hypothesis Agent
→ Quant Agent
→ Critic Agent
→ StrategySpec candidates
→ deterministic backtesting
→ Backtest Analyst
```

Each run generates multiple candidate strategies.

Agents can request available datasets/tools.

They cannot access holdout outcomes directly.

They cannot trade.

Store every:

- prompt,
- research report,
- evidence source,
- hypothesis,
- StrategySpec,
- rejected strategy,
- backtest,
- critique.

Use PydanticAI typed outputs.

Start with StrategySpec/DSL rather than arbitrary generated Python.

### Required demonstration

Prompt:

> "Research strategies for Philadelphia high-temperature prediction markets. Explore forecast revisions and identify other potential signals."

The system should produce several concrete testable strategies, automatically backtest them, and rank/summarize them based on factual validation metrics.

### Phase-5 checkpoint

STOP AND REPORT.

---

# PHASE 6 — STRATEGY REGISTRY + EXPERIMENT TRACKING + DASHBOARD

Implement:

- strategy lineage,
- versioning,
- MLflow integration,
- promotion states,
- approval workflow,
- dashboard.

User should be able to inspect:

`idea → research → hypothesis → model → backtest → validation → deployment`

Provide:

- charts,
- calibration,
- P&L,
- drawdown,
- trades,
- evidence,
- assumptions,
- rejection reasons.

### Phase-6 checkpoint

STOP AND REPORT.

---

# PHASE 7 — STRUCTURAL / ARBITRAGE SCANNER

Implement deterministic constraint detection.

Start inside Kalshi.

Examples:

- monotonic threshold violations,
- mutually-exclusive outcome mispricing,
- exhaustive outcome mispricing,
- complement inconsistencies,
- duplicate/related-contract inconsistencies.

Make it event-driven from WebSocket state.

No LLM in fast path.

Include:

- executable prices,
- fees,
- size,
- spread,
- leg risk,
- partial fills,
- minimum guaranteed/expected edge.

Paper/shadow only initially.

### Phase-7 checkpoint

STOP AND REPORT.

---

# PHASE 8 — LIVE PAPER + SHADOW VALIDATION

Run best strategies against actual live market conditions.

Do NOT place real-money production orders.

Collect:

- intended orders,
- real order-book state,
- projected fills,
- likely actual fills,
- slippage,
- strategy signals,
- observed settlement outcomes.

Compare shadow performance with historical backtests.

Identify systematic differences.

### Promotion requirement

A strategy should not move to real capital simply because historical results are good.

Require satisfactory live paper/shadow behavior over a meaningful sample.

### Phase-8 checkpoint

STOP AND REPORT.

---

# PHASE 9 — LIVE-SMALL EXECUTION

Only after explicit user approval.

Implement production order submission.

Start with an intentionally tiny configurable capital envelope.

Requirements:

- live off by default,
- production credentials isolated,
- explicit enable switch,
- deterministic risk engine,
- reconciliation before trading,
- global kill switch,
- max daily loss,
- max drawdown,
- max exposure,
- stale-data halt,
- unknown-order-state halt,
- full journaling.

Start with one approved strategy.

Use conservative size.

Do not immediately enable autonomous live trading for every strategy in registry.

### Phase-9 checkpoint

STOP AND REPORT.

Review actual fills/slippage/risk behavior before increasing capital or strategies.

---

# PHASE 10 — LIVE DECAY DETECTION + AUTOMATIC DOWNSIZING

Add:

- model drift detection,
- calibration monitoring,
- live/backtest divergence,
- realized-vs-expected edge,
- fill-quality degradation,
- feature drift,
- strategy health score based on objective diagnostics.

Allow:

```text
LIVE
→ DEGRADED
→ reduced size
→ PAUSED
```

Do not allow automatic risk-limit increases.

### Phase-10 checkpoint

STOP AND REPORT.

---

# PHASE 11 — OPTIONAL EXPANSION

Only after core system proves reliable.

Possible additions:

## More Kalshi market families

Create new data adapters/features but retain common research/backtest/execution interfaces.

## Cross-exchange arbitrage

Evaluate `pmxt-dev/pmxt` rather than building every prediction-exchange API ourselves.

## FIX

Only if measured execution latency demonstrates a need.

Our chosen Kalshi SDK already has FIX support.

## Deep learning

Only if dataset scale/unstructured data supports it.

Potential applications:

- news embeddings,
- document models,
- social sentiment,
- order-book sequence models,
- multimodal signals.

## Automatic retraining

Only with strict train/validation separation and model-version promotion controls.

## More advanced portfolio optimization

After enough independent strategies exist to justify it.

---

# 41. THINGS NOT TO BUILD YET

Do not spend time initially on:

- user accounts,
- billing,
- SaaS authentication,
- Kubernetes,
- microservices for their own sake,
- Kafka,
- complex distributed queues,
- mobile app,
- generic support for every prediction market,
- high-frequency market making,
- FIX,
- deep learning merely for novelty,
- full social-media firehose,
- cross-exchange execution,
- autonomous capital-limit increases.

This is one user's private research/trading platform.

---

# 42. CRITICAL DESIGN QUESTIONS TO REVISIT AT CHECKPOINTS

At each checkpoint specifically ask:

### Data
Are we really reconstructing what could have been known at the time?

### Backtesting
Are the fills physically plausible?

### Statistics
Could this result just be data mining?

### Prediction
Does the model actually improve calibration?

### Trading
Does that predictive improvement translate into executable edge after costs?

### Risk
What happens if our model is completely wrong?

### Operations
What happens if the process dies immediately after placing an order?

### Security
Could an LLM or generated strategy ever reach production credentials?

### Scalability
Are we adding complexity because it is actually needed or merely because it sounds production-grade?

### Reuse
Are we rebuilding something a vetted open-source component already solves?

---

# 43. DEFINITION OF SUCCESS

The project succeeds if we can reliably perform this entire experiment:

1. User chooses a market family.
2. User gives a vague or specific trading idea.
3. Agents investigate it.
4. Agents generate several falsifiable strategies.
5. Required point-in-time data is collected.
6. Strategies are converted into reproducible specifications.
7. Statistical/ML models are trained where appropriate.
8. Every candidate is realistically backtested.
9. Overfit/leaky/untradeable candidates are rejected.
10. Surviving strategies are presented with evidence rather than hype.
11. User can promote one to paper/shadow trading.
12. Live behavior is measured.
13. User can authorize a tiny live deployment.
14. Risk controls can stop it independently of the strategy.
15. Every trade can be reconstructed and explained afterward.
16. The system automatically recognizes when a once-valid strategy is degrading.
17. The same infrastructure can later support more market families and structural arbitrage.

The goal is not to create an LLM that confidently generates trades.

The goal is to create an **automated scientific process for discovering, falsifying, validating, deploying, and monitoring prediction-market strategies**, with LLMs doing the parts they are good at and deterministic code controlling the parts where mistakes can lose money.

---

# 44. FIRST INSTRUCTION

Begin with **PHASE 0 ONLY**.

Do not implement subsequent phases yet.

Research the listed repositories in detail, inspect their current code and licenses, create the reuse matrix, establish the repository skeleton/interfaces, and report back to me at the Phase-0 checkpoint before proceeding.

Note: You should first make a STATUS.md File which is the status of the project based on every phase we complete/plan. If we don't follow it exactly (e.g. after phase 5, we want to do some fine tuning instead of jumping to phase 6, it can be phase 5.50, 5.51, etc.). Every time you complete a phase you should update that phase as completed, and the move "next steps" to the next phase. This is so if context ever gets lost I can basically just give this file to an agent and it will be fine.
