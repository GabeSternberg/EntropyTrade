---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.79 checkpoint

Date: 2026-10-02. Phase 4.79 is complete. It is off-plan work. No order was
sent. The stored feature hash was not rewritten. Nothing was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.79.md`.

## What the hash leaves out

Each manifest row has eleven keys. The feature-vector hash matches the row
with `market_ticker` and `sized_book` removed. Hashing the whole row does
not match the stored feature hash. The on-disk prediction records still
match a fresh build, so the hash bytes did not change.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 216 passed
(215 from Phase 4.78, plus 1 hash-gap test).

## Files

- `backend/src/entropytrade/weather/provenance.py`
- `backend/tests/unit/test_feature_hash_gap.py`
