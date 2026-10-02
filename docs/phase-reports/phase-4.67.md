---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.67 checkpoint

Date: 2026-10-02. Phase 4.67 is complete. It is off-plan work. No order was
sent. No contract size was invented.

A copy of this file is in the repository at `docs/phase-reports/phase-4.67.md`.

## What was compared

Each stored print has a `count`, kept as contracts times 100. The sum of
those counts, divided by 100, is the tape's reported size. That sum is
compared with the market's `volume_fp`. A ticker absent from the print
table sums to zero, because the pull stored an empty list for it. The
comparison is exact. A print is not a fill.

3,720 markets have a result, and every one has a volume. 3,702 sums match.
18 are short: the tape is smaller than `volume_fp`. None are long. 54
markets have no prints; each of those has volume 0.00, so they are part of
the 3,702 matches.

The 18 short markets, as volume minus the tape:

- `KXHIGHPHIL-25AUG13-B92.5` short 131.00
- `KXHIGHPHIL-25AUG14-B91.5` short 25.00
- `KXHIGHPHIL-25JUN07-B77.5` short 1.00
- `KXHIGHPHIL-25JUN07-B81.5` short 194.00
- `KXHIGHPHIL-25MAY15-B76.5` short 49.00
- `KXHIGHPHIL-25MAY28-T59` short 1.00
- `KXHIGHPHIL-25OCT07-B81.5` short 148.00
- `KXHIGHPHIL-25OCT17-B63.5` short 170.00
- `KXHIGHPHIL-25OCT23-B60.5` short 1870.00
- `KXHIGHPHIL-25OCT24-B61.5` short 717.00
- `KXHIGHPHIL-25OCT27-T61` short 3.00
- `KXHIGHPHIL-25OCT28-B58.5` short 4.00
- `KXHIGHPHIL-25SEP18-T84` short 1.00
- `KXHIGHPHIL-25SEP21-B77.5` short 175.00
- `KXHIGHPHIL-25SEP25-B78.5` short 2.00
- `KXHIGHPHIL-25SEP27-B79.5` short 28.00
- `KXHIGHPHIL-25SEP27-B81.5` short 4.00
- `KXHIGHPHIL-25SEP27-T82` short 3.00

The gitignored response pages for those 18 tickers are each a single page
with an empty cursor, and the sizes on the page match the committed table.
The shortfall is between `volume_fp` and the trades the endpoint returned.
Those missing contracts are not added. Nothing is promoted. CLI replay
equity stays 100.000000.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 199 passed
(197 from Phase 4.66, plus 2 volume checks).

## Files

- `backend/src/entropytrade/weather/volume_check.py`
- `backend/tests/unit/test_volume_check.py`
