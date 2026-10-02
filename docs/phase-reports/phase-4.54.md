---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.54 checkpoint

Date: 2026-10-02. Phase 4.54 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-4.54.md`.

## What the vendored docs say

`.agents/skills/kalshi-docs/api-reference/market/get-series.md` states that
`quadratic_with_combo_maker_fees` is the same maker-fee structure with a
0.5 maker multiplier instead of 0.25. It points the general table at
`https://kalshi.com/docs/kalshi-fee-schedule.pdf`. It does not write a taker
coefficient.

`.agents/skills/kalshi-docs/getting_started/fee_rounding.md` states how a
model fee is rounded up to six decimal places. The worked example uses a
model fee of $0.00363825. That is an example input, not a coefficient.

`published_fees.py` records version `kalshi-docs-maker-fractions-v1`, cites
the series file, and leaves `QUADRATIC_COEFFICIENT` unset. Series replay
still takes the taker coefficient from the caller. Nothing hard-codes 0.07.

## PDF retry

`GET https://kalshi.com/docs/kalshi-fee-schedule.pdf` at
`2026-10-02T16:10:02.821328Z` returned HTTP 429. The body is a Vercel
security checkpoint page, stored at
`data/public/kalshi-fees/fee-schedule-retry.error.html`. The earlier 429
body is still at `fee-schedule.error.html`. No coefficient was read from
either page.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 161 passed
(160 from Phase 1.50, plus 1 published-fee test).

## Files

- `backend/src/entropytrade/execution/published_fees.py`
- `backend/src/entropytrade/execution/series_fees.py`
- `backend/tests/unit/test_series_fees.py`
- `data/public/kalshi-fees/fee-schedule-retry.error.html`
- `data/public/kalshi-fees/manifest.json`
