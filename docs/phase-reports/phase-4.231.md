---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.231 checkpoint

Date: 2026-10-03. Phase 4.231 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.231.md`.

## Rule

This difference rule was written before the NWS-forecast-minus-HRRR
differences were computed.

Compare the stored Philadelphia NWS forecast periods in
`forecast-phi-48-75.json` with the stored Philadelphia HRRR forecast at
equal UTC instants. The hourly body is not used. An NWS period start is
read with its offset and converted to UTC. The HRRR series is
`temperature_2m` in `ncep-hrrr-conus.json`. When that UTC instant equals
an HRRR timestamp, the difference is the NWS temperature minus the HRRR
temperature. A period that does not land on a stored HRRR hour, or an
hour with a null, is skipped and named. Do not align either series to
the CLI decision clock. Do not snap grid points. Do not add a threshold.
Do not trade. Do not score a holdout. Do not promote. No live order. The
CLI coverage row for NWS forecast stays "no stored value". Do not change
`2°F` or `0.40`.

## Result

2 hours are eligible. 12 periods are skipped. Every skip is named "does
not land on a stored HRRR hour". The first skip is
2026-10-02T19:00:00-04:00 and the last skip is 2026-10-09T06:00:00-04:00.
The first eligible hour is 2026-10-03T10:00, from the period that starts
at 2026-10-03T06:00:00-04:00, and the difference is 13.4°F. The last
eligible hour is 2026-10-03T22:00, from the period that starts at
2026-10-03T18:00:00-04:00, and the difference is -6.9°F. Those
differences are not a new threshold. The period temperature was not
moved to a different hour after those values were seen. The hourly body
was not used. The stored HRRR grid is 39.863625, -75.22328 and was not
rewritten. The NWS polygon was not snapped to that grid. The differences
were not aligned to the CLI decision clock. The CLI coverage row for NWS
forecast still says no stored value. Nothing was traded. `2°F` and
`0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 391 passed.
