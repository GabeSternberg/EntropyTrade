---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.93 checkpoint

Date: 2026-10-02. Phase 4.93 is complete. It is off-plan work. No order was
sent. No rule was promoted. The Philadelphia thresholds were not changed
after the New York score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.93.md`.

## Which market

`KXHIGHNY` is the New York series. The sample contract says the maximum at
New York City (CLINYC) between 80-81 degrees. The CLI products are issued
as `KOKX` for Central Park. The forecast request, frozen before the score,
was Open-Meteo previous-runs at 40.78333 N, 73.96667 W, the NWS station
KNYC geometry. The API returned 40.78858 N, 73.9661 W. The window is
2026-08-23 through 2026-10-01.

40 `B80.5` tickers were requested. 11 exist. 29 returned
`{"error":{"code":"not_found","message":"not found"}}`. Those strikes were
not replaced. 26,644 trade prints are in the compact table. Raw pages stay
under `data/raw`. Fidelity is `trade-print`. A print is not a guaranteed
fill. The rows are not joined to the Philadelphia replay.

## Score

The bracket is still 80 to 81 inclusive. The price threshold is still 0.40.
The midpoint is still 80.5. The decision is still 15:00 UTC. 40 CLI labels
and 40 forecasts were stored.

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity | Base and conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 1 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_above | 14 | 7 | 5 | 100.240000 | 100.000000 |
| forecast_below | 25 | 25 | 1 | 100.640000 | 100.000000 |
| forecast_gap | 15 | 4 | 6 | 100.450000 | 100.000000 |

Base and conservative assume no fill. Philadelphia `forecast_gap` optimistic
equity is still 99.900000. Chicago `forecast_gap` optimistic equity is still
102.430000. Philadelphia replay equity is still 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 231 passed
(229 from Phase 4.92, plus 2 New York tests).

## Files

- `backend/src/entropytrade/weather/newyork_rules.py`
- `backend/tests/unit/test_newyork_rules.py`
- `data/public/newyork/manifest.json`
- `data/public/newyork/markets.json`
- `data/public/newyork/prints.sqlite`
- `data/public/newyork/previous-runs.json`
- `data/public/newyork/clinyc-afos.txt`
