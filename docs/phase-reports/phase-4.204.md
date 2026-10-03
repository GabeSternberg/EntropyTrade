---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.204 checkpoint

Date: 2026-10-03. Phase 4.204 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.204.md`.

## Rule

This comparison rule was written before the differences were computed.

Compare the stored Philadelphia ECMWF previous-day series with the stored
Philadelphia HRRR previous-day series. At each timestamp present in both
series, the difference is the ECMWF temperature minus the HRRR temperature.
A timestamp missing from either series, or an hour with a null, is skipped
and named. Do not snap the grid points together. Do not align the
difference to the CLI decision clock. Do not add a threshold. Do not trade.
Do not score a holdout. Do not promote. No live order. The CLI coverage row
for forecast changes/revisions stays "no stored value".

## Result

24 hours are eligible. 0 hours are skipped. The first difference, at
2026-10-02T00:00, is 1.8°F. The last difference, at 2026-10-02T23:00, is
-1.9°F. ECMWF coordinates stay 39.89455, -75.18826. HRRR coordinates stay
39.863625, -75.22328. The grids were not snapped together. The differences
were not aligned to the CLI decision clock and were not used as a
threshold. The CLI coverage row for forecast changes/revisions still says
no stored value. Nothing was traded. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 337 passed.
