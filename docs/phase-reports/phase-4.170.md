---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.170 checkpoint

Date: 2026-10-03. Phase 4.170 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.170.md`.

## Rule

This rule was written before the Philadelphia score. It does not retune a
number that was already scored.

`forecast_revision_down` uses the same vintages as `forecast_revision_bracket`.
Later is `temperature_2m_previous_day1`. Earlier is
`temperature_2m_previous_day2`. Revision = later_max - earlier_max. It
fires only when revision <= -2°F. `2°F` is the existing revision minimum,
with the sign flipped. It is not a new threshold. The 80-81 gate is not
applied.

The market is the stored KXHIGHPHIL between-contract whose floor and cap
contain later_max under the existing inclusive between rule. If that
contract is not in the stored tape, no trade. A neighbor is not
substituted. If two stored between-contracts contain the same later max,
no trade.

Optimistic may assume one YES at a print at or before 15:00 UTC with price
<= 0.40. Base and conservative do not treat a print as a fill. Fidelity is
`trade-print`. A print is not a guaranteed fill. The fee coefficient stays
unset. Train, then validation. The holdout is not scored. Nothing is
promoted. This is one hypothesis. No new pull. This module does not open
a socket.

## Result

Philadelphia train is 20 days, validation 10, holdout 10. The holdout was
not scored. `forecast_revision_down` fired 13 times on train and 5 times on
validation. Train claim hits are 0. Train optimistic fills are 3 and train
optimistic equity is 99.760000. Validation claim hits are 0. Validation
optimistic fills are 1 and validation optimistic equity is 99.860000. Base
equity is 100.000000 with 0 fills. Conservative equity is 100.000000 with
0 fills. The upward rule is unchanged: train still fires once and train
optimistic equity stays 99.770000. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 273 passed.
