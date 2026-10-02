---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 9 checkpoint

Date: 2026-10-02. Phase 9 is complete as a closed gate. Phase 10 has not been
started. No order was sent.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 10.

A copy of this file is in the repository at `docs/phase-reports/phase-9.md`.

## What was built

`attempt_submit` calls `resolve_trading_mode` and then returns. The injected
transport is called only when the resolved mode is `DEMO`. `READ_ONLY`,
`PAPER`, `SHADOW`, and `LIVE` raise `OrderSubmissionForbiddenError` first.
The live test sets `ENTROPYTRADE_LIVE_TRADING_ENABLED` to `true` and the
transport still is not called. The transport in that test raises if it is
called.

A demo call with status 201 and a matching `client_order_id` is
`acknowledged`. Status 400 is `rejected`. Status 201 with a failed validation
or a different id is `unknown`, and the id on the result is the request's id.
A `SubmitTransportError` (a timeout, not a 4xx) is also `unknown` with that
same id.

The module does not import `httpx` or `kalshi`, and it does not name
`api.elections.kalshi.com` or `demo-api.kalshi.co`. `KalshiGateway.submit_order`
still raises after the mode check and is not connected to `attempt_submit`.

## Acceptance

| Criterion | Result |
| --- | --- |
| Submit is behind `resolve_trading_mode` | Met. |
| `LIVE` does not call out, even with the flag | Met. |
| Demo uses an injected result, not a socket | Met. No real host is named. |
| Non-4xx and validation failure are `unknown`, keyed by `client_order_id` | Met. |
| No production credential | Met. None were added. |
| A real order | Not sent. The gateway method still cannot submit. |

## Files

- `backend/src/entropytrade/execution/submit_gate.py`
- `backend/tests/unit/test_submit_gate.py`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 134 passed.

## Reused code

`resolve_trading_mode` and `OrderSubmissionForbiddenError`. No audited bot.

## Weaknesses

- The gateway's `submit_order` is a second door and it still refuses every
  mode, including demo. There is no path from an approved intent to this gate
  inside the gateway.
- `acknowledged` is a label. It does not build an `Order` or write the ledger.
- Cancel is not classified.

## Decisions

- `LIVE` stays unwired even when the flag is set. The phase plan said not to
  make the change that would open it.
- The transport is an argument. This module has no HTTP client, so it cannot
  reach Kalshi by itself.

## Exact plan for Phase 10

Phase 10 is decay detection and downsizing. No live order. No trading key.
Do not connect `attempt_submit` to `KalshiGateway` in order to test decay.

1. Given a sequence of paper or shadow comparisons, flag decay when the
   recent mean difference (print minus fill price) is worse than a threshold
   supplied by the caller, using only comparisons that are not gaps.
2. A decay flag proposes a lifecycle move downward (`backtested` or `paper`
   toward `degraded` or `paused` only if that edge exists in the allow-list;
   otherwise stop at the nearest legal downward state). It must not propose
   `live` or `live_small`. An agent can apply a downward move. It still
   cannot apply an upward capital move.
3. Tests are fixtures. No socket.
4. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-10.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
