---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2.50 checkpoint

Date: 2026-10-02. Phase 2.50 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-2.50.md`.

## What changed

`adopt_order` still moves an order only along the legal transition table,
keyed by `client_order_id`. It now refuses the adoption when:

- the contract differs,
- the requested quantity differs,
- both sides already have an exchange order id and the ids differ,
- the remote filled quantity is smaller than the local filled quantity.

A missing local exchange id can still be filled in from the remote order when
the state and filled quantity already agree. A partial fill can still advance
to filled when the remote filled quantity is larger and the transition is
legal. Filled quantity still cannot exceed the requested size; that check
stays on `Order`.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 158 passed
(157 from Phase 3.51, plus 1 reconciliation test).

## Files

- `backend/src/entropytrade/execution/reconcile.py`
- `backend/tests/unit/test_paper_risk.py`
