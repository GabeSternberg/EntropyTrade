# Capability roadmap

Active from R0 (2026-10-24). This replaces the historical phase sequence and Phase 4.290
continuation, while preserving the [original product specification](project-spec.md).
R0–R2 were approved and integrated into main at `b9cbaa8`. R3 is authorized and active. Stop at each milestone for review unless
explicitly authorized to cross milestones. A commit, city, JSON field or negative
experiment is not a software milestone.

The target is **Discover → Formalize → Collect → Model → Price → Backtest → Validate →
Approve → Paper/Shadow → Risk → Execute → Monitor → Adapt**. A valid rejection is useful.
No profitability target justifies invented data, leakage or implausible fills.

## Shared acceptance rules

Inspect existing implementations and the reuse audit first. Define measurable acceptance,
reuse correct foundations, implement coherent capabilities, test failure/leakage cases,
run `make check`, record actual external evidence separately from mocks, update concise
docs, commit on the phase branch, integrate current main without overwriting unrelated
changes, verify main and push both branches. Never force-push. Stop for review before the
next major phase. Record experiments as runs with lineage and search
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

**R1 checkpoint:** public REST/dataset demonstration verified; collector implementation and
mock/replay integration verified; authenticated sustained WS session blocked without a read key.
See [operating guide](data-platform.md). Sufficient certified weather history is still missing.

**Purpose:** start accumulating reliable live books while building
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

## R2 — Point-in-time weather features and probability models

**R2 checkpoint:** real Open-Meteo GFS seamless + NWS hourly forward capture/restart,
versioned causal features, event-level statistical/ML models, coherent contract probabilities,
separate temporal calibration/evaluation, fixed pre-holdout walk-forward diagnostics and
SQLite/MLflow artifacts are implemented. All five candidates fit in the explicitly synthetic
proof. The real six-event/three-date sample has zero eligible forecasts/scalar targets;
no empirical probability or trading advantage is established. See [operating guide](weather-modeling.md).

Forward capture takes priority over unbounded historical-source searches. Valid time,
initialization, product update, publication and receipt are distinct. Stitched historical
series and lead-offset fields remain assumption-based until availability can be proven.
No historical release clock is invented. Accumulate actual forecast vintages, known market
rules and source-matched resolved highs; NWS CLI cannot replace Weather Company settlement.

Feature families cover complete-day forecast maximum proxies, revisions, model/ensemble
disagreement, past resolved error/bias, observations and known deadline/calendar. Secondary
weather variables wait for clean useful data. Models use mature scikit-learn: empirical
frequency, raw forecast with explicit spread assumption, learned error distribution,
regularized regression, justified boosting and monotone logistic/isotonic CDF calibration.
Fit one frozen observation per city/day; translate its temperature distribution to related
contracts rather than fitting correlated contracts as independent weather outcomes.

Acceptance is reproducible, leakage-tested fitting/evaluation/prediction/artifact plumbing,
real provider capture and either defensible real evaluation or an explicit end-to-end
insufficiency diagnostic. Gate independent event counts and date partitions; final holdout
stays protected by default. Better probability scores do not qualify a strategy. No deep
learning, agents, strategy tuning, production orders or dashboard work in R2.

## R3 — Provider-backed research

R3 is complete for review on `recovery/r3`, based on `b9cbaa8`. It is **not merged into
main**; the latest user instruction requires separate merge approval for this phase.

Delivered: explicit OpenAI/Anthropic configuration with dedicated research credentials and
live opt-in, bounded read-only evidence tools, typed multi-hypothesis Research → Hypothesis
→ Quant → Critic orchestration, full-spec criticism, independent candidate gates, factual
analyst reports and immutable SQLite audit/search lineage. The original fixture backtest
remains a regression demonstration and is never run by operational research.

Actual recorded Philadelphia/Chicago coverage is inspectable. Mock research and an actual
OpenAI SDK/PydanticAI HTTP-mock protocol run are verified; **external provider execution is
blocked without a research API key**. Mock reasoning is never an empirical autonomous
research claim. See [operating guide](agent-research.md) for exact live/offline commands.
The six-event real dataset still lacks eligible forecasts/scalar labels; no edge is proved.

Holdout protection is enforced through filtered/allowlisted projections, not merely prompts.
No arbitrary paths, SQL, shell, network fetching, joblib loading or execution tools exist.
Token/request/time/cost budgets stop failures without a fixture fallback. Run one live
research worker per isolated process because the framework permission switch is global.

R4 acceptance must attach deterministic experiments to these hypotheses/spec hashes while
preserving the final holdout boundary. Count every search, including related threshold
variants. Complete/validate interpreter semantics before interpreting backtest returns;
repair chronology, liquidity reuse, fees and event exposure. Do not start R4 until review.

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
