---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 3 checkpoint

Date: 2026-10-02. Phase 3 is complete. Phase 4 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 4.

A copy of this file is in the repository at `docs/phase-reports/phase-3.md`.

## What was built

A point-in-time replay in `entropytrade.backtest.replay`. It does not import
`prediction-market-backtester` and it does not send orders.

Books are walked in `(received_at, market_ticker)` order, and only inside the
split window. The strategy is called with a `DecisionView` and that book.
`DecisionView.feature` is `select_as_of`: a row with `available_at` after the
decision is absent. A strategy that would buy only if it could see a future
settlement value does not trade.

`run_walk_forward` runs train and validation. It refuses to call the strategy
on a holdout window, and `run_replay` raises if asked to trade one.

Fills go through `RiskEngine.seal` and `PaperBroker`. The fill book is the
first book at or after `decision_time + latency`. Prices that improved versus
the book the strategy saw are clamped back to that earlier touch, so latency
cannot become a free upgrade. Worse prices still fill only when they are
inside the limit. Fees are `trade_fee`.

Settlements whose `available_at` lies inside the window and at or before the
clock are applied with `Ledger.settle`. A settlement later than the decision
does not flatten the position early.

`ReplayResult.digest` hashes the strategy spec hash, config hash, fill ids,
and ending equity. Two runs of the same recording produce the same digest.
Fill ids are deterministic when the intent id is.

## Acceptance

| Criterion | Result |
| --- | --- |
| Point-in-time replay | Met for books passed into `run_replay`. The SQLite recorder is not the reader yet; the caller supplies the books and features. |
| Fees, spread, latency, slippage | Met. Fees use the Phase 2 schedule. Spread is the book. Latency selects a later book. Slippage that improves on the decision touch is removed; slippage that worsens the touch remains. |
| Partial fills | Met by the paper broker, which the replay calls. The replay tests themselves fill one level completely. |
| Settlement | Met. A YES settlement inside the window pays the YES position and flats it. |
| Artifacts and identical reruns | Met for the digest above. There is no separate metrics file on disk. |
| Splits and walk-forward | Met for train, validation, and a skipped holdout. |
| A leaky strategy is blocked | Met. The future settlement feature is not visible, and the strategy does not trade. |

## Files

- `backend/src/entropytrade/backtest/replay.py`
- `backend/tests/unit/test_replay.py`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 94 passed.

## Reused code

Nothing from `prediction-market-backtester` or the vendored Jon Becker engine.
The point-in-time rule is the Phase 0 `select_as_of`. Fills, fees, and
settlement are the Phase 2 ledger.

## Weaknesses

- The recorder's frame table is not yet the replay source. A caller has to
  turn frames into `OrderBook`s.
- There is no on-disk run directory, no coherence recompute of a written
  metrics file, and no golden file beyond the in-memory digest.
- Partial fills, fee-on, and a multi-level book are not re-tested inside the
  replay module. They are tested on the broker.
- Walk-forward does not fit a model on train and freeze it for validation.
  It only stops the strategy from being invoked on the holdout.
- Open positions are still not marked to market. Ending equity is cash plus
  cost, then settlement.

## Decisions

- The strategy never receives the recording. Blocking leakage by filtering
  the view is the control. A strategy that closed over a future row it loaded
  itself would still cheat; the engine cannot see that, and research code is
  not given a loader that returns future rows.
- Holdout is not a silent empty window. Asking to replay it raises.
- Latency cannot improve the price. It can only keep it or make it worse.
  That is the conservative fill, not the optimistic one.

## Exact plan for Phase 4

Phase 4 is the daily-high weather vertical. No live orders. No label that is
the settlement itself.

1. A fixture dataset for Philadelphia (`KXHIGHPHIL`, station CLIPHL): contract
   text, the 2026-08-14 settlement-source cutover already implemented in
   `parse_settlement`, and daily high observations with `available_at` after
   the observation day. Do not use the maximum of hourly temperatures as the
   label. The label is a CLI daily high that becomes available when the
   fixture says it does.
2. Forecasts are `Forecast` records with `run_time <= available_at`. A
   baseline (persistence of the last available CLI high, or a fixed
   climatology value supplied in the fixture) is scored only on forecasts
   whose `available_at` is before the label's `available_at`.
3. A trading evaluation uses `run_replay` on bracket markets. The strategy
   may see the forecast vintage, not the CLI label. Report a forecast error
   and a paper P&L. Both are from fixtures. No NWS or Weather Company HTTP
   call is required; if one is added, test it with a recorded body and
   document that the live endpoint was not called.
4. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-4.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
