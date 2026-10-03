---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.183 checkpoint

Date: 2026-10-03. Phase 4.183 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.183.md`.

## Rule

This record rule was written before the errors were counted.

For each calendar date in the stored Philadelphia observed `temperature_2m`
archive and the stored `temperature_2m_previous_day1` previous-runs body,
the error is the observed daily maximum minus the previous-day daily
maximum. A daily maximum is the maximum hourly value on that date. A date
is eligible only when both series contain the same timestamps for that
date and none of those hours is null. Any other date is skipped and named.
The two response grid points are not snapped together. Do not add a
threshold. Do not trade. Do not score a holdout. Do not promote. No live
order. The CLI coverage row for previous day's errors stays "no stored
value".

## Result

39 dates are eligible. 2026-08-23 is skipped because it is missing from
the observed series. 2026-10-02 is skipped because it is missing from the
previous-day series. No eligible date had differing timestamps or a null
hour. The first eligible error is -2.1°F on 2026-08-24. The last is 2.4°F
on 2026-10-01. The observed grid point is 39.89455, -75.18826. The
previous-runs grid point is 39.863625, -75.22328. They were not snapped
together. The errors were not used as a threshold. The CLI coverage row
for previous day's errors still says no stored value. Nothing was traded.
`2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 295 passed.
