---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.222 checkpoint

Date: 2026-10-03. Phase 4.222 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.222.md`.

## Rule

This count rule was written before the one-dollar asks were counted.

Count stored Philadelphia candlesticks whose ask close is exactly 1.0000.
An ask counts when `yes_ask.close_dollars` parses as the decimal 1. Record
the count and the first and last ticker-hour that has that ask. Do not
treat 1.0000 as a settlement. Do not call it a probability. Do not compare
it to 0.40. Do not treat a candle as an order book. Do not align an ask to
15:00 UTC. Do not trade. Do not score a holdout. Do not promote. No live
order. The CLI coverage row for Kalshi ask stays "no stored value". Do not
change `2°F` or `0.40`.

## Result

5529 ask closes are decimal strings. 143 of them are exactly 1. The first
is `KXHIGHPHIL-26AUG23-B84.5#22`. The last is
`KXHIGHPHIL-26SEP30-B76.5#24`. 1.0000 is not a settlement and is not a
probability. A candle is not an order book. The count was not compared to
0.40 and was not used as a threshold. Asks were not aligned to 15:00 UTC.
The CLI coverage row for Kalshi ask still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 373 passed.
