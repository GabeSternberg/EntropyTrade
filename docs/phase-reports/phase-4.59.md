---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.59 checkpoint

Date: 2026-10-02. Phase 4.59 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-4.59.md`.

## What the replay keeps out

Twelve stored books have a size, and every one of them is for 2 October or
3 October. The CLI window ends on 1 October. `_books_before_the_label`
drops a book when its market day has no CLI label, so none of the twelve
enter the replay. `sized_books_in_window` stays 0. Fills stay 0. Equity
stays 100.000000.

The twelve tickers are named on `AlignedScore.books_after_window`.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 184 passed.
The settlement test now locks those twelve tickers. No new test file.

## Files

- `backend/src/entropytrade/weather/settlement_score.py`
- `backend/tests/unit/test_settlement_score.py`
