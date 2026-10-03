---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.201 checkpoint

Date: 2026-10-03. Phase 4.201 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.201.md`.

## Rule

This imbalance rule was written before the books were counted.

Record order-book imbalance only when a stored CLI-window order book has
at least one yes level and one no level. A level is a stored price-and-size
pair whose size is greater than zero. When both sides have such a level,
the imbalance is the yes size minus the no size, divided by the yes size
plus the no size. The sizes are the sums of the level quantities. Do not
round that quotient. An empty side is named. A call with no stored body is
named. Do not invent a level. Do not compute a ratio from an empty book.
Do not trade. Do not score a holdout. Do not promote. No live order. The
CLI coverage row for order-book imbalance stays "no stored value".

## Result

240 order-book calls are stored. 0 have both a yes level and a no level, so
no imbalance was computed. 1 stored body has two empty sides. 239 calls
have no stored body and were not filled in. No level was invented. The CLI
coverage row for order-book imbalance still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 331 passed.
