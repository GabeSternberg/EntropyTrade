---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.66 checkpoint

Date: 2026-10-02. Phase 4.66 is complete. It is off-plan work. No order was
sent. No expiration value was invented.

A copy of this file is in the repository at `docs/phase-reports/phase-4.66.md`.

## What was compared

Each stored KXHIGHPHIL market has a result. Where the page also has an
exact `expiration_value` and a strike the existing rule can evaluate, the
rule says whether that value is YES. `greater` is above the floor, `less`
is below the cap, and `between` includes both ends. That side is compared
with the stored result.

3,720 markets have a yes or no result. 2,887 can be evaluated. All 2,887
agree. Mismatches: 0. The other 833 stay unevaluable. 808 of them have an
empty expiration value. 25 have no strike type. None have both problems.
An empty value is not filled in from the ticker, and a missing strike is
not inferred from the suffix. This is not a fill and it is not a
promotion. CLI replay equity stays 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 197 passed
(195 from Phase 4.65, plus 2 expiration checks).

## Files

- `backend/src/entropytrade/weather/expiration_check.py`
- `backend/tests/unit/test_expiration_check.py`
