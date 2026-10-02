---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.76 checkpoint

Date: 2026-10-02. Phase 4.76 is complete. It is off-plan work. No order was
sent. No model was fit.

A copy of this file is in the repository at `docs/phase-reports/phase-4.76.md`.

## What was written

`docs/research/philadelphia-daily-high.md` states the stored Philadelphia
scores. Four rules were tried. None was promoted. Optimistic equity is
100.000000 for the inside, above, and below rules, and 99.900000 for the
gap rule, which assumes 3 fills. Base and conservative equity are
100.000000 on every rule. Walk-forward uses train 20, validation 10, and
holdout 10. The holdout is not scored. The gap rule assumes 2 fills in
train (equity 99.910000) and 1 in validation (equity 99.990000).

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 213 passed
(212 from Phase 4.75, plus 1 note test).

## Files

- `docs/research/philadelphia-daily-high.md`
- `backend/tests/unit/test_philadelphia_note.py`
