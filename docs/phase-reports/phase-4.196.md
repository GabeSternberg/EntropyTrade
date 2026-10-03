---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.196 checkpoint

Date: 2026-10-03. Phase 4.196 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.196.md`.

## Rule

This count rule was written before the files were counted.

Count `volume_fp` and `open_interest_fp` on the already stored Philadelphia
CLI-window candlesticks. A candlestick has volume when `volume_fp` is a
string, including `0.00`. A candlestick has open interest when
`open_interest_fp` is a string, including `0.00`. A missing field is named,
not filled in. Do not treat volume as a size at the touch. Do not align a
candle to 15:00 UTC. Do not add a threshold. Do not trade. Do not score a
holdout. Do not promote. No live order. The CLI coverage rows for trade
volume and open interest stay "no stored value".

## Result

230 candlestick files are stored. They contain 5529 candlesticks. All 5529
have a volume string and an open-interest string. 0 fields were missing.
The string `0.00` is included. Volume was not treated as a size at the
touch and was not aligned to 15:00 UTC. The CLI coverage rows for trade
volume and open interest still say no stored value. Nothing was traded.
`2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 321 passed.
