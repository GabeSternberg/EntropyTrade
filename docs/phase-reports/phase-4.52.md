---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.52 checkpoint

Date: 2026-10-02. Phase 4.52 is complete. No order was sent. No API key was
used.

A copy of this file is in the repository at `docs/phase-reports/phase-4.52.md`.

## What was fetched

Unauthenticated GET against `api.elections.kalshi.com`. Every call returned
HTTP 200. Nothing was a 4xx, so no error body was stored. The demo host was
not required for this pull.

| What | Count |
| --- | --- |
| Live `KXHIGHPHIL` market pages | 3 pages, 420 markets |
| Historical `KXHIGHPHIL` market pages | 19 pages, 3720 markets |
| Order books with at least one price-and-size pair | 12, all `active` |
| Empty order book | 1 sample, `KXHIGHPHIL-26OCT01-T85`. Not loaded as a book. |
| Hourly candlesticks | 22 markets (the `B80.5` days in the CLI window that exist, plus the 12 active tickers) |

Bodies are under `data/public/kalshi-public/`. Each manifest entry has the
URL, status, and path.

## What becomes a book

`load_books` reads only `orderbooks/`. A level is a pair `[price, size]` from
`yes_dollars` or `no_dollars`. A zero size is dropped. Both arrays empty
returns nothing. The empty sample stays on disk and is not a book.

`available_at` for these books is the pull start `2026-10-02T15:48:09.632726Z`,
because the order-book payload has no exchange timestamp. Source is
`kalshi-public`. The endpoint is the order-book URL.

Candlesticks are stored and are not books. They do not include a size at the
touch, and this phase does not borrow the hour's volume to fill that in.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 149 passed.

## Files

- `data/public/kalshi-public/`
- `backend/src/entropytrade/exchange/public_tape.py`
- `backend/tests/unit/test_public_tape.py`
