# Capability roadmap

Active from R0 (2026-10-24). This replaces the historical phase sequence and Phase 4.290
continuation, while preserving the [original product specification](project-spec.md).
R0–R3 are approved; R3 was integrated before R4. R4 is complete for review and its tested
branch/main merge and push are authorized. Stop before the next milestone.
The current continuation is limited to acceptance of the implementation already committed
at reviewed commit `18be50cee17f03ae3dbfa198ed22e7a23635af1b`. All Git mutations belong to the supervisor.
A clean source export exposed a native SQLite job-connection close stall; a bounded
concurrency regression and serialized-connection acceptance fix are now committed there.
The historical candidate passed full checks (734 pytest tests, strict mypy, Ruff, and
nine frontend cases); these receipts describe an overlay on `99e2fbc`. The supervisor's final
independent clean-checkout sign-off remains required. All four documented browser procedures
now pass using Playwright's separate Chromium and the actual localhost backend. The new
receipt preserves successful public ingestion separately from deliberate OS network denial,
checksummed browser downloads, screenshots, cancellation and restart history. No empirical
model performance is inferred from forward capture.
See [status](../STATUS.md), [current evidence](../data/workbench-review/20261026T203717Z/README.md)
and [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) for evidence-backed V1 gates. The user's
current V1 sequence takes precedence over the older R5–R8 numbering below. V1 is incomplete.
The R4 approval request revises the next priorities: minimal localhost website, second real
market family, then continuous paper/shadow. A commit, city, JSON field or negative
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
The current continuation overrides the general integration workflow: implement/test on the
existing branch, return for review and leave all Git mutations to the supervisor.
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

R3 is approved and integrated at `624d442`. Previous recovery branches remain intact.

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
repair chronology, liquidity reuse, fees and event exposure. These requirements are implemented in R4 below.

## R4 — Strategy execution and automated experiments

**Checkpoint:** complete integrated CLI, bounded faithful StrategySpecs, R2 prediction
selection, chronological/capacity/risk/fee-aware replay, forecast/trading diagnostics,
ranking/rejection, date-block uncertainty, search accounting and SQLite/MLflow/Parquet lineage.
The generic adapter boundary is tested on non-weather mentions. Actual historical weather
candidates return insufficient data; full modeling/execution is proved separately on
synthetic inputs/mock agents. Final holdout stays untouched. See [guide](experiments.md).
No empirical edge or trading readiness follows from this milestone.

## R5 — Minimal local research website

**Implementation committed; documented browser acceptance passed on `18be50c`, pending supervisor sign-off.**
The historical candidate passed 734 pytest tests, strict mypy, Ruff and nine
frontend presentation cases. The frozen `99e2fbc` baseline failure and then-uncommitted
candidate remain recorded separately; the supervisor must complete final clean-checkout
locked setup and full checks of the reviewed commit.
Acquisition completeness/counts/failures are prominent on every result tab and text report;
nine frontend presentation regressions pass. A buildless local interface and standard-library
HTTP control plane reuse the existing engines without new web dependencies. Browser
acceptance passed all four procedures through isolated Playwright Chromium, including
actual public captures, visible failure summaries, downloads, active cancellation and
restart persistence. Current-source full checks passed all 734 pytest and nine frontend
tests, Ruff and strict mypy. Git writes belong to the supervisor; V1 remains incomplete.
See the [operating guide](workbench.md).

Original scope: FastAPI plus a minimal React/Vite local interface over existing
research/experiment services: type an idea, explicitly choose provider/data/mock mode,
start a bounded worker, inspect progress/history, hypotheses/specs, probabilities,
forecast/backtest metrics, fidelity and rejection reasons. Preserve protected evidence,
credential isolation, reports and lineage. No SaaS, trading activation or broad dashboard.
Acceptance: open localhost → research idea → saved, reviewable candidates/results. Real
insufficient-data reports and explicit synthetic demonstrations must both be usable.

## R6 — Second real market family

**Bitcoin adapter and successful forward ingestion verified; empirical evaluation absent.**
KXBTC public rules and Coinbase spot are a distinct registered forward-evidence family.
Bitcoin's `rules_known` remains false and settlement sources/basis stay unresolved because
complete resolution semantics are unverified. Exact authority mentions, including negated
or ambiguous text, are retained separately as unverified provenance.
The latest browser run retained 3 successful receipts, 210 listed contracts and one
Coinbase spot observation. A separate OS-denied browser run retained two explicit failures
and zero data. Neither is a historical probability/returns evaluation.
Official source-matched outcomes, independent historical training/evaluation and sized
execution evidence are absent. This does not satisfy an empirical R6 completion claim.

Implement one useful non-weather family through the existing registered adapter/sample/
feature/prediction interfaces. Inspect actual listed contracts, settlement definitions,
point-in-time sources, outcome and execution coverage. Demonstrate the same research and
experiment workflow without rebuilding shared engines. A negative result is acceptable;
real ingestion/coverage evidence must be distinguished from R4's controlled mentions fixture.
Choose the family after reviewing source feasibility; do not build all families at once.

## R7 — Continuous paper/shadow and structural scanning

Connect eligible strategies to the read-only live feed. Persist each decision's versions,
available information, probability, executable bid/ask/depth, edge, intended order, risk,
simulated/observed evidence, later prices and settlement. Compare expected vs observed
conditions; verified structural groups use fees/size/non-atomic leg risk. Add basic collector,
exposure, pause and audit views to the local website only where operationally useful.
Acceptance: recoverable continuous paper/shadow/scanner processes with no exchange orders.
Prints never establish fills. Broader dashboards follow actual operational needs.

## R8 — Live readiness review

Produce a go/no-go report on out-of-sample evidence, execution limitations, sustained
shadow results, feed health, account reconciliation, unknown-order handling, verified fees,
risk enforcement, credential isolation, kill switches, restart/crash recovery and
live-vs-backtest monitoring. Acceptance is a reviewable readiness report, **not activation**.
Keep production disabled. A later separately approved live-small milestone may activate
one strategy under tiny limits, followed by degradation monitoring. Never automatically
increase permitted capital.
