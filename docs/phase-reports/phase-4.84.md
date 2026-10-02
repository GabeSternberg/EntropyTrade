---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.84 checkpoint

Date: 2026-10-02. Phase 4.84 is complete. It is off-plan work. No order was
sent. Nothing was promoted. 0.50 and 15:00 were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.84.md`.

## Score

The YES line is still 0.50. The decision is still 15:00 UTC. A print is
not a guaranteed fill.

Chicago has 40 CLI days. 11 have a B80.5 print at or before 15:00 UTC.
29 do not. 5 of the 11 prints are YES guesses. 10 agree with the CLI
bracket.

Philadelphia is unchanged: 10 days with a print, 0 YES guesses, 9
agreements.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 221 passed
(220 from Phase 4.83, plus 1 guess test).

## Files

- `backend/src/entropytrade/weather/chicago_rules.py`
- `backend/tests/unit/test_chicago_print_guess.py`
