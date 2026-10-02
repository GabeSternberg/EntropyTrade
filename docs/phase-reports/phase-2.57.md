---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2.57 checkpoint

Date: 2026-10-02. Phase 2.57 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-2.57.md`.

## What was already there

The local HALT sentinel and the `trading_enabled` flag already stop new
orders. `halt_sentinel(directory)` is the `HALT` file. `RiskEngine.halted` is
true when `trading_enabled` is false, when `ENTROPYTRADE_TRADING_ENABLED` is
not `true`, or when the HALT file exists. `resume` does not clear those.

## What this phase added

`max_reconciliation_age_seconds` was the missing pure check from that set.
When it is unset, the engine does not add it. When it is set, a missing
`last_reconciled_at` fails `reconciliation_age`, and a reconciliation older
than the cap fails. Age equal to the cap still passes. The caller supplies
the timestamp. This does not call an exchange.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 176 passed
(175 from Phase 2.56, plus 1 reconciliation-age test).

## Files

- `backend/src/entropytrade/risk/engine.py`
- `backend/tests/unit/test_paper_risk.py`
- `docs/risk.md`
