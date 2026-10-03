---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.219 checkpoint

Date: 2026-10-03. Phase 4.219 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.219.md`.

## Rule

This count rule was written before the distinct volumes were counted.

Count the distinct stored Philadelphia candlestick volumes. A volume
counts only when `volume_fp` is a decimal string, including `0.00`.
Record how many distinct volume values occur, and name the smallest and
the largest in numeric order. A missing volume is not filled in. Volume
is not a size at the touch. Do not compare a volume to 0.40. Do not treat
the count as a threshold. Do not align a volume to 15:00 UTC. Do not
trade. Do not score a holdout. Do not promote. No live order. The CLI
coverage row for trade volume stays "no stored value". Do not change
`2°F` or `0.40`.

## Result

5529 volumes are decimal strings, including 0.00. 3023 values are
distinct. 0 volumes were missing. In numeric order the smallest is 0.00
and the largest is 35960.16. The ordered values are locked by SHA-256
`4cc28b60c016a333deb76eb2be4c421b143d73a267ed42e3e7866bad531fb9bf`. Volume
is not a size at the touch. The count was not compared to 0.40 and was
not used as a threshold. Volumes were not aligned to 15:00 UTC. The CLI
coverage row for trade volume still says no stored value. Nothing was
traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 367 passed.
