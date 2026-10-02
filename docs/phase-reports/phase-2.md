---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 2 checkpoint

Date: 2026-10-02. Phase 2 is complete. Phase 3 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 3.

A copy of this file is in the repository at `docs/phase-reports/phase-2.md`.

## What was built

Paper accounting, a paper broker, and a deterministic risk gate. Nothing in
this phase calls `submit_order` or opens a trading key.

`Ledger` tracks cash, one net position per market, fills, settlements,
realized P&L, and collateral reserved by resting orders. Buying the opposite
outcome collapses the overlap: the pair pays one dollar per contract, and the
two costs come out of realized P&L. Equity, defined as cash plus open cost,
equals starting cash plus realized P&L, fees included. The same `fill_id` is
applied once. `LedgerStore` writes that state as one SQLite row. Reloading it
and applying the same fill does not change cash.

`PaperBroker.submit` accepts only an `ApprovedOrderIntent`. A raw
`OrderIntent` raises `PaperBrokerError`. The broker walks the Phase 1
`OrderBook` (YES asks for a YES buy, YES bids for a NO buy), charges
`trade_fee` on each taker slice, and rests good-till-canceled remainder as
collateral. Fill-or-kill cancels when the book cannot complete the walk.
Immediate-or-cancel cancels the remainder. Post-only rejects a cross.
Reduce-only cannot open a position and cannot close more than is held.
A crossed book is refused.

`trade_fee` takes `quadratic_coefficient` from the caller. Makers pay only
when `maker_pays` is true, so a KXHIGH-style quadratic schedule charges makers
nothing. Flat series fees raise `FeeFormulaError` instead of inventing a
formula. There is no built-in 0.07.

`RiskEngine.evaluate` is fail-closed. It rejects on the kill switch, a `HALT`
file, `trading_enabled=False`, `ENTROPYTRADE_TRADING_ENABLED` other than
`true`, a stale book, a crossed book, a spread wider than the cap, a book
thinner than `min_liquidity`, a realized loss at the loss limit, or a realized
drawdown at the drawdown limit. Otherwise it clips the quantity to the
tightest of per-trade, per-event, total deployed, bankroll, and (for a taker)
the size the book can fill. `seal` builds an `ApprovedOrderIntent` and raises
`RiskRejectedError` when the decision did not approve. `resume` clears only
the in-process switch.

`compare_snapshots` reports cash and open-position disagreements.
`adopt_order` moves a local order to the remote state only when
`client_order_id` matches and the Phase 0 transition table allows it, including
`unknown` to `filled`.

## Acceptance

| Criterion | Result |
| --- | --- |
| Property tests for accounting | Met. Makers are free unless the schedule says otherwise. The quadratic product is symmetric in the YES price. Same-side fills keep equity equal to cash plus cost and to starting cash plus realized P&L, and a second apply is a no-op. A YES/NO pair at the same YES price realizes zero. |
| Strategies cannot bypass risk | Met. A raw intent cannot be submitted. A killed, halted, or rejected decision cannot be sealed. The broker's parameter type is `ApprovedOrderIntent`. |
| Crash/restart reconciliation | Met for the paper ledger and for adopting an `unknown` order from a fixture snapshot. A live demo account was not queried. |
| No production trading | Met. No trading key, no `submit_order` call, live mode still off. |

## Files

- `backend/src/entropytrade/portfolio/ledger.py`
- `backend/src/entropytrade/portfolio/store.py`
- `backend/src/entropytrade/execution/fees.py`
- `backend/src/entropytrade/execution/paper.py`
- `backend/src/entropytrade/execution/reconcile.py`
- `backend/src/entropytrade/risk/engine.py`
- `backend/tests/unit/test_paper_risk.py`
- `backend/tests/property/test_accounting.py`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 89 passed.

## Reused code

No bot repository was vendored. The netting rule (YES plus NO collapses to one
dollar) is the Kalshi position model already stated on `Position` in Phase 0.
The fee shape is the published quadratic product, with the coefficient supplied
per schedule rather than copied from a bot.

## Weaknesses

- Drawdown and the loss limit use cash plus open cost. Open positions are not
  marked to the book, so a quote crash does not reduce equity until a fill or
  a settlement. Stale-book and spread checks are what stop a trade on a bad
  quote.
- A resting paper order is not matched against a later book. Collateral stays
  reserved until something else releases it.
- Flat fees are refused. Combo maker fees use the same quadratic product as
  other maker-charging schedules.
- Demo reconciliation is a fixture. No demo credential was available, so the
  gateway's portfolio methods still raise, as they did in Phase 1.
- The dashboard pause button does not exist. `kill` is the function it will
  call. Cancelling resting orders on a halt is not automatic.
- Per-series caps, correlated exposure, order rate, slippage, and minimum net
  edge are not checks yet.

## Decisions

- The quadratic coefficient is an argument. Hard-coding 0.07 would hide that
  series schedules differ. Tests pass a coefficient in, including 0.02, and
  never rely on a default.
- `PaperBroker` does not accept an `OrderRequest` built by hand. The approved
  intent is the only door. That is stricter than the protocol, which still
  has `submit_order` for a later phase, and the read-only gateway still
  refuses that method.
- Equity ignores mark-to-market. The identity "equity = start + realized" is
  then exact, which is what the property tests lock. A mark would break that
  identity unless realized were redefined.

## Exact plan for Phase 3

Phase 3 is the point-in-time backtester. It does not place live or demo
orders. Do not vendor `prediction-market-backtester`. Reimplement the ideas
behind our types: a run record, a coherence check, a deterministic hash, and
a refusal to train on rows that were not available at decision time.

1. A replay clock walks recorded frames and trades in `received_at` order.
   `select_as_of` is the only way a strategy sees a feature or a forecast.
   A fixture strategy that reads a future settlement or a future trade must
   be rejected, or the run must record zero decisions from it. Test that
   leak directly.
2. Fills go through `PaperBroker` and `trade_fee`, with spread already in the
   book. Add a latency shift: a decision at `t` fills against the book at
   `t + latency`, and if that book is missing the order does not fill at a
   better price than the decision book. Partial fills stay as they are.
3. Settlement uses the stored rules and `Ledger.settle`. A run artifact
   records the spec hash, fee schedule, seed, and window. A second run on the
   same recording produces the same artifact hash.
4. Walk-forward splits use the Phase 0 `BacktestRun` windows: train, then
   validation, then optional holdout, non-overlapping. The strategy function
   under test must not receive the holdout rows during training. Test that.
5. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-3.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
