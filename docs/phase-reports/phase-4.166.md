---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.166 checkpoint

Date: 2026-10-03. Phase 4.166 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.166.md`.

## Rule

This hash rule was written before the omitted keys were named in the result.

Each revision-bracket prediction record already has a feature hash. Compare
that hash with the hash of the feature vector and with the hash of the
whole manifest row. Name the row keys that are not in the feature vector.
Do not change the hash. Do not add a row key. The CLI high and the print
price are not features. Do not add a threshold. Do not score a holdout.
Do not promote. No live order.

## Result

The revision row keys are `earlier_max`, `fired`, `fold`, `later_max`,
`place`, `revision`, `rule`, `ticker`, and `valid_on`. The feature hash
covers `earlier_max`, `later_max`, `place`, `revision`, `rule`, and
`valid_on`. The keys left out are `fired`, `fold`, and `ticker`. The hash
of the whole row does not match the stored feature hash. `high_f` and
`yes_price` are not row keys. The hash was not rewritten. `2°F` and
`0.40` were not changed. The holdout is not scored. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 268 passed.
