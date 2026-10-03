---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.283 checkpoint

Date: 2026-10-03. Phase 4.283 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.283.md`.

## Rule

This record rule was written before the stored points geometry type was
read.

Record the stored `geometry.type` value in the Philadelphia NWS points body
`points-39.87--75.23.json`. The forecast body and the hourly body are not
used. Coordinates are not read. A missing geometry is skipped as `missing
geometry`. A missing or empty type is skipped as `missing geometry type`.
Any other type value is skipped as `geometry type is not a string`. The
coordinates key is skipped and not read. Do not snap the polygon to the
HRRR/ECMWF/ensemble grid. Do not rewrite the string. Do not invent a
missing string. Do not compare it to `0.40` or to `2°F`. Do not trade. Do
not score a holdout. Do not promote. No live order. The CLI coverage row
for NWS forecast stays "no stored value". Do not change `2°F` or `0.40`.

## Result

Pending. The value has not been read.

## Tests

Pending.
