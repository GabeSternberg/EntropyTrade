---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.224 checkpoint

Date: 2026-10-03. Phase 4.224 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.224.md`.

## Rule

This count rule was written before the one-contract open-interest values
were counted.

Count stored Philadelphia candlesticks whose open interest is exactly
1.00. An open-interest value counts when `open_interest_fp` parses as the
decimal 1. Record the count and the first and last ticker-hour that has
that value. Do not treat 1.00 as a size at the touch. Do not compare it
to 0.40. Do not align a value to 15:00 UTC. Do not trade. Do not score a
holdout. Do not promote. No live order. The CLI coverage row for open
interest stays "no stored value". Do not change `2°F` or `0.40`.

## Result

5529 open-interest values are decimal strings. 1 of them is exactly 1. The
first and the last are both `KXHIGHPHIL-26SEP09-B84.5#0`. 1.00 is not a
size at the touch. The count was not compared to 0.40 and was not used as
a threshold. The value was not aligned to 15:00 UTC. The CLI coverage row
for open interest still says no stored value. Nothing was traded. `2°F`
and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 377 passed.
