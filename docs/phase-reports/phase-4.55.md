---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.55 checkpoint

Date: 2026-10-02. Phase 4.55 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-4.55.md`.

## What was pulled

Unauthenticated `GET`s against `https://api.elections.kalshi.com/trade-api/v2`
at `2026-10-02T16:13:37.600569Z`. The window is every stored KXHIGHPHIL market
whose target date is 2026-08-23 through 2026-10-01. That is 240 markets and
66 strike suffixes, including B80.5 and 65 others.

Every current order book returned HTTP 200 and
`{"orderbook_fp":{"no_dollars":[],"yes_dollars":[]}}`. None of those 240
bodies has a price-and-size pair. One empty sample is stored. The other empty
bodies are recorded on the manifest with a null path. `book_from_body` still
returns nothing for an empty book.

230 hourly candlestick files are stored under
`data/public/kalshi-public/cli-window/candles/`. Bid and ask fields are open,
high, low, and close dollars. Volume and open interest are not a size at the
touch, and the loader refuses a quote that carries one. Candles are not
books. Failed calls: 0.

The 12 sized books from Phase 4.52 stay where they were. Their
`available_at` is `2026-10-02T15:48:09.632726Z`, which is after every stored
CLI label. This pull did not find a sized book before a CLI label.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 163 passed
(161 from Phase 4.54, plus 2 CLI-window tests).

## Files

- `backend/src/entropytrade/exchange/cli_window.py`
- `backend/tests/unit/test_cli_window.py`
- `data/public/kalshi-public/cli-window/`
