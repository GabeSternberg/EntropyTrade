---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.56 checkpoint

Date: 2026-10-02. Phase 4.56 is complete. It is off-plan work. No order was
sent. Nothing was fit or promoted.

A copy of this file is in the repository at `docs/phase-reports/phase-4.56.md`.

## What was scored

CLI labels and the previous-day Open-Meteo forecast, the Phase 4.55 tape,
and the fee model from Phases 3.50 and 4.54. `series-fields-v1` on
KXHIGHPHIL is quadratic with maker fraction 0. `kalshi-docs-maker-fractions-v1`
leaves the taker coefficient unset. The replay attaches that series version
and does not sweep a coefficient the docs do not state.

The forecast rule from Phase 4.53 still has 0 fills. The broader tape adds
0 sized books. Equity stays 100.000000 at zero latency and at a two-hour
latency. Phase 4.56 does not change the "equity stays 100" result.

## Five questions

What signals have predictive value? The previous-day forecast has MAE
2.9925 °F on 40 CLI days. It resolves the 80-81 strike on 0 days. Raw Brier
is 0.05128205128205128205128205128 against climatology
0.06005699903574191900593262792 on 39 days. No sized book supplies a market
probability before the label.

What signals add incremental value? The calibrated blend Brier is
0.05280102438781537178926993164. It does not beat the raw forecast. No model
was fit. Candles were not used as a market feature.

Is there net edge after costs? The rule does not trade. Fills are 0 and
equity stays 100.000000. KXHIGHPHIL is quadratic with maker fraction 0. The
taker coefficient is unpublished, so no costed edge is claimed.

How stable is it over time? MAE is 2.94 in the first half and 3.045 in the
second. Both halves leave the replay at 0 fills.

How sensitive is profitability to execution assumptions? 240 current books
in the window are empty and 230 candles have no touch size. A two-hour
latency on that tape still ends at 100.000000. The unpublished coefficient
was not swept.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 165 passed
(163 from Phase 4.55, plus 2 rescore tests).

## Files

- `backend/src/entropytrade/weather/tape_score.py`
- `backend/tests/unit/test_tape_score.py`
