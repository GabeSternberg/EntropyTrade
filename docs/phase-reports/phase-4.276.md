---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.276 checkpoint

Date: 2026-10-03. Phase 4.276 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.276.md`.

## Rule

This record rule was written before the stored hourly elevation was read.

Record the stored `properties.elevation` value in the Philadelphia NWS
hourly body `forecast-hourly-phi-48-75.json`. The 14-period forecast body
is not used. A missing value is skipped as `missing elevation`. A
non-empty string is recorded as stored. An object records `value` when it
is an integer or a JSON number, using the unrounded decimal text, and
records `unitCode` when it is a non-empty string. A boolean is not a
number. A missing unit code is named `missing elevation unit`. A missing
number is named `missing elevation value`. A number that is not an
integer or a JSON number is named `elevation value is not a number`. Any
other shape is named `elevation is not a string or object`. Do not
convert the number. Do not invent a unit. Do not compare the number to
`0.40` or to `2°F`. Do not trade. Do not score a holdout. Do not promote.
No live order. The CLI coverage row for NWS forecast stays "no stored
value". Do not change `2°F` or `0.40`.

## Result

The stored number is `0.9144` and the stored unit is `wmoUnit:m`. It was
not a string. The 14-period forecast body was not used. The number was
not converted. A unit was not invented. It was not compared to 0.40 or to
2°F. The CLI coverage row for NWS forecast still says no stored value.
Nothing was traded. `2°F` and `0.40` were not changed. Nothing was
promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 481 passed.
