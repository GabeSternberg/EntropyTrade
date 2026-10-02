---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.85 checkpoint

Date: 2026-10-02. Phase 4.85 is complete. It is off-plan work. No order was
sent. The holdout was not scored. Nothing was promoted. 0.50 and 15:00
were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.85.md`.

## Split

The split is train 20, validation 10, holdout 10. The YES line is still
0.50. A print is not a guaranteed fill.

Train has 8 eligible prints, 5 YES guesses, and 8 agreements. Validation
has 2 eligible prints, 0 YES guesses, and 2 agreements.

Philadelphia's walk-forward is unchanged: train 5 prints and 4 agreements,
validation 3 prints and 3 agreements, no YES guess in either split. Its
holdout stays unscored.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 222 passed
(221 from Phase 4.84, plus 1 walk-forward test).

## Files

- `backend/src/entropytrade/weather/chicago_rules.py`
- `backend/tests/unit/test_chicago_guess_walk.py`
