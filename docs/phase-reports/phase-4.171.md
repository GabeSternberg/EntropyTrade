---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.171 checkpoint

Date: 2026-10-03. Phase 4.171 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.171.md`.

## Rule

This rule was written before the Chicago score. It is the same frozen rule
as Phase 4.170. The thresholds were not changed.

`forecast_revision_down` fires only when revision <= -2°F. Revision =
later_max - earlier_max. Later is `temperature_2m_previous_day1`. Earlier
is `temperature_2m_previous_day2`. Chicago market rows do not carry
`floor_strike` or `cap_strike`. A stored ticker ending in `-B80.5` with
HTTP 200 is the registered between-contract, floor 80 and cap 81. A row
with HTTP 404 is not a contract. If later_max is outside 80-81, no stored
Chicago between-contract contains it, so there is no trade. Another
strike's floor is not invented. A neighbor is not substituted. If two
stored between-contracts contain the same later max, no trade.

Optimistic may assume one YES at a print at or before 15:00 UTC with price
<= 0.40. Base and conservative do not treat a print as a fill. Train, then
validation. The holdout is not scored. Nothing is promoted. This is the
same hypothesis, scored on Chicago. No new pull. No socket.

## Result

Chicago train is 20 days, validation 10, holdout 10. The holdout was not
scored. `forecast_revision_down` fired 3 times on train and 4 times on
validation. Train claim hits are 1. Train optimistic fills are 1 and train
optimistic equity is 100.750000. Validation claim hits are 0. Validation
optimistic fills are 0 and validation optimistic equity is 100.000000.
Base equity is 100.000000 with 0 fills. Conservative equity is 100.000000
with 0 fills. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 274 passed.
