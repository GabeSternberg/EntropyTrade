---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.97 checkpoint

Date: 2026-10-02. Phase 4.97 is complete. It is off-plan work. No order was
sent. Nothing was scored. Nothing was promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.97.md`.

## What was listed

`KXHIGHTEHAM` is the next ticker after `KXHIGHTMMMX`. The series title is
Amsterdam Daily High Temperature. Six listed markets, all for 2026-08-20,
settle in Celsius at thresholds 17 through 22. None of those tickers is
`B80.5`.

40 `B80.5` tickers in the 2026-08-23 through 2026-10-01 window were
requested. All 40 returned
`{"error":{"code":"not_found","message":"not found"}}`. The Fahrenheit
80-81 bracket was not applied to a Celsius strike. `scored` is false.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 237 passed
(236 from Phase 4.96, plus 1 Amsterdam test).

## Files

- `backend/src/entropytrade/weather/amsterdam_listing.py`
- `backend/tests/unit/test_amsterdam_listing.py`
- `data/public/amsterdam/manifest.json`
- `data/public/amsterdam/markets.json`
- `data/public/amsterdam/celsius-markets.json`
