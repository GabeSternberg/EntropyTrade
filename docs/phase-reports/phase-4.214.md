---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.214 checkpoint

Date: 2026-10-03. Phase 4.214 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.214.md`.

## Rule

This count rule was written before the distinct spreads were counted.

Count the distinct stored Philadelphia candlestick spreads. A spread is the
already stored ask close minus the bid close. Record how many distinct
spread values occur, and name the smallest and the largest in numeric
order. Do not compare a spread to 0.40. Do not treat the count as a
threshold. Do not align a spread to 15:00 UTC. Do not trade. Do not score
a holdout. Do not promote. No live order. The CLI coverage row for spread
stays "no stored value". Do not change `2°F` or `0.40`.

## Result

5529 spreads are stored. 20 values are distinct. 0 closes were not
decimals. In numeric order the smallest is 0.0100 and the largest is
0.2100. 0.1800 is absent and was not invented. The count was not compared
to 0.40 and was not used as a threshold. Spreads were not aligned to
15:00 UTC. The CLI coverage row for spread still says no stored value.
Nothing was traded. `2°F` and `0.40` were not changed. Nothing was
promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 357 passed.
