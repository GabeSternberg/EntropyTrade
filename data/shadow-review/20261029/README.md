# Continuous shadow milestone — executed evidence

Working checkout: designated `supervisor/20261029-001707`, starting HEAD `1ed5522`.
No branch/ref/index/commit/merge/push operation, credential access, production activation
or exchange order was performed. This is intermediate implementation evidence. **V1 is
incomplete.** Bitcoin remains optional and its existing receipt/validation boundaries
remain unchanged. The supervisor owns independent review and all Git operations.

The [operating guide](../../../docs/shadow-tracking.md) describes the browser controls,
frozen candidate, collection/evaluation/outcome path, recovery, risk caps, budgets and
remaining model/execution gaps. Source file hashes are recorded in `source-checksums.json`;
`evidence-checksums.json` inventories this bundle after verification. The actual runtime
probe preceded final refinements to offline replay and failure artifact indexing; it is
a development-checkout failure-path record, not final-checkout successful ingestion.

| Executed check | Result and scope |
| --- | --- |
| `.venv/bin/ruff check backend` | Passed; [log](ruff.log). |
| `.venv/bin/ruff format --check backend` | Passed, 491 files; [log](format.log). |
| `.venv/bin/mypy` | Strict check passed, 491 files; [log](mypy.log). |
| Focused pytest | **59 passed in 6.10s**, no skips: `unit/test_tracking.py`, `integration/test_shadow_tracking.py`, `unit/test_workbench_http.py`. [Log](shadow-tests.log), [JUnit](shadow-tests.xml). 45 new shadow cases and 14 existing workbench boundary cases. |
| Retained controlled integration | Both integrated procedures passed again with a new repository-local pytest base directory. [Log](controlled-integration.log), [JUnit](controlled-integration.xml), [workspaces](controlled-workspaces). These are explicitly controlled wire responses and injected clocks, never empirical data. |
| Frontend | `node --check` passed for `app.js` and `shadow.spec.cjs`; the existing presentation test file passes its assertions under `node --test`. [TAP](frontend.log). This is a DOM double, not a browser result. |
| Supported browser install | `PLAYWRIGHT_BROWSERS_PATH=.../frontend/browser/.browsers npm --prefix frontend/browser run install:chromium` exited 0; managed Chromium was present. No system/personal Chrome was used. |
| Actual Chromium launch | **Failed before page interaction**, one attempt: crashpad `socket.cc:45`, `setsockopt: Operation not permitted (1)`, then `SIGTRAP`. [JSON](browser/playwright-results.json), [JUnit](browser/playwright-results.xml), [trace](browser/playwright-artifacts/shadow-continuous-shadow-r-6dbcc-resume-and-durable-evidence/trace.zip). The test body did not run; there is no browser receipt, screenshot, download or browser acceptance pass. The denial was not retried. |
| Actual localhost listener probe | **Failed** during socket construction with `PermissionError: [Errno 1] Operation not permitted`; [exact traceback](listener-probe.log). No localhost page/listener acceptance was performed here. |
| Complete pytest attempt | Interrupted after two completed architecture checks when the existing collector reconnect test stalled. [Original log](pytest-full.log). A separately bounded 75-second diagnostic captured its asyncio selector/default-worker stack and ultimately exited 137 after termination; [trace](collector-diagnostic.log). The cause is unresolved, not asserted to be an application regression or a proved network cause. |
| Broader regression attempts | Excluding the known collector/listener blockers did not finish: the next attempt stalled in existing `test_read_only_market_book_and_cutoff_use_decimals`; a core/unit attempt stalled in existing `test_real_workflow_has_only_insufficient_or_unsupported_results`. Both were interrupted after retaining diagnostic stacks in [remaining regression log](pytest-remaining.log) and [core log](pytest-core.log). These are incomplete selections, not suite passes. No test/policy/risk limit was weakened. |

The focused cases cover strict monitor creation, synthetic refusal, active limits and
CSRF/same-origin restrictions; deterministic replay/strict intent deserialization; missing,
future, ambiguous and mismatched probabilities; future/expired fees; source, strategy
feature and rule gates; stale books, spread, fee-inclusive trade/event/total reservations;
duplicate intentions; protected-record/target withholding; transaction-safe pause and late
completion refusal; interrupted restart and preserved history; retry backoff/five-failure
pause; actual subprocess control seams; partial artifact indexing; original contract terms,
provisional/future/wrong-payout outcomes, archive fallback and receipt-time availability.

The controlled multi-cycle procedure uses real adapter/interpreter/storage code, controlled
HTTP transport bodies and explicit simulated clocks. It commits two cycles, reconciles two
official-format NO outcomes, reopens SQLite, proves original cycle/result/file identity and
recomputes decisions from retained inputs. It deliberately corrupts the second cycle's
`decision-inputs.json` **after verification** and asserts checksum rejection. The retained
workspace therefore intentionally contains that tamper specimen; first-cycle inputs and all
controlled raw receipt bytes remain intact. An offline verification of that altered cycle
must fail. This is software evidence only and proves no market performance.

## Actual credential-free failure-path probe

[probe.py](probe.py) ran the actual recorded research engine, created a real typed weather
candidate monitor, claimed one cycle and used the normal isolated `ShadowRunner` subprocess
with its normal 240-second deadline and credential-free environment. No transport, clock,
worker or HTTP response was replaced. The recorded research completed with real historical
insufficiency. The monitor was then paused and its quiescent workspace copied here.

- Start: October 29, 2026 at **04:34:41.933519 UTC**. Deadline failure committed at
  **04:38:55.545147 UTC**, including process termination/scheduling overhead.
- Partial acquisition: **0 HTTP receipts, 0 listed contracts, 0 observations**. Its five
  clocked failure events were two `GatewayError`s, an Open-Meteo `ConnectError`,
  `NoForecastVintage` and the acquisition time budget. The source capture itself never
  claimed success or substituted fixtures.
- Final cycle status: `failed`, detail `Worker exceeded the four-minute budget; partial
  receipts retained`. Monitor: `paused`. Submission: false, fills empty, performance null.
- [Probe log](probe.log), [monitor export](actual-probe/monitor.json), [stopped workspace](actual-probe/workspace).
  The actual receipt clocks and source error bytes are preserved. Its partial replay inputs
  do not constitute a committed successful cycle and cannot pass the standalone cycle verifier.

This executes persistence and deadline handling through a real isolated child, but does
**not** establish successful source access, a continuous deployment, fitted predictions,
live settlement reconciliation, UI interaction or profitability. Controlled fixtures cover
the corresponding deterministic software paths separately. No successful new real feed
or empirical result is claimed from this bundle.

## Outstanding supervisor/human acceptance

Run the executable [real browser procedure](../../../frontend/browser/shadow.spec.cjs)
using [the documented command](../../../docs/shadow-tracking.md) in an environment permitting
browser and localhost sockets. It submits a real recorded research form, starts a monitor,
waits for actual capture or visible failure, pauses/downloads, restarts the actual server,
compares bytes, resumes a second cycle and retains screenshots/downloads. Run with new
evidence/workspace paths. Fix concrete failures before claiming page-interaction acceptance.
Also run the unchanged complete Python suite in a suitable environment and investigate the
retained asynchronous stalls. No clean-install or complete-suite acceptance is claimed here.

Actual forward models, certified fees and sized books remain absent; actual decisions
therefore block with null probabilities/intents. Provider-backed research execution,
an approved and empirically supported second family, sustained real collection/shadow
operating evidence, final clean install and an independently checked `docs/v1_acceptance.md`
matrix remain release work. Review this milestone and stop before another major phase.
