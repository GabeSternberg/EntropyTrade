---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.95 checkpoint

Date: 2026-10-02. Phase 4.95 is complete. It is off-plan work. No order was
sent. No rule was promoted. The Philadelphia thresholds were not changed
after the Oklahoma City score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.95.md`.

## Which market

`KXHIGHTOKC` is the next `KXHIGH*` ticker after `KXHIGHAUS` in the stored
series list. The contract names Oklahoma City (CLIOKC). The CLI products
are issued as `KOUN`. The forecast request, frozen before the score, was
Open-Meteo previous-runs at 35.46756 N, 97.51643 W, the geocoded Oklahoma
City place. The API returned 35.477013 N, 97.50638 W. The window is
2026-08-23 through 2026-10-01.

40 `B80.5` tickers were requested. None exist. All 40 returned
`{"error":{"code":"not_found","message":"not found"}}`. Those strikes were
not replaced. There are 0 trade prints. Raw pages stay under `data/raw`.
Fidelity is `trade-print`. A print is not a guaranteed fill.

## Score

The bracket is still 80 to 81 inclusive. The price threshold is still 0.40.
The midpoint is still 80.5. The decision is still 15:00 UTC. 40 forecasts
were stored. 39 CLI labels were stored. 2026-09-16 is absent because the
stored products for that day are same-day summaries, and the existing parser
does not take a high that is available on the observation day. No high was
invented for it. The stored highs run from 76 to 108, and none fall inside
80 to 81.

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity | Base and conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_above | 38 | 38 | 0 | 100.000000 | 100.000000 |
| forecast_below | 1 | 1 | 0 | 100.000000 | 100.000000 |
| forecast_gap | 38 | 0 | 0 | 100.000000 | 100.000000 |

Optimistic equity stays 100.000000 because there is no print to treat as a
fill. Base and conservative also stay 100.000000. Nothing is promoted.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 235 passed
(233 from Phase 4.94, plus 2 Oklahoma City tests).

## Files

- `backend/src/entropytrade/weather/oklahomacity_rules.py`
- `backend/tests/unit/test_oklahomacity_rules.py`
- `data/public/oklahomacity/manifest.json`
- `data/public/oklahomacity/markets.json`
- `data/public/oklahomacity/prints.sqlite`
- `data/public/oklahomacity/previous-runs.json`
- `data/public/oklahomacity/cliokc-afos.txt`
