# CIS 1990 check-in handoff

- Repository [GabeSternberg/EntropyTrade](https://github.com/GabeSternberg/EntropyTrade)
- Submission SHA is provided with the completion message. From a checkout containing this handoff, `git log -1 --format=%H -- docs/cis1990/CHECKIN_HANDOFF.md` prints the immutable implementation commit.
- The check-in adds a Philadelphia CLI to the existing four-agent research pipeline. Gemini Flash-Lite receives typed evidence, hypothesis, strategy and critique handoffs. The CLI gathers public Kalshi listings and contract rules, and NWS forecasts. Current evidence stays outside historical backtest coverage. Deterministic checks return eligibility or refusal reasons. This check-in CLI performs research only.

## Run from the repository root

### Website

Load `GEMINI_API_KEY` in the shell that starts the server, then run `uv run --locked entropytrade-web`. Open [CIS 1990 Research Demo](http://127.0.0.1:43128/#/cis1990) in Real Mode and click **Run Philadelphia Weather Research**. The latest course run can be reopened after a reload. The page shows public source receipts, validated stage outputs, candidate and Critic decisions, and a downloadable trace. A missing server credential disables the run button.

### CLI

```sh
uv sync --locked
# Load GEMINI_API_KEY using your shell or secret manager before recording.
uv run --locked entropytrade cis1990-demo
```

Use a Gemini Developer API key in `GEMINI_API_KEY`. Kalshi and NWS calls are public GETs. An absent key exits with status 2 and the message `cis1990-demo: set GEMINI_API_KEY for provider-backed research.` A provider or workflow failure exits with status 1 and saves a trace. A completed, justified refusal exits with status 0. [Gemini key setup](https://ai.google.dev/gemini-api/docs/api-key) · [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) · [PydanticAI Google integration](https://pydantic.dev/docs/ai/models/google/)

For a source-only smoke test, run `uv run --locked entropytrade cis1990-demo --check-sources`. This exits with status 0 when a listed market date has NWS forecast hours. The CLI reports full-day coverage separately. Results go in `data/cache/cis1990/sources-*.json`. An agent run saves `data/cache/cis1990/<run-id>/run.json`, `report.md` and `checksums.json` in the run directory. Review the prompts and public rule excerpts in the trace before sharing it.

## Verification and hand-in materials

| Item | Location and result |
| --- | --- |
| First development checks, November 15, 2026 | [DEV-001](dev-cases/DEV-001.json), [DEV-002](dev-cases/DEV-002.json), [DEV-003](dev-cases/DEV-003.json). Three passed through controlled HTTP at the Gemini SDK and public-source boundaries. The authenticated, scored model evaluation is pending. |
| Reproduce the checks | `uv run --locked pytest -q backend/tests/unit/test_cis1990_demo.py`. This also exercises missing credentials and a redacted provider failure. |
| Live source trace | [public-sources-2026-11-15.json](evidence/public-sources-2026-11-15.json). Kalshi and both NWS requests returned HTTP 200. The sources matched November 15, 2026, with four retained contract rules and a 24-hour NWS forecast. |
| Controlled evaluation evidence | [controlled-dev-results-2026-11-15.json](evidence/controlled-dev-results-2026-11-15.json). Responses were scripted. |
| Repository checks | Ruff lint and format and strict mypy passed. Full pytest with loopback access and one OpenMP/BLAS thread passed 1,506 tests. The final targeted suite passed 74 tests, including the partial-day forecast case added after full-suite collection. |
| Website verification | Full pytest passed 1,510 tests. The 36 focused Python checks and 31 frontend unit checks passed. Real Chromium at port 43128 passed the controlled four-stage workflow, provider failure, missing-key and Demo Mode scenarios, and the existing shell regression. Authenticated Gemini verification requires a server-side key. |
| Progress update notes | [checkin-progress-draft.md](checkin-progress-draft.md) |
| Video recording instructions | [checkin-video-guide.md](checkin-video-guide.md) |

## Before submitting

1. Load your Gemini key and rehearse the website or CLI. Check the source status and open the trace. Authenticated Gemini is pending.
2. Record a 30-second to 2-minute video yourself. Identify saved results or partial runs if you use them.
3. Rewrite the one-page update in your own words. Check it against your original proposal and update the verification claims from your run. Keep the controlled development-check date distinct from any later scored evaluation.
4. Submit the private repository URL and SHA, your video, and your progress update through Gradescope.

The course PDFs were unavailable in the inspected local paths, so this check-in uses the requirements supplied with the request.
