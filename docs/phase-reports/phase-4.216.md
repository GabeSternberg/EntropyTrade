---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.216 checkpoint

Date: 2026-10-03. Phase 4.216 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.216.md`.

## Rule

This count rule was written before the distinct changes were counted.

Count the distinct stored Philadelphia candlestick price changes. A change
is the close minus the previous close when both `price.close_dollars`
fields are decimal strings. The previous close is the immediately previous
candlestick in the same file. Record how many distinct change values
occur, and name the smallest and the largest in numeric order. A missing
change is not filled in. Do not compare a change to 0.40. Do not treat the
count as a threshold. Do not align a change to 15:00 UTC. Do not trade.
Do not score a holdout. Do not promote. No live order. The CLI coverage
row for market price change stays "no stored value". Do not change `2°F`
or `0.40`.

## Result

3372 changes have both a decimal close and a decimal immediately previous
close in the same file. 94 values are distinct. 2157 changes were missing
and were not filled in. The first skip is
`KXHIGHPHIL-26AUG23-B82.5#0: no previous close`. The last skip is
`KXHIGHPHIL-26SEP30-T83#24: missing price close`. In numeric order the
smallest change is -0.9700 and the largest is 0.9800. A stored change of
-0.4000 is one of the 94 values. It was not compared with the 0.40 price
threshold and it is not a new threshold. Changes were not aligned to
15:00 UTC. The CLI coverage row for market price change still says no
stored value. Nothing was traded. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 361 passed.
