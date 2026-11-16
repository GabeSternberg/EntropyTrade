# Acquired-feature modeling and persistent experiments

Milestone C connects durable acquired-feature jobs to modeling, contract probabilities,
deterministic replay and independent validation reports. Controlled software acceptance
and authentic empirical validation remain separate. No profitable strategy, paper eligibility
or Windows deployment is established.

## What runs

`ResearchService` advances its existing SQLite job through feature registration into
`modeling`. Each nonduplicate hypothesis gets an input identity and a durable experiment
row before work begins. Each worker step handles one hypothesis; current results,
refusals, failed attempts and new feature versions remain inspectable. Resume/restart uses
the existing job retry/cancellation/runtime budgets, rather than another job state machine.
Cancelled jobs cannot start or publish late experiments.

The acquired-data adapter currently supports registered Fahrenheit scalar weather features
and the separate settlement-high label. It verifies immutable feature definitions, units,
values, source datasets, raw responses and their hashes. One predeclared decision per
station/day prevents several contracts or forecast revisions from inflating evidence counts.
Missingness and independent event/date counts remain visible.

The adapter reuses `WeatherModel`, temporal partitioning, calibration and probability-score
primitives. It evaluates a temperature threshold determined exclusively by the training
sample: these probabilities are **not exchange contract probabilities**. Available models
include climatology/raw-forecast baselines, regularized ridge, forecast-error distributions
and the existing bounded tree model when its larger evidence minimum is met. Model requests
that require unavailable inputs are refused explicitly.

There are four chronological partitions: fitting, calibration, validation and protected
holdout. Label receipt times must precede the simulated fitting/calibration cutoff;
retrieval today does not make labels available in the past. A two-day embargo applies.
Protected label values do not enter fitting, scoring or coverage decisions. Once a valid
fit is possible, boundaries are persisted **before fitting** and shared across the same
market family, including later jobs, changed features/universes and growing datasets.
Insufficient data cannot prematurely freeze an unusable window.

Brier score, log loss, reliability bins, date-block uncertainty and walk-forward diagnostics
use the permitted validation history. Each walk-forward fold has its own training threshold
and excludes the primary holdout. Search counts and requested models remain visible; no
selection-adjusted significance or prospective success is asserted. The protected holdout
is retained for subsequent independently authorized evaluation.

## Persistence and website

Within the configured workspace:

- `research/research.sqlite`: existing jobs plus experiment checkpoints and protected dates.
- `research/experiments/sha256-*`: fitted model files, frozen predictions, reports and checksums.
- Existing `research/raw`, `datasets`, and `features`: unchanged immutable source conventions.

The **Autonomous Research → Modeling & validation** tab shows real eligibility reasons,
configuration, training/calibration counts, baseline comparisons, model scores, temporal
partitions, execution refusals and full experiment history. **Export report** includes
those results and frozen input identities. Ordinary workspace snapshot/restore includes
research metadata and model files. Artifacts are retained locally; no cloud database or
new external service is required.

## Execution evidence and deterministic replay

`research.backtesting` compiles supported registered features/rules into the existing typed
`StrategySpec` and calls the existing deterministic experiment engine. Controlled synthetic
inputs exercise sized books, fees, risk and simulated YES/NO fills. Real data requires
immutable applicable fee evidence; missing prices, books, decision-time rules, probabilities,
unsupported/unfitted rules and version mismatches refuse.

The worker freezes completed acquisition dataset IDs and exact fee versions into the
experiment identity. Existing typed `MarketEvidence` and `MarketState` records become
contract samples; fitted distributions predict actual acquired strikes. Only decision-time
contract rules, reviewed station/authority/unit semantics and genuine sized books are usable.
Reduced contract metadata retrieved after settlement cannot supply historical rule evidence.

`research.local_evidence` consumes the existing verified `runs/weather-datasets` snapshots
inside the configured workspace. It reparses original market bytes, preserves raw responses
and their original receipt clocks, retains book fidelity and inherits protected partitions.
No network request, arbitrary input path or canonical-chain write is available. Verified
copied research datasets can be reused without their source snapshots. Malformed sources,
corrupt copies, unresolved source-protection conflicts and import-budget limits refuse.
The source directories stay byte-identical. This is a validated evidence-consumption
interface for separately restored research copies, not collector synchronization.

Decision-eligible contracts are selected using information available at the decision,
including their scheduled close. Eventual label or official-publication timing cannot select
trades. Missing outcomes refuse the full executable report; late publication remains an
unsettled position at the frozen evaluation cutoff, with no fabricated P&L. Actual protected
contract identities preserve the engine cutoff without exposing their outcomes.

Other open gates:

- Authentic decision-time books/rules from a verified read-only collector snapshot.
- Applicable human-certified fee versions (see [fee evidence](fee-evidence.md)).
- Enough independent timely labels for fitting/calibration and validation. A 60-day
  window cannot satisfy a 60-event fitting minimum after chronological partitioning. New
  requests default to 240 days (bounded at 365); HTTP/byte/runtime budgets remain unchanged.
  Inspect actual timely counts rather than treating a long window as proof of sufficiency.
- Authenticated provider inference. No credentials are available in this cloud workspace;
  subscription access is not an API key. Explicit provider selection never uses templates
  after a failure. Dedicated variable names are in [credentials](autonomous-research.md#credentials).
- Genuine prospective observations; historical scores remain retrospective.
- Research-to-paper promotion, exact compatible forward feature/model bindings, milestones
  D/E/F and private Windows deployment readiness. Existing legacy paper components are
  preserved; this research workflow does not yet promote models into them.

Collector configuration coverage means **planned**. It does not prove deployment or recent
collection. Only verified data satisfying a job's own requirements can establish sufficiency;
sanitized Windows status summaries cannot. This work never writes to the collector's
canonical chain or assumes access to the user's Windows machine.

## Verification

Run the repository quality checks with its locked environment:

```sh
UV_CACHE_DIR=/tmp/entropytrade-uv uv sync --locked
uv run ruff check backend
uv run ruff format --check backend
uv run mypy
uv run pytest
node --test frontend/tests/*.test.cjs
```

Focused tests are `test_research_modeling.py`, `test_research_modeling_jobs.py`,
`test_research_backtesting.py` and `test_research_forward_status.py`, alongside existing
research/acquisition/provider and disabled-execution suites. Real browser procedures in
`frontend/browser/research.spec.cjs` distinguish offline inventory, replayed authentic
Philadelphia source bytes and explicit synthetic fitting. Test fixtures cannot be selected
through production request schemas.


## Acceptance evidence

The controlled persistent-job acceptance runs acquired features → eligible fit/calibration →
actual contract probabilities → the existing replay/risk/fee engine → durable validation
report. It produces 43 optimistic/base simulated fills and zero conservative fills with the
declared single-snapshot evidence. These are synthetic accounting results, not observed
returns. A separate authentic-byte Philadelphia replay acquires/registers real source data,
reaches modeling and correctly refuses seven dates with insufficient timely training data.
Retained authentic weather snapshots exercise production local ingestion without mutation.

The test suite covers missing prices/books, uncertified fees, insufficient events, unsupported
features/types, future clocks, single-class targets, restart/retry, fitting failure, budgets,
artifact/version corruption, shared heldout protection and prospective-label separation.
Additional tests cover delayed/missing settlement, ambiguous rule revisions, binary payouts,
source snapshot protection/cache migration and local-provider isolation. Four actual browser
procedures cover ordinary research, authentic acquisition replay, synthetic fitting and
synthetic executable replay, including exported accounting, mobile layout and restart.

The implementation uses the existing SQLite/file stores, source adapters, feature registry,
weather models, replay engine, risk controls and backup/restore path. No new managed database,
execution transport or collector process was introduced. Updating running server code requires
stopping and restarting it so loaded code and recorded source versions remain aligned.

Research stores and direct model publication also reject collector-chain roots and symlink
aliases before creating directories or SQLite. The existing unused collector research
service remains lazy; local-chain regression tests verify that path remains compatible.
