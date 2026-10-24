# Capability roadmap

Active from R0 (2026-10-24). This replaces the historical phase sequence and Phase 4.290
continuation, while preserving the [original product specification](project-spec.md).
Only R0 is authorized in the current handoff. Stop at each milestone for review unless
explicitly authorized to cross milestones. A commit, city, JSON field or negative
experiment is not a software milestone.

The target is **Discover → Formalize → Collect → Model → Price → Backtest → Validate →
Approve → Paper/Shadow → Risk → Execute → Monitor → Adapt**. A valid rejection is useful.
No profitability target justifies invented data, leakage or implausible fills.

## Shared acceptance rules

Inspect existing implementations and the reuse audit first. Define measurable acceptance,
reuse correct foundations, implement coherent capabilities, test failure/leakage cases,
run `make check`, record actual external evidence separately from mocks, update concise
docs, commit and stop for review. Record experiments as runs with lineage and search
counts. Keep raw data/provenance immutable. Prefer mature packages behind our interfaces.
No SaaS, distributed-system expansion, arbitrary agent Python or new trading permissions.
Production submission stays disabled until separate explicit approval after R8.

## R0 — Audit, consolidate and simplify

Deliver current-truth subsystem inventory, short entry docs, durable grouped findings,
legacy index and safe fragmentation cleanup. Preserve data/history, test important
invariants and reproduce checks (or document pre-existing failures). Commit and stop.
Acceptance: a newcomer can use the README and five linked short docs to understand the
system; implemented/tested/external/operational states are explicit. No new feature engine.

## R1 — Generic market/data platform and continuous recording

**First priority after R0 approval:** start accumulating reliable live books while building
reusable research datasets. Retain the existing SDK boundary and local storage approach.

- Repair session identities and dedup semantics; retain unsequenced trade/lifecycle
  events and repeated raw-receipt provenance. Preserve old databases with explicit migration.
- Make freshness per market, fail stale after gaps/reconnects, require resnapshot recovery.
  Verify sequence/reset handling against current SDK/API behavior.
- Implement a runnable read-only collector with explicit environment/read-key setup,
  snapshots/deltas/trades/lifecycle subscriptions, reconnect/backoff, graceful stop,
  restart-safe persistence, and persisted health/freshness/gap reporting.
- Paginate actual listed event/contract discovery, dynamically select strikes/buckets,
  version rules and settlement semantics, and track API historical/live cutoffs and budgets.
- Build generic city/date configuration and source adapters, immutable raw receipts,
  normalized data and reproducible manifests with input hashes, code version and coverage.
  Unknown publication/availability stays unknown and is excluded from certified features.
- Label execution evidence as real L2, quote, print, candle or missing. Never convert
  candle volume into displayed size. Bind outcome labels to the actual settlement source.

Deliver **one dataset command** producing `(market, decision_time, point-in-time features,
observed market state, outcome, provenance)` and **one collector command**. Test multiple
cities/strikes using configuration, multi-page discovery, reconnect/gaps, reused sequences
across sessions, unsequenced events, duplicates, crash/restart, stale books and missing clocks.
Validate the dataset on committed/real source data. Demonstrate a sustained authenticated
read-only session (target hours), replay and restart if a read key is available. Otherwise
finish implementation and setup instructions and mark that integration explicitly blocked.
No LLM/model work or live order transport in R1. Replay-risk repair is required before R4
can claim realistic evaluation; do not run R1 data through legacy pseudo-book studies.

## R2 — Features and fitted probability models

Implement a versioned feature registry/pipeline for forecast values/revisions, HRRR/GFS/
ECMWF and ensemble disagreement, error/bias, humidity/dew point/cloud/wind, observations,
time-to-close, market spread/depth and related contracts where real timing/coverage permits.
Use temporal fitting and mature libraries (start with scikit-learn): climatology, market,
raw forecast, regularized logistic models, justified boosting and learned calibration.
Store model/calibrator versions, train ranges, dataset manifests and predictions.
Acceptance: reproducible real-contract probability comparisons with Brier/log loss and
baselines, calibration diagnostics and explicit missing-data exclusions. No deep learning
by default. Better prediction alone does not qualify a strategy.

## R3 — Provider-backed research

Replace production TestModel-only wiring with explicit isolated provider configuration;
retain TestModel for tests. A real prompt and evidence must drive Research → Hypothesis →
Quant → Critic → distinct typed StrategySpec candidates. Supply read-only market/rule,
dataset/feature, external-evidence and past-experiment tools and deterministic experiment
requests. Pass full candidate semantics to the critic. Agents cannot see protected holdout
outcomes, order tools or trading credentials. Acceptance: a configured actual provider
runs the prompt and yields auditable distinct hypotheses; without an LLM key, deliver a
configurable adapter, mocked tests and an explicit external-verification blocker.

## R4 — Strategy execution and automated experiments

Support explicit market selection, feature/model probability predicates, costed net edge,
entry windows, YES/NO, size limits, simple exits and settlement. Reject every unsupported
field/semantic explicitly. Repair replay chronology, split bounds, stale fill horizons,
shared liquidity capacity, event exposure and fees before calling results realistic.
Connect candidates to deterministic runs with complete lineage and MLflow/application
registry links. Count every candidate/search, preserve temporal train/validation/protected
holdout and walk-forward discipline, independent-event minima, useful bootstrap intervals,
selection/multiple-testing warnings, baselines and fee/slippage/fill scenarios.
Acceptance: multiple specs can be evaluated and weak/unsupported ones rejected with
reproducible evidence, trades/equity/artifact coherence and no fabricated metrics.

## R5 — End-to-end research V0

One command/API must handle: “Research Philadelphia daily-high markets; investigate
forecast revisions and model disagreement, and propose other plausible signals.” It must
inspect data/missingness, generate falsifiable hypotheses/specs, train/select justified
models, run deterministic experiments, reject unsupported/overfit candidates, summarize
validation and preserve full lineage. Acceptance: a useful real-data research report;
no passing strategy is an acceptable result. Stop for V0 review.

## R6 — Continuous paper/shadow and structural scanning

Use the read-only live feed for eligible strategies and verified related-contract scans.
Record each decision's time, strategy/model/data versions, available information, prediction,
bid/ask/depth, estimated edge, intent, risk decision, execution evidence, subsequent prices
and settlement. Compare expected execution with observed conditions. Scan structural
relationships using executable prices, fees, size and non-atomic leg/partial-fill risk.
Acceptance: continuous paper/shadow/scanner processes and reviewable records with no
exchange order submission. Prints still do not establish actual fills.

## R7 — Private research/control dashboard

Use FastAPI and minimal React/Vite once workflows exist. Expose prompts/results,
agent/experiment history, candidates, model/backtest/calibration metrics, P&L/drawdown,
paper/shadow signals, books/relationships, risk/exposure, collector health, lineage and
global pause. Acceptance: one private interface operates research through shadow.
No accounts/billing or unnecessary infrastructure.

## R8 — Live readiness review

Produce a go/no-go report on out-of-sample evidence, execution limitations, sustained
shadow results, feed health, account reconciliation, unknown-order handling, verified fees,
risk enforcement, credential isolation, kill switches, restart/crash recovery and
live-vs-backtest monitoring. Acceptance is a reviewable readiness report, **not activation**.
Keep production disabled. A later separately approved live-small milestone may activate
one strategy under tiny limits, followed by degradation monitoring. Never automatically
increase permitted capital.
