# Automated research and strategy experiments

R4 connects the existing research, R2 models, replay, risk, ledger and registry. No exchange
orders, arbitrary generated Python, automatic parameter search or holdout evaluation occurs.
Run from the repository root after `uv sync --locked`.

## One-command workflows

Actual recorded Philadelphia/Chicago coverage, with explicitly mocked research:

```bash
uv run entropytrade research-and-test \
  --prompt 'Investigate Philadelphia forecast revisions and Chicago model disagreement' \
  --config configs/research/weather.json --offline \
  --output data/cache/my-real-run --registry data/cache/research.sqlite \
  --tracking data/cache/mlflow
```

This returns two INSUFFICIENT_DATA candidates and one UNSUPPORTED proposal, with actual
coverage and no invented forecasting scores or executions. Six historical events are not
enough; eligible forecast events and scalar-temperature targets are zero. The proposed
final date block is withheld from research and experiments.

A complete, separately labeled **synthetic software demonstration**:

```bash
uv run entropytrade research-and-test \
  --prompt 'Investigate Philadelphia forecast revisions and model disagreement' \
  --offline --synthetic --days 240 \
  --output data/cache/my-synthetic-run --registry data/cache/research.sqlite \
  --tracking data/cache/mlflow
```

The existing R2 generator provides 480 city/day events and four exhaustive contracts/event.
Forecast-derived, predeclared synthetic books never depend on outcomes. Four mock hypotheses
include an unsupported proposal and an impossible-edge negative control. Existing models
fit separate temporal partitions, produce probabilities, drive taker simulations and save
results. No parameters are tuned for positive synthetic returns; synthetic trading results
cannot qualify as PROMISING_FOR_FURTHER_VALIDATION.

For real agents, replace `--offline` with `--provider openai --model YOUR_MODEL
--enable-provider` (or `anthropic`) and configure **ENTROPYTRADE_RESEARCH_API_KEY** in the
research process. Missing keys/opt-in fail explicitly; there is no mock fallback. See
[provider budgets and isolation](agent-research.md). No live provider was verified for R4.

The CLI prints a readable report and IDs/paths. Add `--json` for complete structured output.
Use `--research-run PATH/TO/run.json` with the same data/configuration to replay a completed
research run without another provider call. New research UUIDs intentionally create new
search history; exact experiment replays are idempotent. Keep the registry across sessions.

## Bounded strategy semantics

`domain/strategy.py` is the schema; `strategies/interpret.py` is the compiler. Universes are
an explicit union of ticker/event/series selectors. UTC entry windows and target-date ranges
include the start and exclude the end. Entries expire at window end. Features must be known
by decision time and meet declared versions. Probability observations bind the selected
model family/hash; R4's weather adapter uses the existing R2 full feature schema.

The language supports conjunctions of lt/le/gt/ge/eq predicates; YES/NO; fixed contracts or
fixed dollars including conservatively estimated fees; maximum same-side position including
pending orders; maximum entry cost, spread, displayed touch size; uncertainty/slippage
allowances; hold to settlement; and predicate exits via opposite-side reduce-only orders.
`yes_bid`/`yes_ask` are decision-book builtins. Specify `model_yes_probability` or an explicit
probability feature. NO edge uses `1 - P(YES)` and `1 - YES bid`. Prices are always stored
in YES units; maximum entry price is the cost of the selected side.

Price/time/liquidity conditions gate decisions; limit prices, expiry and independent risk
also gate execution. Position/exposure caps include pending collateral. Immediate orders use
IOC/FOK; a simple exit cannot flip a position. Fractional Kelly, hedging, resting/post-only,
non-informational strategy families and holding-duration exits are explicitly unsupported.
A proposal without a faithful spec remains UNSUPPORTED even when its mechanism is plausible.
No spec can override risk. Optional slippage changes a limit on the four-decimal domain grid;
venue-specific tick validation is still required before any future real execution.

## Execution and fee evidence

Books update before settlements/orders/decisions at a shared timestamp. Orders become
eligible after latency, use the latest already-received sized book, expire on age/close/split,
and cannot fill against a future book. Identical snapshots do not replenish consumed depth
unless a non-null sequence advances; changed snapshots are treated as new capacity. This
is an explicit snapshot simulation assumption, not a reconstructed queue or trade flow.

Optimistic permits observed price improvement; base clamps improvement to the decision
touch; conservative halves displayed size, moves the touch one cent adversely and stresses
fees 1.5×. Conservative orders can receive no fill. Partial/unfilled remainders cancel.
Records include fills, cancelled orders, rejection audit, fee totals, equity and settlements.
Equity is at cost between settlements; drawdown is explicitly labeled `drawdown_at_cost`.
Unresolved positions make final P&L unavailable. Candles/prints never become executable books.

Pass `--experiment-config config.json` for `ExperimentConfig`. Real execution requires an
explicit quadratic fee policy with version, available/effective UTC clocks, evidence hash
and certification. No real historical schedule is supplied by default. Synthetic .07 is
illustrative. Net-edge checks reserve worst-case quadratic price fees and per-depth rounding;
actual ledger fees use each simulated fill's price/quantity. Fee schedules outside their
effective/information range, or unsupported formulas, refuse execution claims.

## Temporal validation, ranking and lineage

Weather uses R2 date-blocked fit/calibration/validation with a protected final holdout and
fixed pre-holdout walk-forward diagnostics. Research never receives outcome values. The
protected boundary is checked before model fitting; predictions are validated against model
fit/calibration cutoffs, event/ticker/time, feature vector and schema hashes, calibration and
model version. The generic model adapter must return this same provenance. Required sources,
actual universes, feature versions and critic/deterministic rejection are checked again.

Report event-weighted Brier/log loss, calibration diagnostics, independent events and contract
counts separately from trading results. Benchmarks use available quoted midpoint or training
climatology; neither implies fills. Date-block bootstrap intervals preserve correlated
contracts/cities within a day. Minimum gates are configurable (at least ten events), not a
power analysis. Ranking is validation Brier, ties share a rank; missing scores stay unranked.
Every candidate/scenario, including unsupported variants, counts toward the existing Registry's
search ledger. Real/synthetic counts are separate. Intervals after searching are descriptive;
there is no multiple-testing correction or automatic final-holdout promotion.

Artifacts: `research/RUN_ID/{run.json,report.md,checksums.json}`;
`models/MODEL_RUN_ID/` with R2 model/prediction artifacts; and
`experiments/EXPERIMENT_ID/{results.json,report.md,trades.parquet,checksums.json}`.
The experiment identity covers research/spec lineage, dataset/features, normalized data,
resolved model results, source/config/fee/scenario and implementation hashes. SQLite stores
immutable completed results/search counts; local MLflow indexes artifacts and metrics.
Checksums protect replay. No arbitrary joblib loading is exposed to agents.

`ExperimentData`/`ContractSample`, `PredictionProvider` and explicit `AdapterRegistry`
registration separate shared logic from weather. Python callers can pass `adapters` and
`market_family` to `research_and_test`; loader paths remain configured, not agent-selected.
The controlled mentions fixture exercises the same engine, workflow and protected research
projection; actual mentions/news ingestion is future work.

See [frozen R4 demonstrations](../data/r4-demo/README.md), [capabilities](capabilities.md)
and [roadmap](roadmap.md). No empirically profitable strategy is claimed.
