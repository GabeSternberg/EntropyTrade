---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.94 checkpoint

Date: 2026-10-02. Phase 4.94 is complete. It is off-plan work. No order was
sent. No rule was promoted. The Philadelphia thresholds were not changed
after the Austin score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.94.md`.

## Which market

`KXHIGHAUS` is the next `KXHIGH*` ticker after `KXHIGHNY` in the stored
series list. The contract names Austin (CLIAUS). The CLI products are
issued as `KEWX` for Austin Bergstrom. The forecast request, frozen before
the score, was Open-Meteo previous-runs at 30.18304 N, 97.67987 W, the NWS
station KAUS geometry. The API returned 30.189165 N, 97.69134 W. The window
is 2026-08-23 through 2026-10-01.

40 `B80.5` tickers were requested. None exist. All 40 returned
`{"error":{"code":"not_found","message":"not found"}}`. A `B80.5` market
does exist for 2026-10-02, outside this window, and it was not pulled.
Higher brackets that were listed, such as `B99.5`, were not substituted.
There are 0 trade prints. Raw pages stay under `data/raw`. Fidelity is
`trade-print`. A print is not a guaranteed fill.

## Score

The bracket is still 80 to 81 inclusive. The price threshold is still 0.40.
The midpoint is still 80.5. The decision is still 15:00 UTC. 40 CLI labels
and 40 forecasts were stored. The CLI highs in this window run from 87 to
105, so none of them fall inside 80 to 81.

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity | Base and conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_above | 40 | 40 | 0 | 100.000000 | 100.000000 |
| forecast_below | 0 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_gap | 40 | 0 | 0 | 100.000000 | 100.000000 |

Optimistic equity stays 100.000000 because there is no print to treat as a
fill. Base and conservative also stay 100.000000. Philadelphia, Chicago,
and New York gap equity are still 99.900000, 102.430000, and 100.450000.
Philadelphia replay equity is still 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 233 passed
(231 from Phase 4.93, plus 2 Austin tests).

## Files

- `backend/src/entropytrade/weather/austin_rules.py`
- `backend/tests/unit/test_austin_rules.py`
- `data/public/austin/manifest.json`
- `data/public/austin/markets.json`
- `data/public/austin/prints.sqlite`
- `data/public/austin/previous-runs.json`
- `data/public/austin/cliaus-afos.txt`
