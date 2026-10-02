---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2.51 checkpoint

Date: 2026-10-02. Phase 2.51 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-2.51.md`.

## Sentinel

The local HALT file already blocked new orders. What it did not have was one
name. `halt_sentinel(directory)` is `directory / "HALT"`. While that file
exists, `RiskEngine.halted` stays true, including after `resume`. Deleting
the file clears this one switch. The environment flag and `trading_enabled`
are unchanged. The file does not cancel resting orders and it does not
liquidate.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 169 passed.
The halt test now uses `halt_sentinel`. No new test was added.

## Files

- `backend/src/entropytrade/risk/engine.py`
- `backend/tests/unit/test_paper_risk.py`
- `docs/risk.md`
