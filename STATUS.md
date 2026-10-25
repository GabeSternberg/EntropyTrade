# EntropyTrade — current status

Updated 2026-10-25. R0 remains `c7ad278`; R1 remains `e2c1448`.
R2 is on `recovery/r2`, branched from R1. Previous branches are preserved.

## Objective and checkpoint

**R3 — operational agentic research — is complete for review on `recovery/r3`.**
R0–R2 remain on main at `b9cbaa8`. R3 must be pushed separately and not merged without
approval. No R4 work or production trading is authorized. Real LLM provider execution
remains externally blocked because no dedicated research key is configured.

## What now works

- R1's read-only Kalshi collector, session-safe SQLite recording, integrity/freshness
  reporting, generic contract discovery and versioned Parquet datasets are preserved.
- `weather-collect` polls Open-Meteo GFS seamless and NWS hourly across configured locations.
  Raw receipts, normalized vintages, first-seen availability and distinct provider clocks
  survive restart. Poll/retry/disk limits, shutdown, writer lock and failure evidence work.
  `weather-export` produces raw evidence plus R1-compatible observations and coverage.
- `features` creates versioned point-in-time matrices: complete local-day forecast maximum
  proxies, revisions, model disagreement, causal station bias, calendar and known deadlines.
  Canonical ensemble members/recent observations are supported when supplied. Missing values
  stay missing; future revisions/labels and uncertain clocks are excluded.
- `model` fits event-level climatology/frequency, raw forecast with assumed spread,
  learned forecast-error distribution, regularized Ridge and histogram boosting candidates.
  Monotone logistic/isotonic CDF calibration preserves related-contract coherence. Strict
  thresholds and inclusive buckets receive probabilistic YES estimates.
- Date-blocked fit/calibration/validation/protected holdout, known-label cutoffs, fixed
  pre-holdout walk-forward checks, event-weighted Brier/log loss/reliability, sample counts
  and explicit insufficiency diagnostics are implemented. Default real runs leave holdout
  untouched. Predictions/artifacts have input/schema/code/runtime hashes, SQLite lineage,
  checksums and local MLflow tracking. No prices imply fills or trading P&L.

- `research` now runs typed PydanticAI Research → Hypothesis → Quant → Critic with full
  evidence/spec semantics, then independent validation and a deterministic analyst report.
  Explicit OpenAI/Anthropic configuration, request opt-in, dedicated credentials, finite
  budgets and fail-closed restoration preserve the existing mock demonstration.
- Read-only tools project actual markets/rules/relationships, coverage, feature definitions,
  approved pre-holdout model diagnostics and prior research. Protected rows/outcomes,
  holdout scores, arbitrary files/SQL/network, model loading and trading tools are absent.
- Completed and failed agent runs, prompts, tool output hashes, hypotheses, candidate/spec
  hashes, critiques, gate decisions and provider identity/usage remain immutable in the
  existing SQLite Registry and checksummed JSON/Markdown. Idempotent replay recovers files;
  normalized search signatures track prior attempts without promoting lifecycle states.

## Evidence and checks

- R3 release checks: **595 tests passed in 197.48s**, Ruff lint/format clean,
  strict mypy clean (455 files). All 561 R2 tests remain; 34 R3 cases cover provider
  opt-in/failure, bounded/protected evidence, invalid proposals, audit replay and prompt variation.
- Two **mock** research runs over actual R1/R2 data cover Philadelphia revisions and Chicago
  model disagreement. Each returns three hypotheses, two typed candidates with
  INSUFFICIENT_DATA and one UNSUPPORTED proposal. No backtest or model fitting ran.
  Frozen full audit/report artifacts: `data/r3-demo/`.
- The actual OpenAI SDK/PydanticAI protocol is verified through HTTP mocks: evidence tool
  consumption, full critic input, structured outputs and provider failure with no fallback.
  This is not real LLM research; neither provider has a credential-backed verified session.
- R1 baseline rerun: **528 tests passed**, Ruff clean, strict mypy clean.
- R2 final `make check`: **561 tests passed in 203.52s**, Ruff lint/format clean,
  strict mypy clean (449 files). All 528 R1 tests remain; 33 new cases include
  property checks, crash/restart, late revisions/labels, source ambiguity, calibration
  separation and repeated artifact/registry builds.
- **Real forward:** three polls across a clean stop/restart on October 24, 23:55–23:57 UTC:
  **18 HTTP receipts, four distinct provider/location vintages, 648 hourly points, zero
  failures**. Valid horizons extend through October 30 (Open-Meteo) / 31 (NWS). Each source
  has one distinct product per city; actual changing revisions have not yet accumulated.
  Frozen raw archive and coverage: `data/r2-demo/`.
- **Real historical diagnostic:** R1's 36 contracts/six Philadelphia+Chicago events across
  September 1–3 (three date blocks) still have **zero eligible strict forecast events,
  zero source-matched scalar-temperature labels, zero fitted models or model metrics**.
  October forecasts do not backfill September. The 1,060 candles are context, not books.
- **Synthetic proof:** 300 date blocks/600 city-day events, all five candidates fitted,
  separate calibration, validation/explicit fixture holdout and two walk-forward windows.
  Repeated fits/builds reproduce artifacts and prediction identities. Metrics are labeled
  synthetic and are not empirical Kalshi performance. See the frozen evaluation summary.

## Limits and external dependencies

No key is needed for these public forecast requests. Open-Meteo response issue/publication
is unknown; NWS product update is not model initialization. First retained receipt is the
strict availability clock. Historical stitched/lead-offset APIs remain assumption-based.
A matching Weather Company scalar settlement integration/history is still missing; NWS CLI
is not a replacement. Sufficient independent aligned events, historic rules and executable
books remain unavailable. These are substantive modeling/validation blockers.

Authenticated sustained Kalshi WS verification still needs a dedicated read-only key;
R1 mock/replay evidence is unchanged. Replay chronology/capacity/fees and the narrow
StrategySpec interpreter remain R4 work. Provider-backed research is configurable but externally unverified. Automated strategy
experiments, continuous shadow and the dashboard are not operational. Production submission stays
blocked; no order transport or trading credentials were added. Legacy research/data and
previous branches remain intact.

## Exact next action

Review R3 and [agent operating guide](docs/agent-research.md). For real provider verification,
configure `ENTROPYTRADE_RESEARCH_API_KEY` and use an explicit provider/model plus
`--enable-provider`; otherwise use the clearly labeled offline command. Continue forward
weather/market collection and obtain the actual settlement authority's scalar highs.

Recommended R4: faithful StrategySpec universe/time/model/feature predicates, YES/NO,
sizing and exits; actual fee/net-edge semantics; replay chronology, split/freshness bounds,
shared liquidity and event exposure; deterministic candidate experiments with event/date
splits, calibration/baselines, selection/search accounting and protected final evaluation.
Use existing registry/spec/data hashes and MLflow. Do not start R4 or merge R3 until approval.
