---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.61 checkpoint

Date: 2026-10-02. Phase 4.61 is complete. It is off-plan work. No order was
sent. No rule was promoted. The thresholds were not changed after the score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.61.md`.

## Rules, fixed before the score

The bracket is 80 to 81 inclusive. The price threshold is 0.40. The midpoint
is 80.5. Fidelity is `trade-print`. A print is not a guaranteed fill. Base
and conservative never take one. The historical trade table is not used.

| Rule | Fires when | Optimistic action |
| --- | --- | --- |
| forecast_inside | forecast is inside 80-81 | buy YES at a print at or below 0.40 |
| forecast_above | forecast is above 81 | buy NO when a YES print is at least 0.60 |
| forecast_below | forecast is below 80 | buy NO when a YES print is at least 0.60 |
| forecast_gap | forecast is above 80.5 | buy YES at a print at or below 0.40 |

Each rule is a tried hypothesis.

## Score on the 2026 CLI window

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity | Base and conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 0 | 100.000000 | 100.000000 |
| forecast_above | 19 | 17 | 0 | 100.000000 | 100.000000 |
| forecast_below | 21 | 14 | 0 | 100.000000 | 100.000000 |
| forecast_gap | 19 | 1 | 3 | 99.900000 | 100.000000 |

`forecast_above` and `forecast_below` fire, and the label often agrees, but
no print meets the NO price, so they do not fill. `forecast_gap` assumes
three YES fills under the optimistic label. Those three lose 0.10 in total.
That assumption is not a guaranteed fill. No fee was applied.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 189 passed
(186 from Phase 4.60, plus 3 rule tests).

## Files

- `backend/src/entropytrade/weather/informational_rules.py`
- `backend/tests/unit/test_informational_rules.py`
