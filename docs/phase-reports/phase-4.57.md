---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.57 checkpoint

Date: 2026-10-02. Phase 4.57 is complete. It is off-plan work. No order was
sent. No size was invented.

A copy of this file is in the repository at `docs/phase-reports/phase-4.57.md`.

## What was pulled

`GET /markets/trades` on the unauthenticated production host, one ticker at
a time, for the 240 stored KXHIGHPHIL markets. The historical trades
endpoint was empty for a probe ticker because those prints are after the
cutoff (`trades_created_ts` 2026-08-03). The cutoff body is stored. 259
calls, 0 failures, 104,442 prints, 240 tickers with at least one print.
`count_fp` is the size of that trade. It is not a size at the touch.

## How the three scenarios treat a print

The fidelity label on every scenario is `trade-print`. `guaranteed_fill` is
false. The taker coefficient is still unpublished, so no fee is applied.

The forecast rule is unchanged: it fires only when the previous-day forecast
is inside 80-81. That happens on 0 of the 40 CLI days. 2,665 B80.5 prints
fall at or before the 15:00 UTC decision on their market day, and they do
not make the rule fire.

| Scenario | Rule fires | Assumed fills | Equity |
| --- | --- | --- | --- |
| optimistic | 0 | 0 | 100.000000 |
| base | 0 | 0 | 100.000000 |
| conservative | 0 | 0 | 100.000000 |

Optimistic would assume one contract at the best YES print at or below
0.40, and would still call that assumption unguaranteed. Base and
conservative do not take a print as a fill. On this window that difference
does not move equity, because the rule never fires.

A separate test uses one synthetic forecast inside 80–81. A print after
15:00 is ignored. A print at 0.20 before 15:00 is an optimistic assumption
only: equity 99.800000 if the CLI high is 82. Base and conservative stay
at 100.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 180 passed
(176 from Phase 2.57, plus 4 trade-print tests).

## Files

- `data/public/kalshi-public/trades/`
- `backend/src/entropytrade/exchange/trade_prints.py`
- `backend/src/entropytrade/weather/trade_score.py`
- `backend/tests/unit/test_trade_prints.py`
