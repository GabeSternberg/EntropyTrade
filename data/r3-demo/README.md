# R3 recorded-coverage mock research

These are **mock LLM outputs over actual R1/R2 evidence**, not live provider research or
an empirical strategy test. The two prompts cover Philadelphia forecast revisions and
Chicago model disagreement. Each produces three hypotheses, two typed specs blocked by
insufficient data and one explicitly unsupported proposal. No backtest is executed.

Each UUID directory retains run.json (full prompts, tool outputs/hashes, hypotheses,
StrategySpecs, critic and deterministic verdicts, code/config identity, usage and timings),
report.md and checksums. The SQLite demonstration registry remains locally at
`data/cache/r3-release.sqlite`; it uses the same Registry implementation as R1/R2.
The JSON artifacts preserve the completed audit independently of that local database.

No real LLM key was configured; real provider verification is blocked. An HTTP mock tests
the actual OpenAI SDK/PydanticAI tool/structured-output protocol and its failure path.
The example is deliberately not described as empirical autonomous discovery.

See [agent research guide](../../docs/agent-research.md) for offline/live commands,
protection boundaries, limits, assumptions and the proposed R4 scope.
