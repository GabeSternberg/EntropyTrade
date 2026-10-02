---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 7 checkpoint

Date: 2026-10-02. Phase 7 is complete. Phase 8 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 8.

A copy of this file is in the repository at `docs/phase-reports/phase-7.md`.

## What was built

A deterministic scanner in `entropytrade.strategies.scanner`. It does not
import the Kalshi gateway and it has no model call.

A higher `greater` strike whose YES ask exceeds a lower strike's YES ask is a
monotonic violation. Crossed books are omitted. Mutually exclusive YES asks
that sum to less than 1 are an exclusive violation; the caller supplies the
set, so exhaustiveness is not inferred. The same-book complement of YES ask
and the NO ask implied by the YES bid is at least 1 whenever the book is
uncrossed, and a crossed book is skipped.

The paper path buys one lower-strike YES and one higher-strike NO when that
package plus taker fees costs less than 1. Fees use the series `FeeSchedule`.
Both legs go through `RiskEngine.seal` and `PaperBroker`. If either leg is
rejected, or the approved size is smaller than one contract, nothing is
filled and the violation remains. A coefficient of 2 on the fixture consumes
the edge; a coefficient of 0 fills both legs and moves cash from 100 to 99.50.

A `BookSnapshotFrame` converts to the book the scanner reads. No socket is
opened.

## Acceptance

| Criterion | Result |
| --- | --- |
| Monotonic, exclusive, and complement checks | Met on executable asks. The complement check does not fire on an uncrossed book. |
| Fees from the series schedule | Met. Coefficient 0 trades; coefficient 2 does not. Nothing hard-codes 0.07. |
| Paper only, through the risk gate | Met. A zero loss limit reports the violation and does not fill. |
| No LLM and no live submit | Met. The module does not name the gateway. |
| Recorded frames, not a live socket | Met for snapshots. A live WebSocket session is still unverified. |

## Files

- `backend/src/entropytrade/strategies/scanner.py`
- `backend/tests/unit/test_scanner.py`
- `docs/scanner.md`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 126 passed.

## Reused code

The book, the fee function, the risk gate, and the paper broker are ours.
No audited bot is imported.

## Weaknesses

- Deltas are not applied. The scanner wants a snapshot.
- Exclusive asks are not checked for whether the contracts really partition
  the event. A caller can pass an unrelated pair.
- The paper package is one contract on two legs. Partial size and a resting
  hedge are not modeled.
- There is no process that subscribes to frames and calls the scanner. The
  function is there; the live loop is not.

## Decisions

- The locked paper trade is lower-strike YES plus higher-strike NO, because
  that package pays at least 1 across the three temperature regions. Flagging
  a rich ask is not by itself a reason to buy that ask.
- Complement inconsistency on one book is the crossed-book case, which is
  already refused. It is tested as a skip, not as a trade.

## Exact plan for Phase 8

Phase 8 is live paper and shadow. No real order. No trading key. Live mode
stays off.

1. A shadow runner consumes a sequence of recorded books and trade prints for
   one ticker. It may emit a paper intent through the risk gate and the paper
   broker. It must not construct `KalshiGateway` and must not call submit.
2. After a paper fill, compare the fill price to the next recorded trade
   print at or after the fill time. Record the difference. A missing later
   print is a recorded gap, not a guessed price.
3. `resolve_trading_mode` stays the gate. The runner refuses to start when
   the resolved mode is `LIVE`. Default mode remains `read_only`, which also
   does not submit. Paper mode is the one that fills the ledger.
4. Tests use fixtures. A real demo WebSocket and a demo account are
   unverified without a key. Do not block on that.
5. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-8.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
