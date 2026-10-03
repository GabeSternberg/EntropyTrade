---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.213 checkpoint

Date: 2026-10-03. Phase 4.213 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.213.md`.

## Rule

This rank rule was written before the ranks were counted.

Rank the stored Philadelphia GFS ensemble control inside the stored
31-member temperature sample. At each hour, the rank is 1 plus the number
of the 31 `temperature_2m` series in `gfs-ensemble.json` that are strictly
colder than the control `temperature_2m`. A series equal to the control
does not increase the rank. A null hour is skipped and named. Do not
divide the rank. Do not call it a probability. Do not align it to the CLI
decision clock. Do not add a threshold. Do not trade. Do not score a
holdout. Do not promote. No live order. The CLI coverage row for GFS
ensemble stays "no stored value". Do not change `2°F` or `0.40`.

## Result

24 hours are eligible. 0 hours are skipped. The first hour is
2026-10-03T00:00 and the rank is 10. The last hour is 2026-10-03T23:00
and the rank is 16. The rank is an integer. It was not divided and it is
not a probability. A tie does not increase it. The ranks were not aligned
to the CLI decision clock and were not used as a threshold. The CLI
coverage row for GFS ensemble still says no stored value. Nothing was
traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 355 passed.
