---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.221 checkpoint

Date: 2026-10-03. Phase 4.221 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.221.md`.

## Rule

This count rule was written before the zero bids were counted.

Count stored Philadelphia candlesticks whose bid close is exactly 0.0000.
A bid counts when `yes_bid.close_dollars` parses as the decimal 0. Record
the count and the first and last ticker-hour that has that bid. Do not
treat 0.0000 as a fill. Do not compare it to 0.40. Do not treat a candle
as an order book. Do not align a bid to 15:00 UTC. Do not trade. Do not
score a holdout. Do not promote. No live order. The CLI coverage row for
Kalshi bid stays "no stored value". Do not change `2°F` or `0.40`.

## Result

5529 bid closes are decimal strings. 1912 of them are exactly 0. The
first is `KXHIGHPHIL-26AUG23-B82.5#21`. The last is
`KXHIGHPHIL-26SEP30-T83#24`. 0.0000 is not a fill. A candle is not an
order book. The count was not compared to 0.40 and was not used as a
threshold. Bids were not aligned to 15:00 UTC. The CLI coverage row for
Kalshi bid still says no stored value. Nothing was traded. `2°F` and
`0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 371 passed.
