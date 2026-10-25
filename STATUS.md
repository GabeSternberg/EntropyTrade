# EntropyTrade — current status

Updated 2026-10-25. R0 remains `c7ad278`; R1 remains `e2c1448`.
R2 is on `recovery/r2`, branched from R1. Previous branches are preserved.

## Objective and checkpoint

**R2 — point-in-time weather features and statistical probability modeling — is complete
for review.** Real forecast capture works; empirical model evaluation is blocked by data.
The goal remains reproducible research through paper/shadow, with honest rejection of
unsupported claims. [Roadmap](docs/roadmap.md) is the active plan. Stop before R3 approval.

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

## Evidence and checks

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
StrategySpec interpreter remain R4 work. Real LLM agents, automated strategy experiments,
continuous shadow and the dashboard are not operational. Production submission stays
blocked; no order transport or trading credentials were added. Legacy research/data and
previous branches remain intact.

## Exact next action

Review R2 and [weather/model operating guide](docs/weather-modeling.md). Keep forward weather
and read-only market capture running; obtain actual source-matched resolved scalar highs
with defensible clocks and expand independent event history before empirical fitting.

Recommended **R3**: configurable provider-backed PydanticAI Research → Hypothesis → Quant →
Critic → typed candidates, using bounded read-only tools for markets/rules, coverage,
feature definitions, pre-holdout model diagnostics and prior runs. Agents receive honest
insufficient-data responses; they cannot read protected holdout targets, deserialize
arbitrary models, submit orders or access trading credentials. Deterministic modeling
requests stay inside existing eligibility/temporal gates. No general strategy search
engine until R4. Do not start R3 without approval.
