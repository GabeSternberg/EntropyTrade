# Research pipeline

Phase 5 turns a prompt into `StrategySpec` values and backtests the ones that
pass two gates. It does not send orders.

`pydantic-ai-slim[anthropic,openai]` 2.53.0 is imported only under
`entropytrade.agents`. Importing that package sets `ALLOW_MODEL_REQUESTS` to
false. `TestModel` still runs. Constructing `Agent("openai:gpt-4o")` without
a key fails before a request. No provider was called.

The demo prompt is the Philadelphia daily-high prompt from the spec. Scripted
`TestModel` outputs supply the research note, one hypothesis, four specs, and
the critic's judgements. The model does not read the tool results. The tools
themselves only return forecast vintages and displayed books. The CLI label
is not on `ResearchDeps` and does not appear in the stored prompts.

A spec is backtested only when the critic accepts it and
`compile_strategy` can run it. The interpreter requires an informational spec,
fixed contract size, an immediate order, a `*_probability` entry feature, and
an exit description that holds to settlement. Kelly sizing and any other exit
are stored as rejections. `run_replay` still raises on a holdout window, and
the pipeline raises before calling an agent if the window is a holdout.

The analyst summary is computed from ending equity. It is not a fifth model
call. On the fixture, `phl-probability-055` ends at 100.60 and
`phl-probability-090` does not trade. Nothing is promoted.
