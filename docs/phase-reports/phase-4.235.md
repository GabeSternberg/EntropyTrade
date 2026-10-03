---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.235 checkpoint

Date: 2026-10-03. Phase 4.235 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.235.md`.

## Rule

This count rule was written before the distinct dew-point values were
counted.

Count the distinct dew-point values in the stored Philadelphia NWS hourly
forecast. The value is `dewpoint.value` when that field is a number. A
missing object or a null value is skipped and named. Record the count of
periods, the count of distinct values, the smallest, and the largest. Do
not convert the unit. Do not invent a missing dew point. Do not compare a
value to `2°F` or to `0.40`. Do not align a period to the CLI decision
clock. Do not trade. Do not score a holdout. Do not promote. No live
order. The CLI coverage row for dew point stays "no stored value". Do not
change `2°F` or `0.40`.

## Result

156 periods were read. 0 values were missing or null. 25 values are
distinct. The smallest is 3.888888888888889 and the largest is
17.22222222222222. Every stored unit code is `wmoUnit:degC`. The numbers
were not converted and were not rounded. The count was not compared to
0.40 or to 2°F and was not aligned to the CLI decision clock. The CLI
coverage row for dew point still says no stored value. Nothing was
traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 399 passed.
