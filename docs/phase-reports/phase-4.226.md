---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.226 checkpoint

Date: 2026-10-03. Phase 4.226 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.226.md`.

## Rule

This difference rule was written before the NWS-minus-ECMWF differences
were computed.

Compare the stored Philadelphia NWS hourly forecast with the stored
Philadelphia ECMWF forecast at equal UTC instants. An NWS period start is
read with its offset and converted to UTC. The ECMWF series is
`temperature_2m` in `ecmwf-ifs.json`. When that UTC instant equals an
ECMWF timestamp, the difference is the NWS temperature minus the ECMWF
temperature. A period that does not land on a stored ECMWF hour, or an
hour with a null, is skipped and named. Do not align either series to
the CLI decision clock. Do not snap grid points. Do not add a threshold.
Do not trade. Do not score a holdout. Do not promote. No live order. The
CLI coverage row for NWS forecast stays "no stored value". Do not change
`2°F` or `0.40`.

## Result

17 hours are eligible. 139 periods are skipped. Every skip is named
"does not land on a stored ECMWF hour". The first skip is
2026-10-03T20:00:00-04:00 and the last skip is 2026-10-09T14:00:00-04:00.
The first eligible hour is 2026-10-03T07:00, from the period that starts
at 2026-10-03T03:00:00-04:00, and the difference is 1.4°F. The last
eligible hour is 2026-10-03T23:00 and the difference is 3.4°F. Hours of
3.2°F, 3.4°F, and 3.6°F are in the record. They are not a new threshold.
The stored ECMWF grid is 39.89455, -75.18826 and was not rewritten. The
NWS polygon was not snapped to that grid. The differences were not
aligned to the CLI decision clock. The CLI coverage row for NWS forecast
still says no stored value. Nothing was traded. `2°F` and `0.40` were
not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 381 passed.
