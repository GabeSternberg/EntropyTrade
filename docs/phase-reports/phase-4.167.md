---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.167 checkpoint

Date: 2026-10-03. Phase 4.167 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.167.md`.

## Rule

This naming rule was written before the stored strategy id was checked
against the spec list.

Read the strategy id and version on the revision-bracket prediction
records. Confirm every record cites the same id and version. Confirm that
id is not a stored StrategySpec. Do not write a spec. Do not add a
threshold. Do not score a holdout. Do not promote. No live order.

## Result

551 revision records cite `forecast_revision_bracket` version 1. That id
is not one of the stored StrategySpecs. Under `data/public`, the id
appears only in `features/revision-bracket-manifest.json` and
`features/revision-bracket-predictions.json`. No spec was written. `2°F`
and `0.40` were not changed. The holdout is not scored. Nothing was
promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 269 passed.
