# CIS 1990 check-in — progress notes to rewrite

**Student action.** Rewrite these notes in your own words. Update the verification paragraph after your authenticated run.

**Objective.** This solo project builds a Kalshi research agent that can review market rules and external evidence, propose a falsifiable signal and typed strategy, and explain when the available history cannot support a backtest. The check-in focuses on Philadelphia daily-high-temperature contracts.

**Completed and verified.** The CLI routes the existing Research, Hypothesis, Quant and Critic roles through PydanticAI's Gemini adapter with typed handoffs (F3). It exposes a bounded evidence tool and keeps current snapshots outside historical experiment coverage (F6). The trace records source receipt times and hashes, role transitions, tool activity, model latency, token counts, estimated cost and failures (F7). On November 15, 2026, a live source-only run retrieved Kalshi contract rules and a matching NWS hourly forecast. The first development checks on November 15, 2026 used controlled HTTP responses at the Gemini and public-data boundaries. All three cases passed. Authenticated Gemini and scored model evaluation are pending. The retained historical sample has zero eligible forecast events and zero source-matched settlement highs.

**Development cases.** [DEV-001](dev-cases/DEV-001.json) checks source provenance, typed proposals and the backtest refusal. [DEV-002](dev-cases/DEV-002.json) checks the behavior when a forecast endpoint fails. [DEV-003](dev-cases/DEV-003.json) checks that instructions embedded in a market rule cannot authorize an order tool and that fabricated features are rejected.

**Changes and next steps.** The check-in uses one city and a CLI, with the proposal's F3/F6/F7 scope. **Student action.** Confirm any other changes against the submitted proposal. Next, verify authenticated Gemini end to end, run and score the development cases on the real model, then compare the team with a single agent. Keep the final evaluation set separate.

**Two risks.** Provider or source failures can interrupt a demonstration. Mitigate with bounded requests, explicit errors and an honestly labeled saved run. Historical data may lack compatible forecasts, contract terms, settlement labels or execution evidence. Mitigate by enforcing point-in-time eligibility and reporting insufficiency until compatible history is available.
