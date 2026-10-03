---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.208 checkpoint

Date: 2026-10-03. Phase 4.208 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.208.md`.

## Rule

This comparison rule was written before the differences were computed.

Compare the stored Philadelphia GFS ensemble control series with the stored
Philadelphia ECMWF forecast series. The ensemble series is `temperature_2m`
in `gfs-ensemble.json`. The ECMWF series is `temperature_2m` in
`ecmwf-ifs.json`. At each timestamp present in both series, the difference
is the ensemble control minus the ECMWF temperature. A timestamp missing
from either series, or an hour with a null, is skipped and named. Do not
snap the grid points together. Do not align the difference to the CLI
decision clock. Do not add a threshold. Do not trade. Do not score a
holdout. Do not promote. No live order. The CLI coverage row for forecast
changes/revisions stays "no stored value". Do not change `2°F` or `0.40`.

## Result

24 hours are eligible. 0 hours are skipped. The first hour is
2026-10-03T00:00 and the difference is 0.6°F. The last hour is
2026-10-03T23:00 and the difference is 0.0°F. The stored ensemble grid is
39.75, -75.25. The stored ECMWF grid is 39.89455, -75.18826. They were
not snapped together. Hours of 2.1°F, 3.1°F, 2.9°F, 3.2°F, and 2.6°F are
in the record. They are not a new threshold. The differences were not
aligned to the CLI decision clock. The CLI coverage row for forecast
changes/revisions still says no stored value. Nothing was traded. `2°F`
and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 345 passed.
