---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.195 checkpoint

Date: 2026-10-03. Phase 4.195 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.195.md`.

## Rule

This count rule was written before the files were counted.

Count bid and ask closes on the already stored Philadelphia CLI-window
candlesticks. A file under `data/public/kalshi-public/cli-window/candles/`
counts only when it is one JSON object with a `candlesticks` list. A
candlestick has a bid when `yes_bid.close_dollars` is a string, including
`0.0000`. A candlestick has an ask when `yes_ask.close_dollars` is a
string, including `0.0000`. A missing field is named, not filled in. Do
not treat a candle as an order book. Do not align a candle to 15:00 UTC.
Do not add a threshold. Do not trade. Do not score a holdout. Do not
promote. No live order. The CLI coverage rows for Kalshi bid and Kalshi
ask stay "no stored value".

## Result

230 candlestick files are stored. They contain 5529 candlesticks. All 5529
have a bid close string and an ask close string. 0 fields were missing.
The string `0.0000` is included. A candle was not treated as an order book
and was not aligned to 15:00 UTC. The CLI coverage rows for Kalshi bid and
Kalshi ask still say no stored value. Nothing was traded. `2°F` and `0.40`
were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 319 passed.
