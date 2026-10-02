---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2.56 checkpoint

Date: 2026-10-02. Phase 2.56 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-2.56.md`.

## Model age

`RiskLimits.max_model_age_seconds` is optional. When it is unset, the engine
does not add a check. When it is set, a missing `model_as_of` fails
`model_age`. A model older than the cap fails. A model whose age equals the
cap is still fresh, matching the book-age rule. The caller supplies the
timestamp. The engine does not load a model artifact.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 175 passed
(174 from Phase 2.55, plus 1 model-age test).

## Files

- `backend/src/entropytrade/risk/engine.py`
- `backend/tests/unit/test_paper_risk.py`
- `docs/risk.md`
