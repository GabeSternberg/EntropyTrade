---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.185 checkpoint

Date: 2026-10-03. Phase 4.185 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.185.md`.

## Rule

This record rule was written before the hours were counted.

For each stored Philadelphia CLI label, the decision time is 15:00 UTC on
the label's valid day. That is the existing decision clock. Hours until
resolution are the hours from that decision time until the label's stored
`available_at`. A negative value is recorded. Do not drop it. Do not
invent an `available_at`. Do not add a threshold. Do not trade. Do not
score a holdout. Do not promote. No live order. The CLI coverage row for
hours until resolution stays "no stored value".

## Result

40 stored Philadelphia labels have an `available_at`. None of the spans
are negative. The first span, on 2026-08-23, is
14.91666666666666666666666667 hours. The last span, on 2026-10-01, is
15.36666666666666666666666667 hours. No `available_at` was invented. The
spans were not used as a threshold. The CLI coverage row for hours until
resolution still says no stored value. Nothing was traded. `2°F` and
`0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 299 passed.
