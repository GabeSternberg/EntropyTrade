---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4 checkpoint

Date: 2026-10-02. Phase 4 is complete. Phase 5 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 5.

A copy of this file is in the repository at `docs/phase-reports/phase-4.md`.

## What was built

A daily-high vertical that never calls a weather API.

Recorded-body parsers turn an NWS CLI product, a Weather Company JSON object, and
a forecast JSON object into `DailyHigh` or `Forecast`. The CLI label is the first
`MAXIMUM` line. Hourly temperatures in the same text are ignored. A daily high
whose `available_at` falls on the observation day is rejected. Forecast JSON
rejects floats and unknown fields, and the `Forecast` type still requires
`run_time <= available_at`.

Persistence repeats the last CLI high only when that high is already available.
Mean absolute error uses the latest forecast with `available_at` strictly before
the label. A forecast that exists only after the label is not a score.

Four probabilities are comparable on a strike:

- market midpoint (not executable),
- climatology hit rate of CLI highs already available at the decision,
- a raw 0/1 from whether the forecast value would resolve YES,
- the average of those two.

`Strike.resolves_yes` is the operator: `greater` and `less` are strict,
`between` is inclusive. A fitted or ML model raises `InsufficientHistoryError`
below 30 scored days. The fixture is shorter than that, so no model is fit.

Paper trading goes through `run_replay`. The strategy can see `forecast_high`.
It cannot see `cli_high` on the decision day. One YES contract bought at 0.40
and settled YES ends at cash 100.60 with a zero fee coefficient, 100.59 with
coefficient 0.02, and 100 if latency walks off the only book.

Philadelphia text with no named source, ticker `KXHIGHPHIL-26OCT02-T89`, still
parses as `kxhigh_schedule` / The Weather Company.

## Research questions

These answers are about the synthetic fixture. They are not findings about
live Philadelphia markets.

- Predictive value: a post-label forecast is excluded. On the scored pairs in
  the unit test, a raw indicator can look perfect and still be two hand-built
  days. That is not evidence of a signal.
- Incremental value: climatology uses only prior labels, so a later CLI of 100
  does not change a 0.5 hit rate. The calibrated number is the average of that
  rate and the raw indicator. No second model beat a costed market after a
  real sample, because there is no real sample.
- Net edge after costs: the one-contract YES buy makes 0.60 before fees and
  0.59 after a 0.02 quadratic coefficient. The fee is an argument. It is not
  a hard-coded 0.07, and KXHIGH makers are not given a taker fee.
- Stability: two prices and a handful of labels. Not stable, and not claimed
  to be.
- Execution sensitivity: the same signal loses the trade when the fill book
  is two hours later and the recording has no later book. Profitability on
  this fixture is sensitive to that assumption.

No trading edge on live data was found, because live data was not used. That
is a limit of the run, not a software failure.

## Acceptance

| Criterion | Result |
| --- | --- |
| Weather adapters | Met for recorded CLI, Weather Company, and forecast bodies. Live HTTP is not implemented. |
| Point-in-time forecast dataset | Met inside tests: availability is on the record, and later rows do not change the score. There is no on-disk manifest. |
| Baseline probability models | Met for market, climatology, raw forecast, and a one-line calibration. ML is refused on purpose. |
| Forecasting and trading evaluation | Met. MAE ignores leaked forecasts. Paper P&L changes with the fee coefficient and with latency. |
| Do not advance a model for a better score alone | Met. Nothing is promoted. The raw indicator's low error on two days is not treated as edge. |

## Files

- `backend/src/entropytrade/weather/recorded.py`
- `backend/src/entropytrade/weather/baseline.py`
- `backend/src/entropytrade/weather/probability.py`
- `backend/tests/unit/test_weather_baseline.py`
- `backend/tests/unit/test_weather_recorded.py`
- `docs/weather.md`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 109 passed.

## Reused code

Nothing from `mifisher/kalshi-weather-bot` or Open-Meteo. The point-in-time
rule, the strike operators, the paper broker, and the replay engine are ours.

## Weaknesses

- No live NWS, Weather Company, or Open-Meteo client. A recorded body is the
  only input. Those live endpoints are unverified.
- The dataset is inline in tests, not an immutable file with a manifest.
- Calibration is an average, not Platt or isotonic regression.
- No ML model. Thirty scored days are required and not present.
- Weather rows are not written by the recorder.
- The trading test is one synthetic contract-day.

## Decisions

- Adapters parse recorded bodies and do not grow an HTTP client in this phase.
  A live call would be an unverified dependency, and the spec's research
  questions cannot be answered by inventing a response.
- The fitted-model gate is 30 scored days. Below that, the phase reports a
  refusal instead of a coefficient.
- Fee coefficient 0.02 in the sensitivity test is an input to `trade_fee`.
  The series schedule is still per series. KXHIGH maker fee is not set here.

## Exact plan for Phase 5

Phase 5 is the research pipeline. No trading key, no order tool, no live
order, and no holdout rows in the agent deps.

1. Depend on `pydantic-ai-slim[anthropic,openai]>=2.53,<3`. Import
   `pydantic_ai` only under `backend/src/entropytrade/agents/`. Tests set
   `ALLOW_MODEL_REQUESTS` false and use `TestModel` (or `FunctionModel`).
   If no LLM key is present, do not call a provider. Document the live call
   as unverified.
2. A typed pipeline runs Research, Hypothesis, Quant, and Critic, then emits
   `StrategySpec` values. Specs stay data. No generated Python. Each agent
   output is a pydantic model. The critic can reject a spec; rejected specs
   are stored and not backtested.
3. A predicate interpreter turns `entry_rules` into the callable `run_replay`
   already accepts. It reads `DecisionView` features only. A missing feature
   is no trade. It does not `exec` anything. Exit rules that are not "hold
   to settlement" are recorded as unsupported and that spec is rejected
   rather than half-run.
4. The deps object exposes the Phase 4 fixture forecasts and books. It does
   not expose labels with `available_at` after the decision, and it has no
   method that submits an order. `run_replay` still raises on a holdout
   window. The pipeline never builds a holdout window.
5. One in-memory run record stores the prompt, the research note, each
   hypothesis, each spec hash, each rejection, each replay digest, and the
   critic note. The demonstration prompt is the Philadelphia daily-high
   prompt in spec §40. `TestModel` supplies several concrete specs. The
   pipeline backtests them on the fixture and ranks them by ending equity.
   Rank is a sort, not a promotion into live trading.
6. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-5.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
