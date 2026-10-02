---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.77 checkpoint

Date: 2026-10-02. Phase 4.77 is complete. It is off-plan work. No order was
sent. No probability was stored for the skipped day. Nothing was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.77.md`.

## Which day

The stored CLI comparison has 40 labels, from 2026-08-23 through
2026-10-01. The feature manifest and the prediction file each have 39
rows. The day in the labels and not in the records is 2026-08-23.

The forecast for that day is stored. Its `available_at` is 2026-08-23
00:00 UTC. The CLI label's `available_at` is 2026-08-24 05:55 UTC, from
header `240555`. The forecast is available before the label, so the
builder did not skip the day for a missing forecast or a forecast that
arrives with or after the label.

The decision is 2026-08-23 15:00 UTC. `known_highs` at that time is 0.
The day's own CLI high is not available until the next morning, and no
earlier CLI high is in the stored set. `climatology_hit_rate` raises
`InsufficientHistoryError` with the message "no CLI high is available at
the decision". That is the continue branch that dropped the day.

No probability was written for 2026-08-23.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 214 passed
(213 from Phase 4.76, plus 1 coverage test).

## Files

- `backend/src/entropytrade/weather/provenance.py`
- `backend/tests/unit/test_prediction_coverage.py`
