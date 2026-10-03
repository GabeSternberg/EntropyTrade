---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.198 checkpoint

Date: 2026-10-03. Phase 4.198 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.198.md`.

## Rule

This count rule was written before the files were counted.

Count `price.close_dollars` on the already stored Philadelphia
candlesticks. A candlestick has a price close when `price.close_dollars`
is a decimal string. A missing close, or a string that is not a decimal,
is named and not filled in. Do not divide the close by anything. Do not
call a transformed number a probability. Do not compare a close to
`0.40`. Do not align a candle to 15:00 UTC. Do not add a threshold. Do
not trade. Do not score a holdout. Do not promote. No live order. The CLI
coverage row for market probability stays "no stored value".

## Result

230 files and 5529 candlesticks are stored. 4064 have a decimal
`price.close_dollars`. 1465 closes are missing and were not filled in.
The first named skip is `KXHIGHPHIL-26AUG23-B82.5#1`. A close was not
divided and was not called a probability. No close was compared to
`0.40`. Nothing was aligned to 15:00 UTC. The CLI coverage row for
market probability still says no stored value. Nothing was traded.
`2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 325 passed.
