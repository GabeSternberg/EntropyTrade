---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 8.50 checkpoint

Date: 2026-10-02. Phase 8.50 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-8.50.md`.

## What changed

`compare_shadow_and_paper` runs the same books through paper and shadow on
separate ledgers. Each decision becomes a `ShadowPaperRecord`: the market,
whether paper filled, the paper price, the shadow price, and the difference
(paper minus shadow) when both prices exist.

Shadow still does not write the ledger. Paper still fills against the book.
Neither mode can be live. A limit of 0.50 against an ask of 0.40 records a
paper fill at 0.40, a shadow price of 0.50, and a difference of -0.10. A
later book the strategy skips does not add a row.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 159 passed
(158 from Phase 2.50, plus 1 shadow-versus-paper test).

## Files

- `backend/src/entropytrade/execution/shadow.py`
- `backend/tests/unit/test_shadow.py`
