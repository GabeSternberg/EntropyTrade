---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.236 checkpoint

Date: 2026-10-03. Phase 4.236 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.236.md`.

## Rule

This count rule was written before the distinct wind directions were
counted.

Count the distinct wind directions in the stored Philadelphia NWS hourly
forecast. A direction counts when `windDirection` is a non-empty string.
A missing or empty direction is skipped and named. Record the count of
periods, the count of distinct values, and the values in alphabetical
order. Do not convert a direction into degrees. Do not invent a missing
direction. Do not compare a direction to `2°F` or to `0.40`. Do not align
a period to the CLI decision clock. Do not trade. Do not score a holdout.
Do not promote. No live order. The CLI coverage row for wind stays "no
stored value". Do not change `2°F` or `0.40`.

## Result

156 periods were read. 52 directions were missing. 7 values are distinct.
In alphabetical order they are E, N, NE, NW, S, SW, and W. The first
missing direction is 2026-10-04T22:00:00-04:00 and the last is
2026-10-09T06:00:00-04:00. Missing directions were not invented and were
not converted into degrees. The count was not compared to 0.40 and was
not aligned to the CLI decision clock. The CLI coverage row for wind
still says no stored value. Nothing was traded. `2°F` and `0.40` were
not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 401 passed.
