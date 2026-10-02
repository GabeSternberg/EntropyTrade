---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.75 checkpoint

Date: 2026-10-02. Phase 4.75 is complete. It is off-plan work. No order was
sent. No rule was promoted. The Philadelphia thresholds were not changed
after the Chicago score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.75.md`.

## Which city

`GET /series?category=Climate%20and%20Weather` returned 50 `KXHIGH*`
tickers. `KXHIGHCHI` appears before `KXHIGHNY` in that list, so the city
is Chicago. The contract text names Chicago (CLIMDW) and the 80-81 bracket.
The CLI products are issued as `KLOT`. The forecast request, frozen before
the score, was Open-Meteo previous-runs at 41.79 N, 87.75 W. The API
returned 41.77811 N, 87.737 W. The window is 2026-08-23 through 2026-10-01,
the same dates as Philadelphia.

40 `B80.5` tickers were requested. 11 exist. 29 returned
`{"error":{"code":"not_found","message":"not found"}}`. Those strikes were
not replaced with a neighbor. 14,675 trade prints are in the compact table.
Raw pages stay under `data/raw`. Fidelity is `trade-print`. A print is not
a guaranteed fill. The rows are not joined to the Philadelphia replay.

## Score

The bracket is still 80 to 81 inclusive. The price threshold is still 0.40.
The midpoint is still 80.5. The decision is still 15:00 UTC. These four
rules are four more tried hypotheses.

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity | Base and conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 2 | 1 | 1 | 100.750000 | 100.000000 |
| forecast_above | 17 | 12 | 2 | 99.400000 | 100.000000 |
| forecast_below | 21 | 18 | 1 | 99.660000 | 100.000000 |
| forecast_gap | 19 | 5 | 7 | 102.430000 | 100.000000 |

40 CLI labels and 40 forecasts were stored. Base and conservative assume
no fill. Philadelphia's `forecast_gap` optimistic equity is still
99.900000, and its replay equity is still 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 212 passed
(210 from Phase 4.74, plus 2 Chicago tests).

## Files

- `backend/src/entropytrade/weather/chicago_rules.py`
- `backend/tests/unit/test_chicago_rules.py`
- `data/public/chicago/manifest.json`
- `data/public/chicago/markets.json`
- `data/public/chicago/kxhigh-order.json`
- `data/public/chicago/prints.sqlite`
- `data/public/chicago/previous-runs.json`
- `data/public/chicago/climdw-afos.txt`
