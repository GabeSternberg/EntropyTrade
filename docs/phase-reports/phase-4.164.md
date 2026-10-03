---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.164 checkpoint

Date: 2026-10-03. Phase 4.164 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.164.md`.

## Rule

This skip rule was written before the skipped days were counted.

A skipped day is a train or validation label, on a city already scored,
that did not become a `forecast_revision_bracket` prediction record. The
holdout is not listed.

The reason is the first of these that applies. No other reason is used.

1. The later or earlier vintage clock is after 15:00 UTC.
2. That clock is at or after the label.
3. The later max or the earlier max is missing from the stored vintages.

A day that became a record is not skipped, whether or not the rule fired.
This does not add a threshold. Nothing is promoted. No live order.

## Result

17 train days were left out. Each one is 2026-08-23, and each reason is
"a vintage max is missing." The cities are New York, Austin, Oklahoma
City, Dallas, Denver, Louisville, Boston, Minneapolis, San Francisco,
San Diego, Newark, Trenton, Los Angeles, Washington DC, Seattle, Las
Vegas, and Atlanta. Philadelphia and Chicago have a record for that day.
No train or validation day was left out because the vintage clock was
after 15:00 UTC or at or after the label. The holdout is not listed.
`2°F` and `0.40` were not changed. Nothing was promoted.
`docs/research/kxhigh-scan.md` includes the skip sentence.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 267 passed.
