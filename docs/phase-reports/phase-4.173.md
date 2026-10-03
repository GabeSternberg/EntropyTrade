---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.173 checkpoint

Date: 2026-10-03. Phase 4.173 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.173.md`.

## Rule

This rule was written before the remaining cities were scored. It is the
same frozen rule as Phase 4.170. The thresholds were not changed.

`forecast_revision_down` fires only when revision <= -2°F. Revision =
later_max - earlier_max. Later is `temperature_2m_previous_day1`. Earlier
is `temperature_2m_previous_day2`. Named-city and scan-city market rows do
not carry `floor_strike` or `cap_strike`. A stored ticker ending in
`-B80.5` with HTTP 200 is the registered between-contract, floor 80 and
cap 81. A row with HTTP 404 is not a contract. If later_max is outside
80-81, no stored between-contract contains it, so there is no trade.
Another strike's floor is not invented. A neighbor is not substituted. If
two stored between-contracts contain the same later max, no trade.

The cities are the ones that already have both previous-day fields and
were not scored on this rule yet: Austin, Oklahoma City, Dallas, Denver,
Louisville, Boston, Minneapolis, San Francisco, San Diego, Newark,
Trenton, Los Angeles, Washington DC, Seattle, Las Vegas, and Atlanta. A
city without stored coordinates is not pulled.

Optimistic may assume one YES at a print at or before 15:00 UTC with price
<= 0.40. Base and conservative do not treat a print as a fill. Train, then
validation. The holdout is not scored. Nothing is promoted. This is the
same hypothesis. No new pull. No socket.

## Result

Every listed city produced a train fold and a validation fold. The holdout
was not scored. Oklahoma City is 19 train days, 9 validation days, and 11
holdout days. The other cities are 20, 10, and 10. Las Vegas fired 0 times.
The other cities fired on train or validation or both. Newark had 1 train
claim hit and 0 fills. Los Angeles train optimistic equity is 99.990000
with 1 fill. Trenton validation optimistic equity is 99.820000 with 1 fill.
Every other optimistic equity on these cities is 100.000000. Base and
conservative equity stay 100.000000 with 0 fills. `2°F` and `0.40` were
not changed. Nothing was promoted. `docs/research/kxhigh-scan.md` includes
the downward sentences.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 276 passed.
