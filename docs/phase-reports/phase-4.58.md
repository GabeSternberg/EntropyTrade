---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.58 checkpoint

Date: 2026-10-02. Phase 4.58 is complete. It is off-plan work. No order was
sent.

A copy of this file is in the repository at `docs/phase-reports/phase-4.58.md`.

## Records

39 prediction records, one for each rescore day that has a point-in-time
climatology. Each has a prediction id, model version `previous_day1`, a
market ticker, a 15:00 UTC decision time, a feature hash, a probability,
and the source-manifest hash
`sha256:39e075dc258aa7da7ee7561b352515a04726eeef69d0b3970e2bb531e607ddeb`.
Bid, ask, and net edge are empty. The stored books have no size, and a
trade print is not a quote.

The feature vector adds the count of B80.5 prints whose created time is at
or before that decision. Across these 39 days that count is 2,617. Prints
created after 15:00 UTC are not in the count. The manifest version is
`cli-rescore-features-v2`. The source list now includes the stored trades
pull.

## The label rule

`refuse_late_label` raises when a label's `available_at` is after the
decision. `known_highs` leaves those labels out before the climatology is
hashed. The test checks every stored record: the same day's CLI high is
available the next morning, and that timestamp is not among the highs used
for the record.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 181 passed
(180 from Phase 4.57, plus 1 late-label test).

## Files

- `backend/src/entropytrade/weather/provenance.py`
- `backend/tests/unit/test_provenance.py`
- `data/public/features/cli-rescore-manifest.json`
- `data/public/features/cli-rescore-predictions.json`
