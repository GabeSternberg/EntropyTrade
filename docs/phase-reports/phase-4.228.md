---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.228 checkpoint

Date: 2026-10-03. Phase 4.228 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.228.md`.

## Rule

This difference rule was written before the NWS-minus-mean differences
were computed.

Compare the stored Philadelphia NWS hourly forecast with the stored
unrounded Philadelphia ensemble mean at equal UTC instants. An NWS period
start is read with its offset and converted to UTC. The mean is the
existing unrounded sum of all 31 temperature series divided by 31. When
that UTC instant equals a mean timestamp, the difference is the NWS
temperature minus the mean. A period that does not land on a stored mean
hour, or an hour with a null, is skipped and named. Do not replace the
mean formula. Do not align either series to the CLI decision clock. Do
not snap grid points. Do not add a threshold. Do not trade. Do not score
a holdout. Do not promote. No live order. The CLI coverage row for NWS
forecast stays "no stored value". Do not change `2°F` or `0.40`.

## Result

17 hours are eligible. 139 periods are skipped. Every skip is named
"does not land on a stored mean hour". The first skip is
2026-10-03T20:00:00-04:00 and the last skip is 2026-10-09T14:00:00-04:00.
The first eligible hour is 2026-10-03T07:00, from the period that starts
at 2026-10-03T03:00:00-04:00, and the unrounded difference is
2.02580645161290322580645161°F. The last eligible hour is
2026-10-03T23:00 and the unrounded difference is
3.68709677419354838709677419°F. The differences were not rounded. Hours
above 2°F are not a new threshold. The mean still uses all 31 series.
The stored ensemble grid is 39.75, -75.25 and was not rewritten. The NWS
polygon was not snapped to that grid. The differences were not aligned
to the CLI decision clock. The CLI coverage row for NWS forecast still
says no stored value. Nothing was traded. `2°F` and `0.40` were not
changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 385 passed.
