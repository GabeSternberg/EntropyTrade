---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.147 checkpoint

Date: 2026-10-03. Phase 4.147 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.147.md`.

## Rule

This rule was written before the Austin score. It is the same frozen rule
as Phase 4.144. The thresholds were not changed.

Later is `temperature_2m_previous_day1`. Earlier is
`temperature_2m_previous_day2`. The request uses the stored Austin
coordinates and does not send `run`. `previous-runs.json` is not overwritten.
If the payload has no issue time, `available_at` stays the rule clock: 00:00
UTC on the valid day for the later field, and 00:00 UTC the day before for
the earlier field. Revision = later_max - earlier_max. If either field is
missing, no trade.

`forecast_revision_bracket` fires only when revision >= 2°F. It does not
also require the later max to sit inside 80–81. Austin market rows do not
carry `floor_strike` or `cap_strike`. A stored ticker ending in `-B80.5`
with HTTP 200 is the registered between-contract, floor 80 and cap 81. A
row with HTTP 404 is not a contract. Every stored Austin row is HTTP 404, so
no stored between-contract contains a later max and there is no trade.
Another strike's floor is not invented. A neighbor is not substituted. The
stored print table is empty. If two stored between-contracts contain the
same later max, no trade.

Optimistic may assume one YES at a print on that contract at or before
15:00 UTC with price <= 0.40. Base and conservative do not treat a print as
a fill. Fidelity is `trade-print`. A print is not a guaranteed fill. The fee
coefficient stays unset. Train, then validation. The holdout is not scored.
Nothing is promoted. This is the same hypothesis, scored on Austin.

## Result

`temperature_2m_previous_day2` returned HTTP 200 with
`temperature_2m_previous_day1`. The payload has no issue time. Forty
complete days are stored for each field. No hour was invented. `run` was
not sent. `previous-runs.json` was not overwritten.

Austin train is 20 days, validation 10, holdout 10. The holdout was not
scored. `forecast_revision_bracket` fired once on train and not on
validation. Every stored Austin market is HTTP 404, so that fire had no
between-contract and no fill. Train optimistic equity is 100.000000.
Validation optimistic equity is 100.000000. Base equity is 100.000000 with
0 fills. Conservative equity is 100.000000 with 0 fills. `2°F` and `0.40`
were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 250 passed.
