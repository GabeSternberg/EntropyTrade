---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.279 checkpoint

Date: 2026-10-03. Phase 4.279 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.279.md`.

## Rule

This record rule was written before the stored hourly coordinate positions
were counted.

Count the stored coordinate positions in the Philadelphia NWS hourly body
`forecast-hourly-phi-48-75.json`. The 14-period forecast body is not used.
A position counts when it is a non-empty list of integers or JSON numbers.
A boolean is not a number. A ring counts when it is a list. A missing
geometry or a missing coordinates list is skipped as `missing
coordinates`. A ring that is not a list is counted as skipped. A position
that is not a list of numbers is counted as skipped. Do not record a
longitude. Do not record a latitude. Do not snap the polygon to the
HRRR/ECMWF/ensemble grid. Do not compare the count to `0.40` or to `2°F`.
Do not trade. Do not score a holdout. Do not promote. No live order. The
CLI coverage row for NWS forecast stays "no stored value". Do not change
`2°F` or `0.40`. The note keeps the sentence shape "{rings} rings were
stored." even if the ring count is 1.

## Result

Pending. The positions have not been counted.

## Tests

Pending.
