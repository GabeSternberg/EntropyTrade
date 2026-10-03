---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.215 checkpoint

Date: 2026-10-03. Phase 4.215 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.215.md`.

## Rule

This count rule was written before the distinct closes were counted.

Count the distinct stored Philadelphia candlestick price closes. A close
counts only when `price.close_dollars` is a decimal string. Record how
many distinct close values occur, and name the smallest and the largest
in numeric order. A missing close is not filled in and is not called a
probability. Do not compare a close to 0.40. Do not treat the count as a
threshold. Do not align a close to 15:00 UTC. Do not trade. Do not score
a holdout. Do not promote. No live order. The CLI coverage row for market
probability stays "no stored value". Do not change `2°F` or `0.40`.

## Result

4064 closes are decimal strings. 98 values are distinct. 1465 closes
were missing and were not filled in. The first missing close is
`KXHIGHPHIL-26AUG23-B82.5#1`. The last missing close is
`KXHIGHPHIL-26SEP30-T83#24`. In numeric order the smallest close is
0.0100 and the largest is 0.9900. 0.8400 is absent and was not invented.
A stored close of 0.4000 is one of the 98 values. It was not compared
with the 0.40 price threshold and it is not a new threshold. A close was
not called a probability. Closes were not aligned to 15:00 UTC. The CLI
coverage row for market probability still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 359 passed.
