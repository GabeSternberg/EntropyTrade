---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.143 checkpoint

Date: 2026-10-02. Phase 4.143 is off-plan work. No order was sent. Nothing
was promoted. The four bracket rules were not changed. `2°F` and `0.40`
were not changed after a score.

A copy of this file is in the repository at `docs/phase-reports/phase-4.143.md`.

## Rule

This is the same rule as Phase 4.142. It was not changed before the Chicago
score.

The 03:00 vs 15:00 vintages are not available, because `run` is rejected.
The two vintages are the API fields for the same valid hour,
`temperature_2m_previous_day1` (later) and `temperature_2m_previous_day2`
(earlier), which are about one day apart. They are requested from the
previous-runs endpoint with no `run` parameter. If the payload has no issue
time, `available_at` is 00:00 UTC on the valid day for the later field and
00:00 UTC the day before for the earlier field. That clock is a rule.

Revision = later_max - earlier_max, using hourly values whose vintage is
available at or before 15:00 UTC on the valid day. If either field is
missing, no trade. `forecast_revision_up` fires only when revision >= 2°F
and the later max is inside 80–81 inclusive. Optimistic may assume one YES
at a B80.5 print at or before 15:00 UTC with price <= 0.40. Base and
conservative do not treat a print as a fill. Fidelity is `trade-print`. A
print is not a guaranteed fill. The fee coefficient stays unset. Train, then
validation. The holdout is not scored. Nothing is promoted. No third city.

## Result

`temperature_2m_previous_day2` returned HTTP 200 with
`temperature_2m_previous_day1` for the stored Chicago point. The payload has
no issue time. `available_at` is the same rule. Forty complete days are
stored for each field. No hour was invented. `run` was not sent.

Chicago train is 20 days, validation 10, holdout 10. The holdout was not
scored. `forecast_revision_up` fired 0 times on train and 0 times on
validation, so there are 0 optimistic fills. Train optimistic equity is
100.000000. Validation optimistic equity is 100.000000. Base equity is
100.000000 with 0 fills. Conservative equity is 100.000000 with 0 fills.
Train had 7 days with a revision of at least 2°F and 2 days whose later max
was inside 80–81. Those sets did not overlap. Validation had 3 days with a
revision of at least 2°F and no later max inside 80–81. `2°F` and `0.40`
were not changed. Nothing was promoted. No third city was scored.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 245 passed.
