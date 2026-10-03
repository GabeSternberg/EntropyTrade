---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.184 checkpoint

Date: 2026-10-03. Phase 4.184 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.184.md`.

## Rule

This record rule was written before the mean was computed.

The historical station/model bias for the stored Philadelphia pair is the
arithmetic mean of the 39 eligible previous-day errors. Skipped days are
not in the mean. The mean is the exact decimal quotient. It is not rounded
to a trading tolerance. It is not subtracted from a forecast. Do not add a
threshold. Do not trade. Do not score a holdout. Do not promote. No live
order. The CLI coverage row for historical station/model bias stays "no
stored value".

## Result

The 39 eligible errors sum to 24.7°F. Their exact mean is
0.6333333333333333333333333333 °F. Skipped days are not in the mean. The
mean was not rounded and it was not subtracted from a forecast. The CLI
coverage row for historical station/model bias still says no stored value.
Nothing was traded. `2°F` and `0.40` were not changed. Nothing was
promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 297 passed.
