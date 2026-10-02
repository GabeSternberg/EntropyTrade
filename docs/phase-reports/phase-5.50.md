---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 5.50 checkpoint

Date: 2026-10-02. Phase 5.50 is complete. It is off-plan work. No order was
sent. No LLM provider was called.

A copy of this file is in the repository at `docs/phase-reports/phase-5.50.md`.

## What ran

The 40 stored CLI days are split in time with the existing `SplitWindow`
values: 20 train, 10 validation, 10 holdout. `run_walk_forward` runs train
and validation and skips the holdout. A direct replay of the holdout window
raises `ReplayError`. Holdout feature rows are not passed in.

Train MAE is 2.94 °F. Validation MAE is 2.53 °F. The holdout labels are not
scored here. There is still no sized book, so fills stay 0 and equity stays
100.000000. Nothing was promoted.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 167 passed
(165 from Phase 4.56, plus 2 walk-forward tests).

## Files

- `backend/src/entropytrade/weather/walk_forward.py`
- `backend/src/entropytrade/weather/settlement_score.py`
- `backend/tests/unit/test_walk_forward.py`
