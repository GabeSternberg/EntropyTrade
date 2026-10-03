---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.190 checkpoint

Date: 2026-10-03. Phase 4.190 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.190.md`.

## Rule

This record rule was written before the ranges were computed.

At each stored hour of the Philadelphia GFS ensemble, the forecast
dispersion is the maximum of the 31 temperatures minus the minimum. Do
not drop a series. Do not use a standard deviation. Do not align it to
the CLI decision clock. Do not add a threshold. Do not trade. Do not
score a holdout. Do not promote. No live order. The CLI coverage row for
forecast dispersion stays "no stored value".

## Result

24 hours have a range. Each range is the maximum minus the minimum of all
31 temperature series. No series was dropped. A standard deviation was not
used. The first hour's range is 1.0°F. The last hour's range is 4.3°F.
The ranges were not aligned to the CLI decision clock. The CLI coverage
row for forecast dispersion still says no stored value. Nothing was
traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 309 passed.
