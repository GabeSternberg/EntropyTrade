---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.189 checkpoint

Date: 2026-10-03. Phase 4.189 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.189.md`.

## Rule

This record rule was written before the means were computed.

At each stored hour of the Philadelphia GFS ensemble, the forecast mean is
the unrounded arithmetic mean of the 31 temperature series. Do not drop a
series. Do not round the mean to a trading tolerance. Do not align it to
the CLI decision clock. Do not add a threshold. Do not trade. Do not score
a holdout. Do not promote. No live order. The CLI coverage row for
forecast mean stays "no stored value".

## Result

24 hours have an unrounded mean. Each mean uses all 31 temperature series.
No series was dropped. The first hour's mean is
73.27741935483870967741935484 °F. The last hour's mean is
64.31290322580645161290322581 °F. The means were not rounded and were not
aligned to the CLI decision clock. The CLI coverage row for forecast mean
still says no stored value. Nothing was traded. `2°F` and `0.40` were not
changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 307 passed.
