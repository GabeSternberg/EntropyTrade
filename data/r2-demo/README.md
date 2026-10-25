# Frozen R2 evidence

**Real:** `weather.sqlite` contains raw public provider receipts and normalized first-seen
vintages for Philadelphia/Chicago; `weather-coverage.json` describes three polls including
a clean stop/process restart on October 24, 2026. There are 18 receipts, four distinct
vintages and 648 hourly points, with zero recorded failures. `forward-maxima.json` shows
24 complete-local-day forecast proxies known by the final receipt, with source evidence.
They are forecasts, not observed settlement temperatures or independent market labels.

`features/` and `models/` are the deterministic strict feature/model diagnostic on the
committed R1 September dataset plus this forward archive. Six city/day events/three dates,
36 contracts, zero eligible forecast events and zero scalar targets produce an explicit
insufficient-data result. No real trained model or empirical metric is presented.

**Synthetic:** `synthetic-evaluation.json` and `synthetic-report.md` are the separate
controlled 300-day/two-city software proof. All five models fit/calibrate and generate
coherent contract probabilities; these scores say nothing about empirical Kalshi skill
or profitability. Full synthetic dataset, model joblibs, predictions, SQLite registry and
MLflow artifacts can be recreated with `entropytrade model-demo --days 300 --output NEW_DIR`.
The development run remains locally under ignored `data/cache/r2-complete-demo/`.

See [operating guide](../../docs/weather-modeling.md) for exact commands, source semantics,
eligibility, statistical assumptions, safeguards and remaining collection requirements.
Do not append to this frozen database; use `data/cache/weather.sqlite` for ongoing capture.
`checksums.json` covers every frozen evidence file except itself.
