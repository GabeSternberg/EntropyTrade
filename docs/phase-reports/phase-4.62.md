---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.62 checkpoint

Date: 2026-10-02. Phase 4.62 is complete. It is off-plan work. No order was
sent. No LLM was called. No rule was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.62.md`.

## Split

The stored 40 CLI days use the existing split: 20 train, 10 validation, 10
holdout. The holdout window is built and then refused. Feature rows for
holdout days are not passed in. The rule scores receive train labels and
validation labels only.

## Scores

Fidelity stays `trade-print`. Base and conservative equity stays 100 on
both splits. Optimistic fills:

| Rule | Train fires | Train optimistic fills | Train optimistic equity | Validation fires | Validation optimistic fills | Validation optimistic equity |
| --- | --- | --- | --- | --- | --- | --- |
| forecast_inside | 0 | 0 | 100.000000 | 0 | 0 | 100.000000 |
| forecast_above | 15 | 0 | 100.000000 | 4 | 0 | 100.000000 |
| forecast_below | 5 | 0 | 100.000000 | 6 | 0 | 100.000000 |
| forecast_gap | 15 | 2 | 99.910000 | 4 | 1 | 99.990000 |

The gap rule's optimistic case assumes two fills in train and one in
validation. Those are not guaranteed fills. Thresholds were not changed.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 190 passed
(189 from Phase 4.61, plus 1 walk-forward test).

## Files

- `backend/src/entropytrade/weather/walk_forward.py`
- `backend/tests/unit/test_walk_forward.py`
