---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.141 checkpoint

Date: 2026-10-02. Phase 4.141 is complete. It is off-plan work. No order was
sent. Nothing was promoted. The four bracket rules were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.141.md`.

## Rule

This rule was written before any score. It was not changed afterward.

At 15:00 UTC, take two vintages of the same valid day's hourly temperature
whose `available_at` is at or before the decision. Later vintage: latest run
with `available_at` <= 15:00 UTC. Earlier vintage: latest run with
`available_at` <= 03:00 UTC the same day. Daily max is the max of that
vintage's hourly values. Revision = later_max - earlier_max. If either
vintage is missing, no trade.

`forecast_revision_up` fires only when revision >= 2°F and the later max is
inside 80–81 inclusive. Optimistic may assume one YES at a B80.5 print at or
before 15:00 UTC with price <= 0.40. Base and conservative do not treat a
print as a fill. Fidelity label `trade-print`. A print is not a guaranteed
fill. Fee coefficient stays unset. Walk-forward train then validation. No
holdout. No promotion. This is one more hypothesis.

## Result

Two vintages are not on disk. `data/public/open-meteo/previous-runs.json`
has `time` and `temperature_2m_previous_day1` only. That series has no run
time and no `available_at`.

The previous-runs API was asked for one model run of the Philadelphia point
and returned HTTP 400. The body, unchanged, is
`data/public/open-meteo/two-vintages.error.json`:

```json
{"error":true,"reason":"Parameter 'run' must not be set"}
```

No hourly rows were invented from that body. `forecast_revision_up` was not
scored. Fires, fills, optimistic equity, and validation equity were not
computed. Chicago was not scored. Nothing was promoted.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 243 passed.
