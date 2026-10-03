---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.218 checkpoint

Date: 2026-10-03. Phase 4.218 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.218.md`.

## Rule

This count rule was written before the distinct asks were counted.

Count the distinct stored Philadelphia candlestick ask closes. An ask
counts only when `yes_ask.close_dollars` is a decimal string, including
`0.0000`. Record how many distinct ask values occur, and name the
smallest and the largest in numeric order. A missing ask is not filled
in. Do not compare an ask to 0.40. Do not treat a candle as an order book.
Do not treat the count as a threshold. Do not align an ask to 15:00 UTC.
Do not trade. Do not score a holdout. Do not promote. No live order. The
CLI coverage row for Kalshi ask stays "no stored value". Do not change
`2°F` or `0.40`.

## Result

5529 ask closes are decimal strings. 100 values are distinct. 0 asks were
missing. In numeric order the smallest is 0.0100 and the largest is
1.0000. 0.0000 is absent and was not invented. A stored ask of 0.4000 is
one of the 100 values. It was not compared with the 0.40 price threshold
and it is not a new threshold. A candle is not an order book. Asks were
not aligned to 15:00 UTC. The CLI coverage row for Kalshi ask still says
no stored value. Nothing was traded. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 365 passed.
