---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.91 checkpoint

Date: 2026-10-02. Phase 4.91 is complete. It is off-plan work. No order was
sent. The holdout was not scored. Nothing was promoted. The full-window
gap equity 102.430000 was not used as a threshold. 0.40, 15:00 UTC, and
80.5 were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.91.md`.

## Split

Train 20, validation 10. The holdout is not scored. Fidelity is
`trade-print`. A print is not a guaranteed fill. Base and conservative
assume 0 fills and equity 100.000000 on every rule in both folds.

## Train

| Rule | Fires | Agreements | Optimistic equity | Base equity | Conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 2 | 1 | 100.750000 | 100.000000 | 100.000000 |
| forecast_above | 14 | 10 | 99.400000 | 100.000000 | 100.000000 |
| forecast_below | 4 | 3 | 99.660000 | 100.000000 | 100.000000 |
| forecast_gap | 16 | 5 | 102.510000 | 100.000000 | 100.000000 |

## Validation

| Rule | Fires | Agreements | Optimistic equity | Base equity | Conservative equity |
| --- | --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 100.000000 | 100.000000 | 100.000000 |
| forecast_above | 3 | 2 | 100.000000 | 100.000000 | 100.000000 |
| forecast_below | 7 | 6 | 100.000000 | 100.000000 | 100.000000 |
| forecast_gap | 3 | 0 | 99.920000 | 100.000000 | 100.000000 |

The train gap equity is 102.510000. It is not the full-window 102.430000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 228 passed
(227 from Phase 4.90, plus 1 fold test).

## Files

- `backend/tests/unit/test_chicago_fold_equity.py`
