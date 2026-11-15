# CIS 1990 check-in video guide

Record a 75–90 second video. Rehearse with your Gemini key in the website’s masked field or loaded in the server’s environment. Keep the key masked during the recording. [Gemini API key setup](https://ai.google.dev/gemini-api/docs/api-key)

## 0:00–0:15 — Introduce the project

Explain in your own words that the Kalshi research agent checks market rules and outside evidence. This run asks about Philadelphia daily-high temperature and whether the evidence supports a testable strategy.

## 0:15–0:55 — Show the running application

Start the website from the repository root with `uv run --locked entropytrade-web`. Open [CIS 1990 Research Demo](http://127.0.0.1:43128/#/cis1990) in Real Mode and click **Run Philadelphia Weather Research**. Point out the four stages, expand one Kalshi rule, and show the NWS coverage and matching target date. Scroll to a hypothesis, a structured proposal, the Critic decision, and backtest eligibility. Finish with **Execution trace** and its model, latency, token and available cost fields.

For the CLI walkthrough, run the same workflow from the repository root:

```sh
uv run --locked entropytrade cis1990-demo
```

The command submits the Philadelphia prompt printed at startup. Show `gemini-3.5-flash-lite`, the Kalshi and NWS lines with HTTP status, and the matching date if available. Show the four role names as they run. In the final report, show one hypothesis, the typed proposal or reason it was withheld, and the Critic's decision plus the deterministic reasons. Point to the printed `data/cache/cis1990/<run-id>/run.json` path and open it if time permits.

If rehearsal takes longer than the video window, complete a genuine run before recording and reload the course page to reopen it. Identify it as a saved run and walk through its results. In a terminal, you can likewise show the start of a new run and switch to the saved trace.

If a source or Gemini fails, show the status honestly. For a source-only partial demonstration, run the command below and identify it as a live Kalshi/NWS check. The saved controlled test results can illustrate trace format if labeled as controlled.

```sh
uv run --locked entropytrade cis1990-demo --check-sources
```

## 0:55–1:25 — Explain progress and next steps

Name the approved features and give each one concrete example. F3 coordinates four roles through typed handoffs. F6 bounds calls and denies access to order tools, secrets and held-out outcomes. F7 records source, model, tool and handoff events. Explain why the available historical data cannot support an empirical backtest. The next milestones are a scored development evaluation, a single-agent comparison, and enough compatible historical evidence for a defensible backtest.
