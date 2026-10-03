---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.209 checkpoint

Date: 2026-10-03. Phase 4.209 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.209.md`.

## Rule

This comparison rule was written before the differences were computed.

Compare the stored Philadelphia GFS previous-day series with the stored
Philadelphia ECMWF previous-day series. The GFS series is
`temperature_2m_previous_day1` in `gfs-seamless-previous-day1.json`. The
ECMWF series is `temperature_2m_previous_day1` in
`ecmwf-ifs-previous-day1.json`. At each timestamp present in both series,
the difference is the GFS temperature minus the ECMWF temperature. A
timestamp missing from either series, or an hour with a null, is skipped
and named. Do not snap the grid points together. Do not align the
difference to the CLI decision clock. Do not add a threshold. Do not trade.
Do not score a holdout. Do not promote. No live order. The CLI coverage row
for forecast changes/revisions stays "no stored value". Do not change
`2°F` or `0.40`.

## Result

24 hours are eligible. 0 hours are skipped. The first hour is
2026-10-02T00:00 and the difference is -1.8°F. The last hour is
2026-10-02T23:00 and the difference is 1.9°F. The stored GFS grid is
39.863625, -75.22328. The stored ECMWF grid is 39.89455, -75.18826. They
were not snapped together. Hours of -3.5°F and 2.1°F are in the record.
They are not a new threshold. The stored GFS previous-day series equals
the stored HRRR previous-day series at every hour, so these differences
are the negation of the stored ECMWF-minus-HRRR previous-day differences.
That fact is not a reason to drop a model. The differences were not
aligned to the CLI decision clock. The CLI coverage row for forecast
changes/revisions still says no stored value. Nothing was traded. `2°F`
and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 347 passed.
