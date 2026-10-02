---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 6 checkpoint

Date: 2026-10-02. Phase 6 is complete. Phase 7 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 7.

A copy of this file is in the repository at `docs/phase-reports/phase-6.md`.

## What was built

A SQLite strategy registry, a local MLflow log, and a read-only page.

`Registry.register` inserts a spec hash once. Version 1 cannot name a parent.
A later version must name a parent that is already stored. Recording the
Philadelphia pipeline twice leaves four rows. Backtested specs move
`draft → research → backtested`. Rejected specs stop at `research`. A second
record does not walk those states backward.

Promotion uses `LifecycleTransition`. An agent cannot move `shadow_live` to
`live_small`, even with an approval object attached. A human actor can, when
the approval time is at or before the transition. The demo rows are not put
on that path.

`log_rows` writes the `entropytrade` experiment to a local tracking directory.
Ending equity is the string `100.600000` for the traded spec and `none` for a
rejection. No tracking server is started.

`GET /` renders the rows: strategy, state, verdict, equity, hypothesis, digest.
An empty file says nothing has been recorded. `POST` returns 405. The HTML
has no submit control and no script.

## Acceptance

| Criterion | Result |
| --- | --- |
| Lineage and versioning | Met. One row per hash. Version 2 names version 1. |
| MLflow | Met as a local file store. Equity is a string parameter. The MLflow UI server is not run. |
| Promotion states and approval | Met on the existing lifecycle table. Live-small requires a human. The demo stays at research or backtested. |
| Dashboard | Met for the columns in the Phase 5 plan. No charts, calibration plot, or trade blotter. |
| No live orders | Met. The page cannot post, and the registry does not import the gateway. |

## Files

- `backend/src/entropytrade/strategy_registry/store.py`
- `backend/src/entropytrade/strategy_registry/experiments.py`
- `backend/src/entropytrade/strategy_registry/dashboard.py`
- `backend/tests/unit/test_registry.py`
- `docs/registry.md`

`mlflow==2.22.5` is a direct dependency. It pulls FastAPI along. The page
does not use FastAPI.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 120 passed.

## Reused code

The lifecycle allow-list is the Phase 0 model. MLflow is the experiment log.
Nothing from the audited bots is vendored.

## Weaknesses

- The page is one table. Spec §40 also asks for charts, calibration, drawdown,
  trades, evidence, and assumptions. Those are not on the page.
- MLflow's own UI is not served. The test reads the tracking directory.
- The registry file is not yet written by the research pipeline automatically.
  `record_research` is a call the caller makes.
- SQLite reads for the page open a second connection so the server thread
  does not reuse the writer's connection.

## Decisions

- Equity is not an MLflow metric. Metrics are floats, and money in this
  codebase is `Decimal`.
- The page is the stdlib HTTP server, not a second frontend stack and not
  the FastAPI copy that MLflow installed.
- `configs/live` is still not loaded. The page has no path to it.

## Exact plan for Phase 7

Phase 7 is a deterministic scanner. No LLM in the path. No live order. No
trading key.

1. Given the books of one event at one time, flag:
   - a higher `greater` strike whose YES ask is above the YES ask of a lower
     strike (buying the harder contract costs more than the easier one),
   - mutually exclusive YES asks that sum to less than 1, and
   - a YES ask plus the complementary NO ask (the YES bid's complement) that
     sums to less than 1.
   Compare executable asks, not midpoints. A crossed book is skipped.
2. Fees come from the series `FeeSchedule` passed in. KXHIGH maker fee stays
   zero unless that schedule says makers pay. Do not hard-code 0.07.
3. A violation can become a paper intent only through `RiskEngine.seal` and
   `PaperBroker`. The scanner does not import `KalshiGateway` and does not
   call submit. If the risk gate rejects the intent, the violation is still
   reported and no fill is created.
4. Drive it from recorded `MarketFrame` values, not a live socket. Document
   that a hours-long WebSocket session is still unverified.
5. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-7.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
