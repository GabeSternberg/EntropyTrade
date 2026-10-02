---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.78 checkpoint

Date: 2026-10-02. Phase 4.78 is complete. It is off-plan work. No order was
sent. No value was invented for a missing feature. No model was fit.
Nothing was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.78.md`.

## What the rows contain

The CLI rescore manifest has 39 rows, all station CLIPHL. The decision
clock is 15:00:00Z. The named columns are forecast_high,
point_in_time_climatology, and prints_at_decision. sized_book is false on
every row. Bid is empty on all 39 prediction records. Ask is empty on all
39 prediction records.

The stored previous-runs file has two hourly fields: time and
temperature_2m_previous_day1.

## Spec section 27

The spec lists 27 potential features. None of those names is a manifest
column or a previous-runs hourly field. The note does not fill one in.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 215 passed
(214 from Phase 4.77, plus 1 coverage test).

## Files

- `backend/src/entropytrade/weather/feature_coverage.py`
- `backend/tests/unit/test_feature_coverage.py`
- `docs/research/feature-manifest-coverage.md`
