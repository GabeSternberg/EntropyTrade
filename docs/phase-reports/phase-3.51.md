---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 3.51 checkpoint

Date: 2026-10-02. Phase 3.51 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-3.51.md`.

## What changed

`select_as_of` already dropped a row whose `available_at` was after the
decision, including inside replay's `DecisionView`. It still accepted a row
that was available early and then revised after the decision. That revision
could replace the value the strategy saw.

A row is now visible only when `available_at <= decision_time` and
`revised_at` is absent or also at or before the decision. Adding the late
revision does not change the selection. A replay strategy that buys only when
the revised value is 1 sees the original 0 and does not trade.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 157 passed
(155 from Phase 3.50, plus 2 leakage tests).

## Files

- `backend/src/entropytrade/domain/observations.py`
- `backend/tests/unit/test_strategy_and_pit.py`
- `backend/tests/unit/test_replay.py`
