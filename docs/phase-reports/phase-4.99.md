---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.99 checkpoint

Date: 2026-10-02. Phase 4.99 is complete. It is off-plan work. No order was
sent. No rule was promoted. The Philadelphia thresholds were not changed
after the Dallas score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.99.md`.

## Which market

`KXHIGHTDAL` is the next ticker after `KXHIGHHOU`. A listed sample names
Dallas (CLIDFW) and is a greater-than-81 Fahrenheit contract, not B80.5.
That strike was not substituted. The CLI products are issued as `KFWD` for
Dallas/Fort Worth. The forecast request, frozen before the score, was
Open-Meteo previous-runs at 32.89743 N, 97.02196 W, the NWS station KDFW
geometry. The API returned 32.893456 N, 97.02648 W. The window is
2026-08-23 through 2026-10-01.

40 `B80.5` tickers were requested. None exist. All 40 returned
`{"error":{"code":"not_found","message":"not found"}}`. There are 0 trade
prints. Fidelity is `trade-print`. A print is not a guaranteed fill.

## Score

The bracket is still 80 to 81 inclusive. The price threshold is still 0.40.
The midpoint is still 80.5. The decision is still 15:00 UTC. 40 CLI labels
and 40 forecasts were stored. One CLI high is 81. The rest are above 81.
None of the forecasts fall inside 80 to 81.

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity | Base and conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_above | 40 | 39 | 0 | 100.000000 | 100.000000 |
| forecast_below | 0 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_gap | 40 | 1 | 0 | 100.000000 | 100.000000 |

Optimistic equity stays 100.000000 because there is no print. Base and
conservative stay 100.000000. Nothing is promoted.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 240 passed
(238 from Phase 4.98, plus 2 Dallas tests).

## Files

- `backend/src/entropytrade/weather/dallas_rules.py`
- `backend/tests/unit/test_dallas_rules.py`
- `data/public/dallas/manifest.json`
- `data/public/dallas/markets.json`
- `data/public/dallas/prints.sqlite`
- `data/public/dallas/previous-runs.json`
- `data/public/dallas/clidfw-afos.txt`
