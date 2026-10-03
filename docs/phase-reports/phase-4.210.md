---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.210 checkpoint

Date: 2026-10-03. Phase 4.210 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.210.md`.

## Rule

This comparison rule was written before the differences were computed.

Compare the stored Philadelphia unrounded GFS ensemble mean with the stored
Philadelphia HRRR forecast. The mean is the existing unrounded sum of the
31 `temperature_2m` series in `gfs-ensemble.json`, divided by 31. The HRRR
series is `temperature_2m` in `ncep-hrrr-conus.json`. At each timestamp
present in both series, the difference is that mean minus the HRRR
temperature. A timestamp missing from either series, or an hour with a
null, is skipped and named. Do not replace the mean formula. Do not snap
the grid points together. Do not align the difference to the CLI decision
clock. Do not add a threshold. Do not trade. Do not score a holdout. Do
not promote. No live order. The CLI coverage row for forecast mean stays
"no stored value". Do not change `2°F` or `0.40`.

## Result

24 hours are eligible. 0 hours are skipped. The first hour is
2026-10-03T00:00 and the unrounded difference is
0.07741935483870967741935484°F. The last hour is 2026-10-03T23:00 and the
unrounded difference is 0.91290322580645161290322581°F. The stored
ensemble grid is 39.75, -75.25. The stored HRRR grid is 39.863625,
-75.22328. They were not snapped together. The mean is still the
unrounded sum of all 31 series divided by 31. Differences were not
rounded. Hours above 2°F are in the record and are not a new threshold.
The differences were not aligned to the CLI decision clock. The CLI
coverage row for forecast mean still says no stored value. Nothing was
traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 349 passed.
