---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.233 checkpoint

Date: 2026-10-03. Phase 4.233 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.233.md`.

## Rule

This count rule was written before the distinct precipitation
probabilities were counted.

Count the distinct probability-of-precipitation values in the stored
Philadelphia NWS hourly forecast. The value is
`probabilityOfPrecipitation.value` when that field is a number. A missing
object or a null value is skipped and named. Record the count of periods,
the count of distinct values, the smallest, and the largest. Do not invent
a missing probability. Do not divide a value by 100. Do not call a value a
market probability. Do not compare a value to `0.40` or to `2°F`. Do not
align a period to the CLI decision clock. Do not trade. Do not score a
holdout. Do not promote. No live order. The CLI coverage row for NWS
forecast stays "no stored value". Do not change `2°F` or `0.40`.

## Result

156 periods were read. 0 values were missing or null. 14 values are
distinct: 0, 1, 2, 3, 4, 5, 7, 9, 11, 12, 15, 30, 39, and 66. The
smallest is 0 and the largest is 66. Absent integers were not invented.
A value was not divided by 100 and was not called a market probability.
The count was not compared to 0.40 and was not aligned to the CLI
decision clock. The CLI coverage row for NWS forecast still says no
stored value. Nothing was traded. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 395 passed.
