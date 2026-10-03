---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.197 checkpoint

Date: 2026-10-03. Phase 4.197 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.197.md`.

## Rule

This spread rule was written before the spreads were computed.

Record the spread on the already stored Philadelphia candlesticks. When
both `yes_ask.close_dollars` and `yes_bid.close_dollars` are decimal
strings, the spread is the ask close minus the bid close. A string that
is not a decimal is named and skipped. A zero spread is kept. Do not
compare a spread to `0.40`. Do not treat a candle as an order book. Do
not align a candle to 15:00 UTC. Do not add a threshold. Do not trade.
Do not score a holdout. Do not promote. No live order. The CLI coverage
row for spread stays "no stored value".

## Result

5529 candlesticks have a decimal bid close and a decimal ask close. 0
spreads are zero and 0 are negative. 0 closes were skipped. The first
spread, `KXHIGHPHIL-26AUG23-B82.5#0`, is 0.0300. The last spread,
`KXHIGHPHIL-26SEP30-T83#24`, is 0.0100. No spread was compared to `0.40`.
A candle was not treated as an order book and was not aligned to 15:00
UTC. The CLI coverage row for spread still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 323 passed.
