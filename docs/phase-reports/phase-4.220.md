---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.220 checkpoint

Date: 2026-10-03. Phase 4.220 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.220.md`.

## Rule

This count rule was written before the distinct open-interest values were
counted.

Count the distinct stored Philadelphia candlestick open-interest values.
An open-interest value counts only when `open_interest_fp` is a decimal
string, including `0.00`. Record how many distinct values occur, and name
the smallest and the largest in numeric order. A missing value is not
filled in. Open interest is not a size at the touch. Do not compare a
value to 0.40. Do not treat the count as a threshold. Do not align a
value to 15:00 UTC. Do not trade. Do not score a holdout. Do not promote.
No live order. The CLI coverage row for open interest stays "no stored
value". Do not change `2°F` or `0.40`.

## Result

5529 open-interest values are decimal strings. 3846 values are distinct.
0 values were missing. In numeric order the smallest is 1.00 and the
largest is 39211.47. 0.00 is absent and was not invented. The ordered
values are locked by SHA-256
`612efff39fa2ba61230bad93320693b06bdc7df130e01936dcb2cd353385d071`. Open
interest is not a size at the touch. The count was not compared to 0.40
and was not used as a threshold. Values were not aligned to 15:00 UTC.
The CLI coverage row for open interest still says no stored value.
Nothing was traded. `2°F` and `0.40` were not changed. Nothing was
promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 369 passed.
