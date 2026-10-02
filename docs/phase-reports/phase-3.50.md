---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 3.50 checkpoint

Date: 2026-10-02. Phase 3.50 is complete. It is off-plan work. No order was
sent. No trading key was used.

A copy of this file is in the repository at `docs/phase-reports/phase-3.50.md`.

## What was stored

Unauthenticated GET. The fee-schedule PDF did not return a fee table.

| Call | Result |
| --- | --- |
| `GET /trade-api/v2/series/KXHIGHPHIL` | HTTP 200. `fee_type` `quadratic`, `fee_multiplier` 1. |
| `GET /trade-api/v2/series/fee_changes?series_ticker=KXHIGHPHIL` | HTTP 200. `series_fee_change_arr` is empty. |
| `GET /trade-api/v2/series/KXNHL` | HTTP 200. `fee_type` `quadratic_with_maker_fees`, multiplier 1. |
| `GET /trade-api/v2/series/KXMVECROSSCATEGORY` | HTTP 200. `fee_type` `quadratic_with_combo_maker_fees`, multiplier 1. |
| `https://kalshi.com/docs/kalshi-fee-schedule.pdf` | HTTP 429. Body is a Vercel security checkpoint page, stored at `data/public/kalshi-fees/fee-schedule.error.html`. |

Bodies and the manifest are under `data/public/kalshi-fees/`. Each call has
its URL and `fetched_at`. The series payload has no quadratic coefficient.
None was invented. `manifest.json` records `"quadratic_coefficient": null`.

## How replay uses it

`run_replay(..., series_fees=table)` replaces the broker schedule for each
book with the stored series. The stored fields are `fee_type`,
`fee_multiplier`, and whether makers pay. Maker fractions follow the fee-type
description already in the API reference: 0 for `quadratic`, 0.25 for
`quadratic_with_maker_fees`, 0.5 for `quadratic_with_combo_maker_fees`.

The quadratic coefficient stays the number already on the broker. It is the
one field the payload does not contain. A caller-supplied coefficient is no
longer the only path: a broker built as maker-fee multiplier 9 is overridden
to KXHIGHPHIL quadratic multiplier 1 before the fill.

The run records fee-model version `series-fields-v1` and a `FeeModelRef` per
series seen. `effective_from` is the series `last_updated_ts`.

## Tests

On one contract at 0.50 with coefficient 0.20 and quantity 10:

| Series | Role | Fee |
| --- | --- | --- |
| KXHIGHPHIL | maker | 0 |
| KXHIGHPHIL | taker | 0.50 |
| KXNHL | maker | 0.13 |
| KXNHL | taker | 0.50 |
| KXMVECROSSCATEGORY | maker | 0.25 |

A replay of `KXHIGHPHIL-26OCT02-T89` that starts with multiplier 9 and
`maker_pays` true fills as a taker for 0.05, which is coefficient 0.20 at
price 0.40 with the stored multiplier 1. The recorded model is quadratic,
multiplier 1, makers do not pay, version `series-fields-v1`. An unknown
series raises `ReplayError` and does not get a fee.

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 155 passed
(151 from Phase 4.53, plus 4 series-fee tests).

## Files

- `data/public/kalshi-fees/`
- `backend/src/entropytrade/execution/series_fees.py`
- `backend/src/entropytrade/execution/fees.py`
- `backend/src/entropytrade/backtest/replay.py`
- `backend/tests/unit/test_series_fees.py`
- `docs/backtesting.md`

## Decisions

- The general-table coefficient is not hard-coded. The PDF fetch failed and
  the body is kept.
- Flat fees still raise. None of the stored series is flat.
- Paper fills stay taker fills. Maker versus taker is scored on the schedule
  the series table builds.
