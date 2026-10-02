---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.82 checkpoint

Date: 2026-10-02. Phase 4.82 is complete. It is off-plan work. No order was
sent. No calibration version was invented. Nothing was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.82.md`.

## What the records show

Spec section 28 lists a calibration version on a prediction record. The
stored CLI rescore file has 39 records. `calibration_version` is empty on
all 39.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 219 passed
(218 from Phase 4.81, plus 1 calibration test).

## Files

- `backend/src/entropytrade/weather/provenance.py`
- `backend/tests/unit/test_calibration_gap.py`
