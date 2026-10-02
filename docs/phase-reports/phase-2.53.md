---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2.53 checkpoint

Date: 2026-10-02. Phase 2.53 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-2.53.md`.

## Open orders

`RiskLimits.max_open_orders` is optional. When it is unset, the engine does
not add a check. When it is set, the caller-supplied `open_orders` count must
be strictly below the cap, so one more order still fits. A count of 1 against
a cap of 1 is rejected. A count of 1 against a cap of 2 is approved. The
portfolio snapshot stores resting collateral, not a count, so the caller
passes the count. A negative count is refused before the checks run.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 171 passed
(170 from Phase 2.52, plus 1 open-order test).

## Files

- `backend/src/entropytrade/risk/engine.py`
- `backend/tests/unit/test_paper_risk.py`
- `docs/risk.md`
