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

## R1 real-data demonstration (2026-10-24)

Public read-only SDK acquisition retrieved **36 actual contracts / six events** for
Philadelphia (`KXHIGHPHIL`) and Chicago (`KXHIGHCHI`), September 1–3, 2026, plus **1,060
hourly candle observations**. Eighteen contracts/three events per city; no acquisition
failures in the verified pull. Contracts were discovered from actual event responses,
not a fixed B80.5 request. Source receipts/raw bodies are in `data/r1-source/`.

The deterministic sample has 36 rows at 15:00 UTC and 36 finalized Kalshi YES/NO targets.
All rows have candle context; none has a certified historical rule snapshot, strict
forecast feature or executable historical book. The 1,920 legacy hourly forecast records
are preserved separately with units/valid times and unknown availability, not invented
issue times. Late contract snapshots do not prove historical rules or universe completeness.
These are data/coverage findings, not strategy or model results. Modeling a forecast-revision
edge remains unsupported until defensible vintages and enough independent events exist.

The sample manifest/version and row hash reproduce across frozen-source builds. See
[data platform commands](data-platform.md) and `data/r1-demo/` for Parquet, coverage,
provenance and checksums. The R1 operating guide also records the synthetic replay/restart
and mock transport evidence. No authenticated WebSocket handshake or multi-hour real feed
was verified: dedicated read credentials were absent.

Live REST verification exposed two compatibility facts: historical discovery rejects
simultaneous series/event filters, and public market bodies omit the SDK's required but
unused liquidity field. R1 handles both at the pinned SDK boundary, preserving missing
liquidity as None. Failed exploratory responses were retained locally under `data/cache/`
without altering the original Phase 4 inputs. No exchange order or LLM request was made.

R1 frozen demonstration version: `sha256:7be1ac67055e7abdc15bf90cdf093d257bde67f484440297add4428075c15b14`; row hash: `sha256:03dcb5e0af1d5b4b7382f1ae89054f3eb9dab12345136cad26f0bde4a92d596b`.
The [committed manifest](../data/r1-demo/7be1ac67055e7abdc15bf90cdf093d257bde67f484440297add4428075c15b14/manifest.json)
records exact inputs, coverage, code hashes and limitations.

## R2 forecast capture and modeling (2026-10-24–25)

Public **Open-Meteo GFS seamless** and **NWS hourly** collection completed three polls
across a clean stop/process restart for Philadelphia/Chicago, October 24 at 23:55–23:57 UTC.
The frozen archive contains **18 raw HTTP receipts, four distinct provider/location
vintages, 648 hourly points and zero failures**. Repeated products retained their original
first-seen times. Open-Meteo valid hours span October 24–30 UTC; NWS spans October 24–31.
There are 24 complete-local-day forecast maximum proxies available by the last receipt,
including source/hash evidence. These are forecast values, not verified scalar settlements.
Only one distinct vintage per provider/city was captured; real changing revisions and
long-running availability coverage have not yet accumulated.

Availability is the actual first retained receipt. Open-Meteo's captured response supplies
no model initialization or publication time. NWS update/generation clocks are product
metadata, not model initialization. The official [historical API documentation](https://open-meteo.com/en/docs/historical-forecast-api)
describes stitching the first hours of runs into a continuous series; the [previous-runs API](https://open-meteo.com/en/docs/previous-runs-api)
describes fixed 24/48-hour lead offsets. Neither by itself proves when a particular forecast
was published. These historical sources remain excluded from strict availability claims.
[NOAA/NWS API documentation](https://www.weather.gov/documentation/services-web-api) supports
the points → gridpoint hourly workflow. Forward receipt certification avoids a fabricated
historical publication clock; it does not recover missed upstream runs.

The **real R1 dataset diagnostic** now executes the connected feature/model/registry/MLflow
workflow. It has **six city/day events, three date blocks and 36 contracts**, but **zero
eligible forecast events and zero source-matched scalar-temperature targets**. October
captures cannot supply September features. All five model candidates explicitly refuse
fitting/evaluation. There are no empirical model scores, trading returns or promotions.
Weather Company integer settlement highs, matching historic rules, more independent aligned
events and execution-depth evidence remain missing. NWS CLI labels are not substituted.

Separately, an **explicitly synthetic** 300-date/two-city fixture proves all five models
fit, separate monotone calibration works, strict/inclusive contract probabilities are
coherent, validation/explicit fixture holdout and pre-holdout walk-forward runs execute,
and model/prediction/feature hashes reproduce. Training uses one frozen decision per city/day,
not four independent examples for its four contracts. Synthetic performance is exclusively
implementation verification. See the [frozen evidence and summaries](../data/r2-demo/README.md)
and [operating guide](weather-modeling.md); no empirical edge follows from that proof.

## R4 integrated evidence (2026-10-25)

The integrated offline research-to-experiment run over the existing real sample cleanly
returns two INSUFFICIENT_DATA candidates and an unsupported proposal. No new empirical
forecasting metrics, fills or P&L were established. Full software verification is separately
synthetic/mock; conservative execution produces no fills. Frozen audits, probability records,
ledger results and exact-replay identities are in [R4 evidence](../data/r4-demo/README.md).
These are integration findings, not a revision to the historical data/edge conclusions.
