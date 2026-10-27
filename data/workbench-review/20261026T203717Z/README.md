# Website acceptance — 20261026T203717Z

**All four documented browser procedures passed. V1 remains incomplete.** Reviewed source
is `18be50cee17f03ae3dbfa198ed22e7a23635af1b`, tree
`529aaaa9802045b1dcf9dc6a99235c6634b7fd28`, on `supervisor/20261025-014400`.
The initial checkout was clean. Local `main` remains `30bed8e`; no remote freshness is
claimed. No branch, index, commit, merge or push was changed. The supervisor retains
independent final clean-checkout sign-off, review and all Git integration.

## Actual browser execution

The [passing receipt](browser-attempt-2/browser-receipt.json) records October 26,
**20:42:33.731–20:43:23.788 UTC**. Playwright **1.56.1** explicitly launched its own
**Chromium 141.0.7390.37** from `frontend/browser/.browsers/`, with a fresh context.
No Computer Use, personal Chrome, saved user profile, CDP connection, mocked response,
direct job submission or substituted source data was used. The real backend listened
on `127.0.0.1:43128`; backend/worker environments excluded inherited credentials.
Production submission and provider activation were confirmed false.

The [exact harness snapshot](harness-attempt-2/workbench.spec.cjs),
[configuration](harness-attempt-2/playwright.config.cjs) and pinned npm lockfile bind
the passing execution. The reusable [harness guide](../../../frontend/browser/README.md)
provides installation and repeat commands. The original sandbox npm attempt failed with
`ENOTFOUND registry.npmjs.org`; a normally approved network-enabled install and independent
Chromium download succeeded. Both installation logs remain here. No Chrome denial was retried.

| Procedure | Job / observed outcome |
| --- | --- |
| 1. Recorded weather | `c49061d6-61ea-4d84-b50d-fe56832634ee`: exact `revision_f >= 1.25 and hours_to_close < 8` typed specification; two INSUFFICIENT_DATA candidates; zero eligible historical feature events/labels/probabilities; holdout excluded; both downloads |
| 2. Software demo | `e5a7e2fb-add9-45d8-b9de-d69256b7c676`: independent gates, forecast metrics and simulated scenarios inspected; 100 of 192 validation probabilities; negative control zero fills in three scenarios; synthetic banner on all three tabs; both downloads |
| 3. Public weather | `576f88be-e8bc-423e-9d8a-737636124be1`: 8 successful HTTP receipts, 24 contracts, 648 observations, zero failures; complete forward ingestion |
| 3. Public Bitcoin | `f3d5c072-10f1-49a9-a730-b04550c218d5`: 3 successful receipts, 210 contracts, one spot observation, zero failures; all 210 `rules_known=false`, settlement basis unresolved, verified sources empty, 420 separate unverified authority mentions |
| 3. Deliberate OS-denied Bitcoin | `1b2f949a-9fe2-4e0f-bae8-18438b079fcd`: zero receipts/contracts/observations; timestamped KXBTC GatewayError and Coinbase ConnectError; visibly INCOMPLETE; expected failure path, never successful ingestion |
| 4. Active cancellation | `4161af54-ab3c-42cf-8ef3-4e3e5b3a09a7`: observed running, Cancel run clicked, terminal cancelled retained after restart |
| 4. Worker-slot reuse | `b8c4685e-eb1e-4ae8-8f95-b3b280e1a391`: recorded run completed after cancellation and both artifacts downloaded |
| 4. Shutdown/restart | `01e35f87-7e15-410c-9166-296b0eb7eb44`: observed running; own server stopped with SIGINT; restarted same workspace; interrupted history inspected; all six completed runs reopened |

The failure-path backend was explicitly launched under macOS `sandbox-exec` with outbound
connections denied. Its child worker attempted actual acquisition and produced two failure
events without fabricated HTTP receipts. Normal backend execution was restored before
lifecycle testing. Every public run was checked on Review, Probabilities and Evidence &
lineage: acquisition heading, receipt/contract/observation counts, UTC clocks, uncollapsed
failure summaries and limitations. Capture details and an actual contract's rules/available
features were expanded. The downloaded text contains the same summaries and settlement
limits. Neither current family acquired historical labels, fitted probabilities, empirical
model metrics or execution scenarios. Holdout stayed closed in every review.

There are **26 full-page screenshots**, **24 browser downloads**, saved DOM text,
[Playwright JSON](browser-attempt-2/playwright-results.json),
[JUnit](browser-attempt-2/playwright-results.xml) and a Playwright trace under
`browser-attempt-2/playwright-artifacts/`. One Playwright test executes four separately
recorded procedures; each procedure passed. Six completed protected reviews and **63 workflow
artifact hashes** were checked. The 12 original JSON/text downloads match parsed retained
reviews and report bytes. All 12 downloads repeated after restart have identical hashes.
Raw public capture files, model/experiment artifacts and final jobs/registry SQLite snapshots
are retained. [State audit](state-and-network-audit.json) records six completed, one cancelled
and one interrupted job. One browser console resource 404 remains recorded; no JavaScript
page errors or failed workflow requests occurred.

The [supplemental visual inspection](visual-review/receipt.json) reopened saved results
through the real UI and captured 12 readable, unedited screenshots of acquisition panels,
Bitcoin rule provenance, synthetic validation probabilities and negative-control scenarios.
These supplement the full-page screenshots; they do not replace an unexecuted procedure.

## Preserved initial failure

[Attempt 1](browser-attempt-1/browser-receipt.json) failed and remains intact, including its
JSON/JUnit results, trace, screenshots and downloads. It incorrectly required every exposed
prediction to have a calibration timestamp. The actual ridge outputs are uncalibrated and
record `calibration_asof=null`; the UI displays an em dash. This harness error stopped the
synthetic procedure before its initial downloads and then caused the restart comparison to
lack that download baseline. Procedures 1 and 3 passed; procedures 2 and 4 did not.

The corrected harness accepts null calibration only as the existing model representation,
checks all present calibration clocks and every fit clock against the decision, and asserts
validation-only predictions. No application assertion, model policy or safety boundary was
changed. Attempt 1 used Playwright's default separately installed headless shell; its receipt
recorded `chromium.executablePath()` for the full Chromium binary, which did not establish
the actual default process path. Attempt 2 makes the full executable explicit in launch
options. Its complete fresh rerun, not attempt 1, satisfies acceptance.

## Full unchanged committed-source checks

The [source runner](verify_source.py) exported committed source read-only at the repository
root, avoiding ignored-directory Ruff skips. The [manifest](export-manifest.json) binds all
**2,347 files** to the reviewed commit; [checks](checks.json) retain command clocks, exit
codes, deadlines, environment and log hashes. Locked offline setup used a fresh virtual
environment, pinned installed Python and existing package cache. No application dependency
was upgraded. All exported files remained unchanged.

- `uv lock --check`, `uv sync --locked` and the real server entry-point help passed.
- Full unchanged `make check` passed: Ruff lint, Ruff format (**477 files**), strict mypy
  (**477 files**) and **734 pytest tests in 184.91 seconds**, with no skips.
- JavaScript syntax and all **nine frontend presentation tests** passed without skips.

Listener-capable execution was normally approved; no listener test was skipped or relaxed.
This is additional committed-source verification, not the supervisor's final independent
clean-checkout sign-off. The temporary source export was removed only after byte-identity
verification; cleanup and final source comparison are recorded separately.

All **275 existing evidence checksums passed** before updates. Historical receipts were
preserved. Current documentation and the reusable browser harness are the only authored
changes; the application's financial safety boundaries, source provenance, point-in-time
clocks, settlement semantics and protected holdout were not changed. **V1 is incomplete**:
verified Bitcoin settlement/history and empirical evaluation, plus integrated continuous
paper/shadow, remain outside this acceptance task. Return to the supervisor for review.

From `data/workbench-review/`, verify all preserved evidence with:

```bash
shasum -a 256 -c SHA256SUMS
```
