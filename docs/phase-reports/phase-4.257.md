---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.257 checkpoint

Date: 2026-10-03. Phase 4.257 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.257.md`.

## Rule

This count rule was written before the distinct forecast-period
precipitation probabilities were counted.

Count the distinct precipitation-probability integers in the stored
Philadelphia NWS forecast periods in `forecast-phi-48-75.json`. The hourly
body is not used. The value is `probabilityOfPrecipitation.value` as
stored. A missing object is skipped as `missing probability`. A present
object with a null value is skipped as `null probability`. A value counts
when it is an integer. Any other value is skipped and named. Record the
count of periods, the count of distinct integers, and the integers in
ascending order. Do not divide a value by 100. Do not call a value a
market probability. Do not invent a missing integer. Do not compare an
integer to `0.40` or to `2°F`. Do not align a period to the CLI decision
clock. Do not trade. Do not score a holdout. Do not promote. No live
order. The CLI coverage row for NWS forecast stays "no stored value". Do
not change `2°F` or `0.40`.

## Result

14 periods were read. 0 values were missing or null. 6 integers are
distinct, in ascending order: 0, 1, 4, 5, 60, 66. The hourly body was not
used. A value was not divided by 100 and was not called a market
probability. A missing integer was not invented. The count was not
compared to 0.40 or to 2°F and was not aligned to the CLI decision clock.
The CLI coverage row for NWS forecast still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 443 passed.
