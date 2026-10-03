---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.284 checkpoint

Date: 2026-10-03. Phase 4.284 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.284.md`.

## Rule

This record rule was written before the stored points coordinates were
counted.

Count the stored coordinate numbers in the Philadelphia NWS points body
`points-39.87--75.23.json`. The geometry type was already recorded as
`Point`. The forecast body and the hourly body are not used. One position
counts when `coordinates` is a non-empty list of integers or JSON numbers.
A boolean is not a number. The count is the number of values in that list.
A missing coordinates value, or a value that is not a list of numbers, is
skipped as `missing coordinates`. Do not record a longitude. Do not record
a latitude. Do not snap the point to the HRRR/ECMWF/ensemble grid. Do not
compare the count to `0.40` or to `2°F`. Do not trade. Do not score a
holdout. Do not promote. No live order. The CLI coverage row for NWS
forecast stays "no stored value". Do not change `2°F` or `0.40`. The note
keeps the sentence shape "{count} numbers were stored in one position."
when a position is stored.

## Result

1 position was stored and 2 numbers were in that position. A longitude was
not recorded and a latitude was not recorded. The forecast body and the
hourly body were not used. The point was not snapped to the
HRRR/ECMWF/ensemble grid. The count was not compared to 0.40 or to 2°F.
The CLI coverage row for NWS forecast still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 497 passed.
