---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.73 checkpoint

Date: 2026-10-02. Phase 4.73 is complete. It is off-plan work. No order was
sent. No LLM was called. The 0.50 line and the 15:00 UTC decision were not
changed. The holdout was not scored.

A copy of this file is in the repository at `docs/phase-reports/phase-4.73.md`.

## What was walked forward

The Phase 4.72 guess uses the existing day split. 40 CLI days become train
20, validation 10, and holdout 10. Holdout labels are not passed to the
scorer. The holdout window is built and then refused. Feature rows for
those days are not passed in.

Train: 5 days have an eligible print, 15 do not. Zero YES guesses. 4
agreements. Validation: 3 days have an eligible print, 7 do not. Zero YES
guesses. 3 agreements. Fidelity stays `trade-print`. A print is not a
guaranteed fill. Nothing is promoted.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 210 passed
(209 from Phase 4.72, plus 1 walk-forward test).

## Files

- `backend/src/entropytrade/weather/cli_print_guess.py`
- `backend/src/entropytrade/weather/walk_forward.py`
- `backend/tests/unit/test_walk_forward.py`
