---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.169 checkpoint

Date: 2026-10-03. Phase 4.169 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.169.md`.

## Rule

This count was written before the empty fields were counted.

Spec section 28 lists calibration version and uncertainty on a prediction
record. Count how many revision-bracket records leave each one empty.
Do not invent a calibration version. Do not invent an uncertainty. Do not
add a threshold. Do not score a holdout. Do not promote. No live order.

## Result

551 revision records leave `calibration_version` empty. The same 551 leave
`uncertainty` empty. Neither value was invented. `2°F` and `0.40` were not
changed. The holdout is not scored. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 271 passed.
