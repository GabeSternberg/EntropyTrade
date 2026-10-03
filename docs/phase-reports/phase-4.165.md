---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.165 checkpoint

Date: 2026-10-03. Phase 4.165 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.165.md`.

## Rule

This note was written before the stored feature names were copied into it.

Read the `features` field of the stored revision-bracket manifest. Report
those names. Do not add them to the CLI rescore manifest. The existing
table row for `forecast changes/revisions` stays "no stored value" because
that row means the CLI rescore columns and the previous-runs hourly fields.
Do not add a threshold. Do not score a holdout. Do not promote. No live
order.

## Result

The stored revision-bracket manifest features are `later_max`,
`earlier_max`, and `revision`. They match a rebuild. They were not added
to the CLI rescore columns. The table row for `forecast changes/revisions`
still says no stored value, because that row is the CLI rescore manifest
and the previous-runs hourly fields. `2°F` and `0.40` were not changed.
The holdout is not scored. Nothing was promoted.
`docs/research/feature-manifest-coverage.md` includes the sentence.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 267 passed.
