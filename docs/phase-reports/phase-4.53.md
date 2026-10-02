---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.53 checkpoint

Date: 2026-10-02. Phase 4.53 is complete. It is off-plan work. No order was
sent. No new HTTP call was made. Open-Meteo is not the settlement label.

A copy of this file is in the repository at `docs/phase-reports/phase-4.53.md`.

## What was scored

The label is the Phase 4.51 CLIPHL daily high (earliest post-day NWS CLI).
The forecast is the stored Open-Meteo `temperature_2m_previous_day1` daily
max. Its `available_at` is 00:00 UTC on the valid day. A forecast is scored
only when that time is strictly before the CLI `available_at`.

The bracket is `between` 80 and 81, inclusive. Climatology at 15:00 UTC uses
only CLI highs already available. The calibrated number is the average of the
raw 0/1 forecast indicator and that climatology. The 30-day gate is open
(40 scored days). No model was fit. Nothing was promoted.

Sized books are the Phase 4.52 order books that have a real price-and-size
pair and a target date with a CLI label whose `available_at` is still in the
future relative to the book. The strategy sees `DecisionView` only. It buys
one YES at 0.40, fill-or-kill, only when the visible forecast would resolve
YES on that bracket.

## Numbers

| Quantity | Value |
| --- | --- |
| Scored days | 40 |
| MAE, forecast vs CLI | 2.9925 °F |
| MAE, first 20 days | 2.94 °F |
| MAE, second 20 days | 3.045 °F |
| Probability days | 39 (23 Aug has no prior CLI) |
| Brier, raw forecast | 0.05128205128205128205128205128 |
| Brier, climatology | 0.06005699903574191900593262792 |
| Brier, calibrated blend | 0.05280102438781537178926993164 |
| Days the forecast is inside 80–81 | 0 |
| Sized books before the CLI label | 0 |
| Replay fills | 0 |
| Ending equity | 100.000000 |
| Model gate open | yes |
| Fitted | no |
| Promoted | no |

The raw Brier is two misses in 39 days. Both are days the CLI high is inside
80–81 and the forecast is not: 25 Aug 2026 (CLI 80, forecast 79.8) and
11 Sep 2026 (CLI 81, forecast 81.7). The forecast never said YES.

## Phase 4 questions

**What has predictive value?** The previous-day Open-Meteo max is a rough
guide to the CLI integer (MAE 2.9925 °F). On the 80–81 bracket its raw
indicator has a lower Brier than climatology. It never landed inside the
bracket, so it has no YES signal on the contract this replay can trade.

**What adds incremental value?** Averaging the raw indicator with
climatology raises the Brier from 0.05128 to 0.05280. On these 39 days the
blend is worse than the raw forecast and better than climatology alone.
Climatology does not add value on top of the raw indicator here.

**Is there net edge after costs?** No. The forecast rule does not trade.
No sized book has a target date whose CLI label is still unpublished, so
replay produces no fill and equity stays 100.

**How stable is it?** MAE is 2.94 °F on the first half and 3.045 °F on the
second. The error stays near 3 °F. There is no P&L path to split.

**How sensitive is profitability to execution assumptions?** Not measurable
on this join. Fee and latency cannot move a run that never sees a signal
and never sees an in-window sized book. Equity stays 100.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 151 passed
(149 from Phase 4.52, plus 2 settlement-score tests).

## Files

- `backend/src/entropytrade/weather/settlement_score.py`
- `backend/tests/unit/test_settlement_score.py`
- `docs/weather.md`

## Decisions

- The CLI label is the score target. It matched official Kalshi results on
  the stored overlap in Phase 4.51. The contract text on these dates still
  names The Weather Company. The CLI is not renamed to settlement.
- The 30-day gate would allow a fit. This phase does not fit one and does
  not promote a strategy.
- The 12 sized books are active markets for 2 and 3 Oct 2026. Their pull
  time is after every stored CLI label that exists, and those two dates have
  no final CLI in the stored pull. They stay out of the replay.
