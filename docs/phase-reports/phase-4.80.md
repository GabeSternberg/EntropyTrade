---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.80 checkpoint

Date: 2026-10-02. Phase 4.80 is complete. It is off-plan work. No order was
sent. The holdout was not scored. Nothing was promoted. The registered
thresholds were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.80.md`.

## Split

Chicago has 40 CLI days. The split is the one already used for
Philadelphia: train 20, validation 10, holdout 10. The bracket is still
80 to 81. The price threshold is still 0.40. The midpoint is still 80.5.
The decision is still 15:00 UTC. A print is not a guaranteed fill. Base
and conservative assume 0 fills and equity 100.000000 on every rule in
both scored splits.

## Train

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity |
| --- | --- | --- | --- | --- |
| forecast_inside | 2 | 1 | 1 | 100.750000 |
| forecast_above | 14 | 10 | 2 | 99.400000 |
| forecast_below | 4 | 3 | 1 | 99.660000 |
| forecast_gap | 16 | 5 | 6 | 102.510000 |

## Validation

| Rule | Fires | Label agrees | Optimistic fills | Optimistic equity |
| --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 0 | 100.000000 |
| forecast_above | 3 | 2 | 0 | 100.000000 |
| forecast_below | 7 | 6 | 0 | 100.000000 |
| forecast_gap | 3 | 0 | 1 | 99.920000 |

The holdout is not in this table.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 217 passed
(216 from Phase 4.79, plus 1 walk-forward test).

## Files

- `backend/src/entropytrade/weather/chicago_rules.py`
- `backend/tests/unit/test_chicago_walk_forward.py`
