# CIS 1990 check-in video guide

Record a 75–90 second video from the repository root. Rehearse the command with a Gemini API key loaded through your shell or secret manager. Keep the key setup outside the recording. [Gemini API key setup](https://ai.google.dev/gemini-api/docs/api-key)

## 0:00–0:15 — Introduce the project

Explain in your own words that the Kalshi research agent checks market rules and outside evidence. This run asks about Philadelphia daily-high temperature and whether the evidence supports a testable strategy.

## 0:15–0:55 — Show the running application

```sh
uv run --locked entropytrade cis1990-demo
```

The command submits the Philadelphia prompt printed at startup. Show `gemini-3.5-flash-lite`, the Kalshi and NWS lines with HTTP status, and the matching date if available. Show the four role names as they run. In the final report, show one hypothesis, the typed proposal or reason it was withheld, and the Critic's decision plus the deterministic reasons. Point to the printed `data/cache/cis1990/<run-id>/run.json` path and open it if time permits.

If rehearsal takes longer than the video window, run the command before recording and keep that genuine trace open. Show the command starting and switch to the saved run. Say explicitly that the displayed result came from the earlier run.

If a source or Gemini fails, show the status honestly. For a source-only partial demonstration, run the command below and identify it as a live Kalshi/NWS check. The saved controlled test results can illustrate trace format if labeled as controlled.

```sh
uv run --locked entropytrade cis1990-demo --check-sources
```

## 0:55–1:25 — Explain progress and next steps

Name the approved features and give each one concrete example. F3 coordinates four roles through typed handoffs. F6 bounds calls and denies access to order tools, secrets and held-out outcomes. F7 records source, model, tool and handoff events. Explain why the available historical data cannot support an empirical backtest. The next milestones are a scored development evaluation, a single-agent comparison, and enough compatible historical evidence for a defensible backtest.
