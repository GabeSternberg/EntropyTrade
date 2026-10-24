# Research results and evidence limits

R0 review, 2026-10-24. These are durable conclusions from committed source bodies,
manifests, code and selected reports. They do not establish a validated profitable strategy.
R0 reran the stored-data summaries; it did not refresh external services.

## Historical market data

The repository retains 817 files under `data/public/` (about 88 MB), including public/demo
Kalshi market metadata, trade prints, candles, a few contemporary books, IEM CLI products,
Open-Meteo fields, NWS points/forecast/hourly snapshots, failed responses and manifests.
Main weather studies span 2026-08-23 through 2026-10-01. Coverage varies by source/city.
`data/raw`, `normalized`, `features` and `backtests` are not an operating layered pipeline;
legacy committed study artifacts are mainly under `data/public/`.

- The CLI-window manifest records **240 empty settled-market book responses across 66
  strike suffixes**, **230 candle files**, and no failed calls. Only **one** empty book
  body was retained; the other 239 paths are null. A manifest count is not 240 retained bodies.
- The 12 nonempty books used by the Philadelphia score were fetched on October 2 for
  October 2–3 contracts. They do not overlap a decision before a stored final CLI label.
- Trade prints prove a trade occurred. Candles describe an interval. Neither establishes
  displayed executable depth, queue position or an available fill at the decision time.
- Much city exploration requested a fixed B80.5 strike; a miss means that requested ticker
  was absent, not that the city had no useful listed contracts. The stored generic scan has
  41 tickers, 13 scored, zero promoted, and zero holdout-scored (R0 local recomputation).

Evidence: `data/public/kalshi-public/cli-window/manifest.json`,
`exchange/{cli_window,public_tape,historical_trades}.py`,
[book-coverage report](phase-reports/phase-4.55.md), [scan note](research/kxhigh-scan.md).

## Settlement and forecast sources

Saved KXHIGH rules name **The Weather Company** for the studied dates. NWS CLI/IEM
highs are useful comparison labels, not a substitute settlement source. Matching labels
on an overlap does not establish equivalence on all dates or justify a future rule fallback.
The Weather Company parser accepts a small custom `high_f` JSON fixture; no actual
provider schema/integration has been demonstrated.

Open-Meteo previous-day fields provide real forecast-like source values, but the studies
assign availability using rules (midnight or valid hour minus 24 hours). The stored
revision manifest explicitly says `clock: rule`. Rejected `run` requests were replaced by
previous_day1/previous_day2 fields, roughly a day apart, not verified 03:00/15:00 model
publications. Observation archives also have assigned next-day availability. These clocks
are assumptions, not point-in-time evidence. Do not use them to certify tradable edge.

Stored HRRR/GFS/ECMWF/ensemble and humidity/dew point/cloud/wind/precipitation data are
partial provider compatibility evidence. A successful parser is not an aligned feature
history. The NWS points/14-period/156-hour snapshots are later than the studied historical
windows and cannot reconstruct historical forecast revisions. Many later reports only
counted or preserved metadata strings. Provider timestamps and missing publication times
must remain distinguishable in R1.

Evidence: [source audit](external-repositories.md), `data/public/open-meteo/*manifest.json`,
`data/public/nws/`, [revision clock report](phase-reports/phase-4.142.md).

## Measured Philadelphia baseline study

R0 reran `weather.settlement_score.load_aligned_score(Path("data/public"))`:

| Quantity | Stored-data result |
| --- | --- |
| CLI-aligned days | 40 |
| Forecast MAE against CLI | 2.9925 °F |
| MAE first / second 20 days | 2.94 / 3.045 °F |
| Probability-scored days | 39 |
| Brier, binary raw forecast | 0.05128205 |
| Brier, prior CLI hit rate | 0.06005700 |
| Brier, arithmetic blend | 0.05280102 |
| Forecast inside 80–81 / eligible sized books | 0 / 0 |
| Replay fills / ending equity from 100 | 0 / 100.000000 |
| Fitted model / promoted strategy | none / none |

The raw forecast always said NO on this bracket. Its low Brier reflects a rare YES
outcome (two misses in 39 days); it is not evidence of useful calibration or trading edge.
The blend is an arithmetic average, not fitted probability calibration. The nominal
30-day model gate opened but no model was fitted. These descriptive scores used the full
40-day window and must not be presented as a protected holdout evaluation.

Evidence: `backend/tests/unit/test_settlement_score.py`,
[original score report](phase-reports/phase-4.53.md). The CLI feature manifest hash reran as
`sha256:39e075dc258aa7da7ee7561b352515a04726eeef69d0b3970e2bb531e607ddeb`.

## Trading rules and negative findings

The four initial rules (forecast inside/above/below/gap) and later upward/downward
revision/containing-bracket variants explored explicit fixed thresholds. A 20/10/10
train/validation/holdout split was used in several studies; holdout was skipped/refused.
Base/conservative print scenarios assume no fills. This is an execution-data limitation,
not a measured real-market flat P&L result.

For the initial Philadelphia gap rule, the recorded optimistic print scenario had two
train fills ending at 99.91 and one validation fill ending at 99.99, each from 100.
Other initial rules had no optimistic fills. Those are assumed fills, not observed orders
or established after-fee returns; fee schedule evidence is incomplete.

R0 regenerated **551** revision-bracket train/validation records, **91** binary fires.
The original analysis found just three fires with a stored containing contract; most
selected tickers remain `no-stored-bracket`. Those records have no bid/ask/net edge and
no fitted calibrator/uncertainty. `probability_yes` represents a rule fire, not a calibrated
contract probability. Cross-city attempts increase selection risk and are not independent
replications. No candidate has passed an adequate statistical or execution validation gate.

Evidence: [walk-forward results](phase-reports/phase-4.62.md),
[revision record analysis](phase-reports/phase-4.163.md), `weather/revision_records.py`.

## Claims that remain unsupported

Synthetic fixture equity 100.60 (zero fee) or 100.59 (example coefficient 0.02) proves
accounting behavior, not market profit. The early candle-derived pseudo-books must not
be used for executable claims. Maker/taker type and multiplier were stored, but the
fee-schedule fetch failed with HTTP 429 and the quadratic coefficient remains unverified.
No provider-backed agent research, fitted model comparison, continuous authenticated feed,
continuous shadow performance, observed live fills or real-account reconciliation has
been demonstrated. No profitable strategy is validated; these studies also do not prove
that all temperature strategies are unprofitable.

Next questions: which actual listed contracts have usable decision-time quote/depth data;
which providers expose verifiable forecast vintages; how settlement values are obtained;
and whether sufficient independent events remain after quality gates and temporal splits.
