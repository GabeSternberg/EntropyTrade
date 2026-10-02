---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 5 checkpoint

Date: 2026-10-02. Phase 5 is complete. Phase 6 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 6.

A copy of this file is in the repository at `docs/phase-reports/phase-5.md`.

## What was built

A research pipeline under `entropytrade.agents`. `pydantic_ai` is imported
only there. Importing the package sets `ALLOW_MODEL_REQUESTS` to false.
`TestModel` still runs. An OpenAI agent string, with no key, raises
`UserError` before any request.

Four agents run in order: research, hypothesis, quant, critic. Their outputs
are pydantic models. The quant output is a batch of `StrategySpec` values.
The research agent has two tools, `list_forecasts` and `list_books`. There is
no submit tool and no Kalshi client in the package.

`compile_strategy` turns a supported spec into the callable `run_replay`
already accepts. It reads `DecisionView` features. A missing feature or a
failed predicate is no trade. Intent ids are a hash of the spec and the
decision time, so a second run of the same fixture has the same fill ids and
the same digest.

The critic can reject a spec. That spec is stored and not backtested, even
when the same predicates would have traded. A spec the critic accepts is
still refused when sizing is fractional Kelly or the exit text does not hold
to settlement. Those rejections are stored too.

The pipeline refuses a holdout window before any agent is called.
`run_replay` would also refuse one. The analyst summary is a sort of ending
equity plus the rejection reasons. It is not another model.

The demonstration prompt is the Philadelphia prompt in spec §40. On the
Phase 4 fixture, `phl-probability-055` buys one YES at 0.40 and ends at cash
100.60. `phl-probability-090` does not trade. The CLI value 91 is not in the
prompts, the forecast tool rows, or the summary.

## Acceptance

| Criterion | Result |
| --- | --- |
| Research → Hypothesis → Quant → Critic → StrategySpec | Met with TestModel. The outputs are scripted. A live model was not called. |
| Deterministic backtesting | Met through `run_replay` and the interpreter. |
| Backtest analyst | Met as computed text over the replay. It is not a fifth model call. |
| No holdout access | Met. A holdout window raises `PipelineError` before the agents run. |
| No trading | Met. No order tool, no trading key, no submit path. |
| Several concrete specs, ranked on the fixture | Met. Four specs, two backtests, ranked by equity. |
| PydanticAI typed outputs, StrategySpec only | Met. No generated Python. |

## Files

- `backend/src/entropytrade/agents/guard.py`
- `backend/src/entropytrade/agents/outputs.py`
- `backend/src/entropytrade/agents/deps.py`
- `backend/src/entropytrade/agents/team.py`
- `backend/src/entropytrade/agents/fixture.py`
- `backend/src/entropytrade/agents/pipeline.py`
- `backend/src/entropytrade/strategies/interpret.py`
- `backend/tests/unit/test_interpret.py`
- `backend/tests/unit/test_research_pipeline.py`
- `docs/research.md`

`pydantic-ai-slim[anthropic,openai]>=2.53,<3` is in `pyproject.toml`. The
resolved version is 2.53.0.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 115 passed.

## Reused code

Nothing from the audited trading bots. The agent framework is PydanticAI.
The spec type, the paper broker, and the replay engine are ours.

## Weaknesses

- `TestModel` does not read the prompt or the tool payload. The Philadelphia
  "research" is a script that states the fixture has no revision series.
  Live Anthropic and OpenAI calls are unverified.
- The interpreter does not run structural specs, Kelly sizing, resting
  orders, or any exit other than hold-to-settlement.
- Exit predicates are not evaluated. The description text is the gate.
- The run record is in memory. It is not in the strategy registry yet.
- The analyst cannot see a number the replay did not produce, and it also
  cannot explain a result beyond those numbers.

## Decisions

- The analyst is deterministic. A model that writes the P&L could disagree
  with the ledger. The spec's chain names an analyst agent; this phase
  keeps that step as code.
- Provider requests are blocked on import and left blocked. A later phase
  that calls a model has to set the flag back, on purpose, in a process
  that still has no trading key.
- Specs the interpreter cannot run are rejected rather than partially
  executed.

## Exact plan for Phase 6

Phase 6 stores lineage and shows it. No live orders. No trading key.
`configs/live` stays unloaded.

1. A SQLite registry records each `StrategySpec` by `spec_hash`, the parent
   hash, the research run id, the critic verdict, the replay digest, and the
   ending equity. Inserting the same hash twice does not create a second
   version. Version 1 has no parent.
2. Promotion uses the existing lifecycle table. An agent cannot construct
   `HumanApproval`. A transition into `live_small` or `live` without a human
   id is rejected. Moving down does not require one. The demo specs stay in
   `research` or `backtested`. None are marked live.
3. Experiment tracking writes those same fields to a local MLflow tracking
   directory created in the test temp dir. If the package cannot be imported
   without a server, do not start a server and do not mark the phase
   complete on a skipped test. No remote tracking URI.
4. A read-only dashboard lists the registry rows: hypothesis, spec id,
   verdict, equity, digest, state. It does not submit an order and it does
   not load `configs/live`. Cover an empty registry. The app stays on an
   uncommon port.
5. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-6.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
