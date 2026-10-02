---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 6.50 checkpoint

Date: 2026-10-02. Phase 6.50 is complete. It is off-plan work. No order was
sent. No LLM provider was called.

A copy of this file is in the repository at `docs/phase-reports/phase-6.50.md`.

## What was stored

`data/public/features/cli-rescore-manifest.json` is the feature manifest for
the Phase 4.56 rescore. Version `cli-rescore-features-v1`. Sources are the
stored Open-Meteo previous-day forecast, the IEM CLI pull, and the Phase 4.55
tape, each with its endpoint and `available_at`. The manifest hash is checked
against a fresh build of those rows.

`data/public/features/cli-rescore-predictions.json` holds 39 prediction
records, one per probability day. Decision time is 15:00 UTC. The feature
vector is the forecast and the climatology known at that time. The day's own
CLI high is not in the vector. Probability is the raw forecast indicator,
which is 0 on every one of these days. Bid, ask, and net edge are empty
because there is no sized book. Nine records name a stored B80.5 ticker.
The other 30 days had no B80.5 market in the stored lists, so the record
names the stored series `KXHIGHPHIL` and marks the strike unlisted. Nothing
was promoted.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 169 passed
(167 from Phase 5.50, plus 2 provenance tests).

## Files

- `backend/src/entropytrade/weather/provenance.py`
- `backend/tests/unit/test_provenance.py`
- `data/public/features/cli-rescore-manifest.json`
- `data/public/features/cli-rescore-predictions.json`
