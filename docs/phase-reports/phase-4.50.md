---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.50 checkpoint

Date: 2026-10-02. Phase 4.50 is complete. It is off-plan work, numbered 4.50.
No order was sent. No API key was used. The production host was not called.
`attempt_submit` is not connected to `KalshiGateway`.

A copy of this file is in the repository at `docs/phase-reports/phase-4.50.md`.

## What was fetched

Unauthenticated GET only, on 2026-10-02 at 06:34 UTC. Bodies are under
`data/public/`. `entropytrade.weather.public_dataset` reads those files and
does not open a socket.

| Call | Result |
| --- | --- |
| Open-Meteo previous-runs, hourly `temperature_2m_previous_day1`, past 40 days, 39.87 N, 75.23 W, Fahrenheit | HTTP 200. 960 hours, 2026-08-23 through 2026-10-01. |
| Open-Meteo archive, daily `temperature_2m_max`, 2026-08-23 through 2026-10-01, same point | HTTP 200. 40 days. |
| Open-Meteo previous-runs, daily `temperature_2m_max_previous_day1` | HTTP 400. Body below. No rows were invented from it. |
| Kalshi demo `GET /trade-api/v2/markets?series_ticker=KXHIGHPHIL`, 11 pages | HTTP 200. The stored file keeps the 360 market objects whose tickers start with `KXHIGHPHIL-26AUG`, `26SEP`, or `26OCT`. The other pages were not committed. |
| Kalshi demo hourly candlesticks for `KXHIGHPHIL-*-B80.5` on days from 2026-08-23 through 2026-09-30 where that ticker existed | HTTP 200. Nine files. |
| Kalshi demo order book for `KXHIGHPHIL-26AUG23-B80.5` | HTTP 200. `yes_dollars` and `no_dollars` were both empty. |

The failed call's body, unchanged:

```json
{"reason":"Invalid value: Cannot initialize ForecastVariableDaily from invalid String value temperature_2m_max_previous_day1","error":true}
```

Hourly `temperature_2m_previous_day1` is the forecast that was actually stored.
The archive daily max is the label. It is not an NWS CLI product and it is not
The Weather Company. The request point snapped to about 39.864 N, 75.223 W.
Settlement of `KXHIGHPHIL` is still CLIPHL via the contract text.

## How a row is timed

Every stored row has `available_at`, `source`, and `endpoint`.

- A previous-day hour is available 24 hours before that hour. That is what the
  field name means. The daily forecast is the max of those hours, available at
  00:00 UTC on the valid day, which is after every hour's previous-day run.
- The archive response has no issue time. The label is treated as available at
  12:00 UTC on the next calendar day, so it is not visible during the valid day.
- A market row uses `updated_time` from the market object.
- A candle row uses `end_period_ts`.
- The empty order book has no exchange time. Its `available_at` is the fetch
  time. It is not turned into levels.

A candle becomes a book only when the close bid and close ask are both strictly
inside (0, 1), the book is not crossed, and `volume_fp` is positive. The level
quantity is that hour's volume. The candle does not include a size at the
touch. One hour qualified: `KXHIGHPHIL-26AUG25-B80.5` at 2026-08-25 14:00 UTC,
bid 0.09, ask 0.15, volume 1.00.

The saved `B80.5` markets are `between` strikes with floor 80 and cap 81,
matching the contract text (80–81 °F, inclusive, The Weather Company).

## Research questions

These numbers are from the stored rows. The loader's tests lock them.

**What has predictive value?** The previous-day Open-Meteo max against the
same provider's archive high has mean absolute error 1.4725 °F over 40 days.
On the 80–81 bracket, the raw 0/1 forecast was wrong on 2 of 39 days that had
a prior label (Brier 0.05128205128205128205128205128). Those two archive days
inside the bracket are 2026-09-16 and 2026-10-01. The forecast was inside the
bracket on 0 days. That is agreement with this archive, not with CLIPHL.

**What adds incremental value?** Climatology, using only labels already
available at 15:00 UTC, has Brier 0.05036444892650982740970468118 on the same
39 days. The average of climatology and the raw indicator is
0.05072391959520405119825128533, which sits between them and does not beat
climatology. The one sized book has midpoint 0.12 and Brier 0.7744 against
the official YES. One day is not a market model. Nothing is promoted.

**Is there net edge after costs?** The forecast rule buys one YES only when
the previous-day max would resolve 80–81, limit 0.40, fill-or-kill. It signaled
on 0 days. Replay fills are 0 and ending equity is 100 at fee coefficient 0
and at 0.02, with latency 0 and with latency 2 hours. No edge was observed.
On 9 finalized `B80.5` days that also have an archive high, the archive
bracket and the official `result` disagree once: 2026-08-25, archive high
79.8 (not in 80–81), official result `yes`. The other eight agree, and all
eight are `no`.

**How stable is it?** The first 20 days have MAE 1.315 °F. The second 20 have
MAE 1.63 °F. The sample is 40 days at one gridpoint. It is not claimed to be
stable.

**How sensitive is profitability to execution assumptions?** A separate probe
buys the one displayed ask whether or not the forecast says YES. It is not the
forecast rule. At latency 0 and fee coefficient 0 it fills at 0.15, the
contract settles YES, and equity is 100.85. Coefficient 0.02 charges a 0.01
taker fee and equity is 100.84. The coefficient is an argument. It is not
0.07. At a two-hour latency the probe does not fill and equity stays 100,
because that hour is the only sized book. The forecast rule never reaches
this path.

`refuse_fitted_model` does not raise at 40 scored days. No model was fit.
There is no retraining.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 143 passed
(140 from Phase 10, plus 3 public-dataset tests).

## Files

- `data/public/` — raw bodies, the market subset, and `manifest.json`
- `backend/src/entropytrade/weather/public_dataset.py`
- `backend/tests/unit/test_public_dataset.py`
- `docs/weather.md`

## Weaknesses

- The archive clock is a rule, not a timestamp from the response.
- Quote size at the touch was not in the candle. Volume stands in for it on
  the one book that qualified.
- Eleven market-list pages returned 200 and were not stored in full. The
  retained objects are verbatim, limited to August, September, and October
  2026 tickers.
- Demo-host quotes are not a production recording. The production host was
  not called.
- Open-Meteo at this coordinate is not the CLIPHL settlement value. The one
  disagreement above is the evidence in this pull.

## Decisions

- The daily previous-run variable was rejected by the server. The hourly
  field that succeeded is the forecast. The 400 body is kept.
- An empty order book stays empty.
- The forecast rule and the ask probe are separate. The probe exists so the
  one real ask can show the fee and the latency. It is not a claim of edge.
