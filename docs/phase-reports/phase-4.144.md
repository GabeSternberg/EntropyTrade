---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.144 checkpoint

Date: 2026-10-03. Phase 4.144 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed. The 80–81 gate on
`forecast_revision_up` was not used to pick a new threshold.

A copy of this file is in the repository at `docs/phase-reports/phase-4.144.md`.

## Rule

This rule was written before any score.

The vintages are the same as Phase 4.142. Later is
`temperature_2m_previous_day1`. Earlier is `temperature_2m_previous_day2`.
`run` is not sent. `available_at` stays the rule clock: 00:00 UTC on the
valid day for the later field, and 00:00 UTC the day before for the earlier
field. Revision = later_max - earlier_max. If either field is missing, no
trade.

`forecast_revision_bracket` fires only when revision >= 2°F. It does not
also require the later max to sit inside 80–81. The market is the stored
KXHIGHPHIL between-contract whose floor and cap contain later_max under the
existing inclusive between rule. If that contract is not in the stored tape,
no trade. A neighbor is not substituted. If two stored between-contracts
contain the same later max, no trade.

Optimistic may assume one YES at a print on that contract at or before
15:00 UTC with price <= 0.40. Base and conservative do not treat a print as
a fill. Fidelity is `trade-print`. A print is not a guaranteed fill. The fee
coefficient stays unset. Train, then validation. The holdout is not scored.
Nothing is promoted. This is one hypothesis.

## Result

Philadelphia train is 20 days, validation 10, holdout 10. The holdout was
not scored. `forecast_revision_bracket` fired once on train and not on
validation. That train day had one optimistic fill. Train optimistic equity
is 99.770000. Validation optimistic equity is 100.000000. Base equity is
100.000000 with 0 fills. Conservative equity is 100.000000 with 0 fills.
The claim did not hit: the label was outside the traded bracket. `2°F` and
`0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 247 passed.

