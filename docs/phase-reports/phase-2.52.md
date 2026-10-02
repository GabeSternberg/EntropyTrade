---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2.52 checkpoint

Date: 2026-10-02. Phase 2.52 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-2.52.md`.

## Net edge

`RiskLimits.min_net_edge` is optional. When it is unset, the engine does not
add a check, so existing approvals stay as they were. When it is set, an
intent with no `EdgeEstimate` fails `min_net_edge`, and so does an estimate
whose net edge is below the floor. Net edge is model probability minus the
executable price minus the cost reserves on `EdgeEstimate`. A 0.70
probability at 0.69 with a 0.02 fee is rejected at a floor of 0. A 0.80
probability at 0.40 with no fee is approved.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 170 passed
(169 from Phase 2.51, plus 1 net-edge test).

## Files

- `backend/src/entropytrade/risk/engine.py`
- `backend/tests/unit/test_paper_risk.py`
- `docs/risk.md`
