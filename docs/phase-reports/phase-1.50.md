---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 1.50 checkpoint

Date: 2026-10-02. Phase 1.50 is complete. It is off-plan work. No order was
sent. No socket was opened.

A copy of this file is in the repository at `docs/phase-reports/phase-1.50.md`.

## What changed

`health_flags` reads a `FeedHealth` and returns four booleans: connected,
stale, gapped, and lagging. Stale means at least one ticker is waiting for a
snapshot. Gapped means `last_gap` is set or `missing_sequence_frames` is
above zero. Lagging means `lag_seconds` is strictly above the caller's
limit. A limit equal to the lag is not lagging. A disconnected feed with no
messages is only disconnected.

`CollectorFeed.health` is unchanged. The flags are derived from it.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 160 passed
(159 from Phase 8.50, plus 1 health-flag test).

## Files

- `backend/src/entropytrade/exchange/feed.py`
- `backend/tests/exchange/test_feed_recorder.py`
