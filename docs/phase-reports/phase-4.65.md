---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.65 checkpoint

Date: 2026-10-02. Phase 4.65 is complete. It is off-plan work. No order was
sent. The 0.50 line was not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.65.md`.

## What was compared

The last print in the tape agreed with the result 3,661 times out of 3,666,
and most of those prices sat within a cent of 0 or 1. That print can be
after the day is over. This phase uses an earlier print: the last one whose
time is strictly before the market's `occurrence_datetime`. A print at that
instant is excluded. A YES price at or above 0.50 is a YES guess. The guess
is not a fill.

3,078 of the 3,720 stored markets have no occurrence time. They get no
guess. The missing time is not replaced with `close_time` or any other
field. The other 642 markets all have at least one print strictly before
occurrence, so none of those 642 are left without a guess.

75 of the 642 prints are YES guesses. 544 guesses match the stored result.
98 do not. Of the 642 prices, 168 are at most 0.01, 399 sit strictly
between 0.01 and 0.50, and 75 are at or above 0.50. None are at or above
0.99. Fidelity stays `trade-print`. Nothing is promoted. The 2026 CLI
replay still does not read these prints, and its equity stays 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 195 passed
(193 from Phase 4.64, plus 2 pre-occurrence tests).

## Files

- `backend/src/entropytrade/weather/before_occurrence.py`
- `backend/tests/unit/test_before_occurrence.py`
