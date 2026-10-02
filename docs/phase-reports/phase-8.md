---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 8 checkpoint

Date: 2026-10-02. Phase 8 is complete. Phase 9 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 9.

A copy of this file is in the repository at `docs/phase-reports/phase-8.md`.

## What was built

`run_shadow` walks recorded books. It calls `resolve_trading_mode` first.
`LIVE` raises even when the environment is production and
`ENTROPYTRADE_LIVE_TRADING_ENABLED` is `true`. `DEMO` raises because that mode
submits to an exchange. The strategy is not called in either case.

`PAPER` sends the intent through the risk gate and `PaperBroker`. A YES buy
at 0.40 against a later print at 0.45 records a difference of 0.05 and cash
of 99.60. `SHADOW` records that same 0.40 and does not change the ledger.
`READ_ONLY` does not fill and does not emit a comparison. If no print exists
at or after the book, `gap` is true and the difference is absent. The runner
does not invent a price.

## Acceptance

| Criterion | Result |
| --- | --- |
| Paper fills through the risk gate and the paper broker | Met in `PAPER`. |
| Shadow records a price without filling | Met. Cash stays 100. |
| Comparison to the next print | Met. A missing print is a gap. |
| Refuses `LIVE` | Met, including when the live flag is set. `DEMO` is refused too. |
| No gateway and no exchange submit | Met. The module does not name `KalshiGateway`. |
| Live demo socket | Unverified. The inputs are fixtures. |

## Files

- `backend/src/entropytrade/execution/shadow.py`
- `backend/tests/unit/test_shadow.py`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 131 passed.

## Reused code

The mode gate, the risk engine, and the paper broker. No audited bot.

## Weaknesses

- One book and one strategy callback. It does not subscribe to a socket or
  read the recorder.
- Shadow compares the approved limit, which on this fixture is the ask. It
  does not walk a later book the way replay does.
- `READ_ONLY` drops the intent instead of logging that it saw one.

## Decisions

- `DEMO` is refused alongside `LIVE`. The phase plan named `LIVE`. Demo
  submission is the other mode that talks to an exchange, so the runner
  refuses it too.
- A missing print stays missing. There is no fallback price.

## Exact plan for Phase 9

Phase 9 is the first mode that could submit. Do not place an order. Do not
add a trading key. Do not load `configs/live` as a default.

1. A submit function exists only behind `resolve_trading_mode`. It returns
   before any network call unless the resolved mode is `DEMO`. `LIVE` returns
   before the call even when the flag is set, until a later explicit change
   this plan does not make. Default mode stays `read_only`.
2. Tests prove: read-only, paper, shadow, and live-with-the-flag never call
   the transport. A demo-mode test uses a mock transport and a thrown-away
   key generated in the test, never a real credential. A non-4xx or a
   validation failure is `unknown` and is reconciled by `client_order_id`.
   Do not send that mock order to `api.elections.kalshi.com` or
   `demo-api.kalshi.co`.
3. No production trading credential in the repo, logs, or fixtures.
4. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-9.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only. If the only way to
   finish a test is a real order, stop and leave Phase 9 unmarked.
