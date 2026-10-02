---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.60 checkpoint

Date: 2026-10-02. Phase 4.60 is complete. It is off-plan work. No order was
sent. No print was invented.

A copy of this file is in the repository at `docs/phase-reports/phase-4.60.md`.

## What was pulled

`GET /historical/trades` for the 3,720 KXHIGHPHIL tickers stored in the
historical market pages. Requests were paced. 3,880 calls, 0 failures.
1,018,012 prints. 3,666 tickers had at least one print. 54 tickers returned
an empty list, and those empty lists were kept as empty.

The raw pages are about 300MB, so they stay under `data/raw`, which git
already ignores. The commit has the manifest and a sqlite table of ticker,
time, price, count, and endpoint. The table is about 26MB. Price and count
stay on the exchange grid. A print is not a fill.

## What was not done

These rows are not an input to the 2026 CLI replay. That replay's equity
stays 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 186 passed
(184 from Phase 4.59, plus 2 historical-print tests).

## Files

- `data/public/kalshi-public/historical-trades/manifest.json`
- `data/public/kalshi-public/historical-trades/prints.sqlite`
- `backend/src/entropytrade/exchange/historical_trades.py`
- `backend/tests/unit/test_historical_trades.py`
