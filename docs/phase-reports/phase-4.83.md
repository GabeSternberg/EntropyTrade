---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.83 checkpoint

Date: 2026-10-02. Phase 4.83 is complete. It is off-plan work. No order was
sent. No StrategySpec was written. Nothing was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.83.md`.

## What the rows show

The 39 prediction records share one strategy id, `cli-aligned`, at version
1. The stored research specs are `phl-probability-055`,
`phl-probability-090`, `phl-copy-rejected`, and `phl-kelly`.
`cli-aligned` is not among them. Under `data/public`, the only JSON file
that contains the string is `features/cli-rescore-predictions.json`.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 220 passed
(219 from Phase 4.82, plus 1 strategy test).

## Files

- `backend/src/entropytrade/weather/provenance.py`
- `backend/tests/unit/test_prediction_strategy.py`
