---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.237 checkpoint

Date: 2026-10-03. Phase 4.237 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.237.md`.

## Rule

This count rule was written before the distinct wind-speed strings were
counted.

Count the distinct wind-speed strings in the stored Philadelphia NWS
hourly forecast. A speed counts when `windSpeed` is a non-empty string. A
missing or empty speed is skipped and named. Record the count of periods,
the count of distinct strings, and the strings in alphabetical order. Do
not parse a string into a number. Do not convert miles per hour. Do not
invent a missing speed. Do not compare a speed to `2°F` or to `0.40`. Do
not align a period to the CLI decision clock. Do not trade. Do not score
a holdout. Do not promote. No live order. The CLI coverage row for wind
stays "no stored value". Do not change `2°F` or `0.40`.

## Result

156 periods were read. 0 speeds were missing. 3 strings are distinct. In
alphabetical order they are `0 mph`, `10 mph`, and `5 mph`. The strings
were not parsed into numbers and were not reordered numerically. The
count was not compared to 0.40 and was not aligned to the CLI decision
clock. The CLI coverage row for wind still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 403 passed.
