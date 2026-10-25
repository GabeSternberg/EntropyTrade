# Weather collection and probability modeling (R2)

The commands are local and read-only. They never load Kalshi trading credentials or place
orders. `uv sync --locked` installs the existing locked packages. Start from the repository
root; use `UV_CACHE_DIR=/tmp/entropytrade-uv` if the home cache is read-only.

## Capture forecast vintages

```bash
uv run entropytrade weather-collect --config configs/data/weather-forward.json \
  --db data/cache/weather.sqlite
# Ctrl-C shuts down cleanly. Run the same command to resume.
# Add --once for one poll or --seconds 1800 for a bounded session.
uv run entropytrade weather-export --db data/cache/weather.sqlite \
  --output data/cache/weather-export
```

Configuration covers locations/coordinates/stations, providers, interval, bounded attempts
and disk budget. Default: Philadelphia/Chicago, Open-Meteo GFS seamless + NWS hourly,
15-minute polling, three attempts, 5 GB. Use one writer per archive; the CLI enforces a
process lock. SQLite uses the R1 raw receipt/body journal and WAL/FULL transactions.
The disk budget stops collection without deleting evidence. Archive closed databases
manually before the budget is reached. No daemon manager is required; keep the process
running in a terminal/tmux or supervise this same command on a private server.

Every response retains its URL/status/body/hash and actual receipt. Parse/HTTP failures
remain evidence; transport errors and invalid NWS discovery responses enter health records.
Successful captures report provider/location. The final JSON summary reports receipts,
failures, distinct vintages, first-seen/last successful receipt and forecast valid ranges.
These are observational health facts, not a guarantee that no upstream run was missed.
Check the last successful receipt against the polling interval to detect stale collection.
A crash after the raw commit can leave an unnormalized raw receipt; it remains in the R1
journal. The next successful response is certified only from its own retained receipt.

Repeated sightings do not move availability backwards or create new normalized facts.
A distinct provider product/revision or changed forecast content creates a new vintage;
a changed generation-runtime field alone does not claim a new model run. NWS product
update and generation clocks are separate from initialization. Neither adapter invents
initialization; Open-Meteo provides no publication clock in this response. All strict
availability is conservatively **first retained receipt**, even if a product clock is older.
A response's past valid hours cannot be retroactively used before that receipt.

`weather-export` writes raw bodies, R1-compatible `observations.jsonl` with relative raw
paths/file hashes, and coverage. The SQLite archive preserves all sightings, including
identical and failed responses; the export contains the first raw evidence for each vintage.
Frozen real evidence is committed at `data/r2-demo/weather.sqlite`; use `data/cache/` for
continued collection so the demonstration stays reproducible.

## Features and the real-data diagnostic

```bash
uv run entropytrade features \
  --dataset data/r1-demo/7be1ac67055e7abdc15bf90cdf093d257bde67f484440297add4428075c15b14 \
  --archive data/r2-demo/weather.sqlite --output data/cache/r2-features
# Substitute the feature_version suffix printed above as FEATURE_HASH below.
uv run entropytrade model --features data/cache/r2-features/FEATURE_HASH \
  --output data/cache/r2-models --registry data/cache/research.sqlite \
  --tracking data/cache/mlflow
```

Multiple `--archive` arguments are supported. R1 canonical observations are also read
from the source dataset. The frozen real outputs in `data/r2-demo/features/` and `models/`
show **six city/day events, three date blocks, 36 contracts, zero eligible forecast events,
zero source-matched scalar-temperature labels, no fitted models or empirical metrics**.
October captures cannot backfill September. All five candidates return insufficiency;
this diagnostic itself is recorded in SQLite and MLflow.

Feature definitions, units, versions, dependency/availability/missingness rules live in
`features/registry.py`; coherent transforms live in `features/pipeline.py`. Each row has
feature values/hash, forecast and bias evidence, missingness and eligibility reasons.
A full local day of hourly forecast is required, including 23/25-hour DST days. Its maximum
is a **forecast proxy**, not an official observed maximum. Partial days remain missing.
Distinct vintages provide revisions; latest models provide disagreement. Ensemble members
and recent observations are supported canonical inputs but are not captured by these two
provider requests. Nulls remain null; learned imputers fit only on the training partition.

Station bias uses earlier events' frozen forecasts and only label revisions available by
the current decision. Contract rules must be historically known and explicitly Fahrenheit;
unsupported payouts/units are refused. Scalar targets require the contract's named source,
station/date, integer Fahrenheit and a defensible post-day availability clock. NWS CLI is
never substituted for a Weather Company settlement. Final binary Kalshi outcomes can
score predictions but do not supply a scalar temperature target. Labels are stored
separately and never included in the feature vector.

Feature manifests hash source rows, observations/archive snapshot, feature definitions,
transform code, each row's cutoff and content; Parquet has a checksum. Modeling records
configuration, code/runtime versions, feature schema and source dataset. Joblib artifacts,
JSON/Parquet predictions, metrics, report and checksums identify each deterministic run.
The existing SQLite registry stores runs/models/predictions; local MLflow tracks parameters,
metrics and artifacts. Interrupted staging builds can resume; completed artifacts are
checksum-verified and registration is idempotent. Joblib can execute code: load only
trusted local artifacts using an externally expected hash and `trusted=True`.

## Complete synthetic pipeline proof

```bash
uv run entropytrade model-demo --output data/cache/r2-synthetic --days 300
```

Use a new output directory. This generates **explicitly synthetic** R1-compatible evidence
for two city configurations and 300 date blocks/600 city-day events. It builds features,
fits all five candidates, fits separate calibrators, evaluates validation and (for this
controlled demonstration only) final holdout, runs two fixed pre-holdout walk-forward
windows and writes artifacts to the existing registry/MLflow. These metrics are software
verification, not empirical Kalshi results, a profitable strategy or a source-coverage claim.

Models are an empirical training-temperature CDF, raw forecast + **assumed 3°F spread**,
learned forecast-error normal distribution, regularized Ridge temperature regression and
histogram gradient boosting. Modeling the underlying reported integer high yields coherent
strict threshold and inclusive bucket YES probabilities via CDF differences. This is an
explicit statistical assumption about reported integer values, not a provider rounding rule.
Ridge/boosting residual spreads are training estimates, not confidence intervals. Calibration
is monotone Platt/logistic CDF mapping (or optional isotonic), preserving bucket coherence.

Date blocks split chronologically 60% training / 20% validation / 20% final holdout. The
last 20% of training is reserved for calibration; fitting/calibration reject overlapping
events, future labels and overlapping decision schedules. One frozen decision per city/day
fits weather models; all related contracts stay together. Defaults require 60 fit events,
20 calibration/evaluation events and 200 fit events for boosting. These are minimum gates,
not guarantees of statistical power. Walk-forward runs fixed forecast-error/Ridge candidates
on two expanding windows entirely before the final holdout when at least 80 pre-holdout
dates exist. Metrics weight each city/day equally, report independent events/contracts,
Brier/log loss, reliability and (with adequate sample) calibration slope/intercept. Cities
on the same date may remain correlated; no significance or edge claim follows from counts.

`model --config CONFIG.json` accepts the fields in `ModelingConfig`. Real runs leave
`evaluate_holdout` false. Holdout evaluation is an explicit final action, not a tuning loop;
the file boundary is not a security sandbox. R3 tools must withhold protected rows/outcomes.
Market benchmarks require a fresh, receipt-backed quoted midpoint. Candles/prints are
excluded. Midpoints are not guaranteed fills; executable price/net edge stay null. No P&L,
strategy promotion, repeated search engine or trading transport is part of R2.

## Remaining collection requirements

Accumulate many decision-time forecasts alongside actual rule/contract snapshots and
source-matched resolved scalar highs. Polling alone does not obtain Weather Company
settlement history. The current forward capture contains one distinct product per provider
and city, so **real revisions and fitted calibration are still data-limited**. Keep the
read-only market collector running with its separate read key when available. Historical
Open-Meteo stitched/lead-offset series remain assumption-based unless an adapter can prove
run/publication availability; NOAA model initialization alone also does not prove when a
specific output was published. No historical clock is manufactured to pass eligibility.
