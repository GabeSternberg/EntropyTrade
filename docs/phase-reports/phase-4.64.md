---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.64 checkpoint

Date: 2026-10-02. Phase 4.64 is complete. It is off-plan work. No order was
sent. The 0.50 line was not changed after the count.

A copy of this file is in the repository at `docs/phase-reports/phase-4.64.md`.

## What was compared

For each stored KXHIGHPHIL historical market, the last trade print is the
print with the greatest `created_us`. If several prints share that time,
the guess uses the highest YES price. A price at or above 0.50 is a YES
guess. A lower price is a NO guess. Markets with no print are not given a
guess. The print is not a fill. The comparison is not joined to the 2026
CLI replay.

3,720 markets have a stored result (620 yes, 3,100 no). 3,666 have a last
print. 54 do not. 621 last prints are YES guesses. 3,661 guesses match the
stored result. Five do not:

- `KXHIGHPHIL-26MAR15-T53` last YES price 0.13, result yes
- `KXHIGHPHIL-26MAR15-B53.5` last YES price 0.82, result no
- `KXHIGHPHIL-25JAN14-T26` last YES price 0.99, result no
- `KXHIGHPHIL-24DEC10-B56.5` last YES price 0.16, result yes
- `KXHIGHPHIL-24DEC10-B54.5` last YES price 0.80, result no

2,753 last prices are at most 0.01. 594 are at least 0.99. 292 sit strictly
between 0.01 and 0.50. 27 sit at or above 0.50 and below 0.99. None are
exactly 0 or exactly 1. Agreement this high, with prices piled at the
extremes, is the last print in the tape. It is not evidence that a forecast
would have been right. Nothing is promoted. CLI replay equity stays
100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 193 passed
(191 from Phase 4.63, plus 2 last-print tests).

## Files

- `backend/src/entropytrade/weather/last_print.py`
- `backend/tests/unit/test_last_print.py`
