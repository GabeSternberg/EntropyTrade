---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.223 checkpoint

Date: 2026-10-03. Phase 4.223 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.223.md`.

## Rule

This count rule was written before the zero volumes were counted.

Count stored Philadelphia candlesticks whose volume is exactly 0.00. A
volume counts when `volume_fp` parses as the decimal 0. Record the count
and the first and last ticker-hour that has that volume. Do not treat
0.00 as a missing volume. Do not treat volume as a size at the touch. Do
not compare it to 0.40. Do not align a volume to 15:00 UTC. Do not trade.
Do not score a holdout. Do not promote. No live order. The CLI coverage
row for trade volume stays "no stored value". Do not change `2°F` or
`0.40`.

## Result

5529 volumes are decimal strings. 1465 of them are exactly 0. The first is
`KXHIGHPHIL-26AUG23-B82.5#1`. The last is `KXHIGHPHIL-26SEP30-T83#24`.
0.00 is not a missing volume. Volume is not a size at the touch. The count
was not compared to 0.40 and was not used as a threshold. Volumes were not
aligned to 15:00 UTC. The CLI coverage row for trade volume still says no
stored value. Nothing was traded. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 375 passed.
