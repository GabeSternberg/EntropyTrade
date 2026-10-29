# Legacy SQL NULL model binding recovery — October 29, 2026

Implemented from `bd67f10` on designated `supervisor/20261029-124902`. All Git mutations
remain with the supervisor. **V1 complete=false; browser/full-suite acceptance unresolved.**

[Verification receipt and source fingerprints](verification.json) record the checked
JUnit totals and executed commands. [Artifact checksums](checksums.json) cover this
correction's reports and notes; earlier evidence remains unchanged.

Recovery now preserves SQL NULL model bindings left by the tracking store's supported
legacy migration. Strategy identity, job references and later cycle/evidence validation
still apply. No model is inferred from a reference or an available export. Non-null values
must decode to an object and pass the existing hash, bound/blocked and model identity
checks. JSON `null` is rejected; it is distinct from SQL NULL.

The regression removes the binding column to exercise the actual legacy migration, with
both a paused completed monitor and an active unfinished monitor. It verifies exact logical
database dumps before startup, original exports, source/evidence bytes and timestamps,
startup interruption with a fresh cycle, idempotent recovery, unchanged NULL after resume,
and continued scoring/decision replay refusal. A model reference and export deliberately
remain present; freezing a binding or invoking strategy/risk execution fails the test.
Ten malformed non-null cases check both snapshot and restore refusal without publication.
All data/models in these new tests are CONTROLLED software fixtures, not empirical evidence.

| Check | Executed result |
|---|---|
| [Pre-fix regressions](before-fix.log), [JUnit](before-fix.xml) | 6 failed, 5 passed, 23 deselected. Reproduces SQL NULL JSON decoding failure and five non-object JSON values raising an unhandled `AttributeError`. |
| [Recovery suite](recovery.log), [JUnit](recovery.xml) | 34 passed in 11.74 seconds. |
| [Broader focused selection](focused.log), [JUnit](focused.xml) | 291 passed, 3 explicitly deselected in 18.13 seconds. Recovery, tracking/models, workbench HTTP, multi-cycle shadow integration, deterministic experiments/execution and submit refusal. |
| [Ruff](ruff.log), [format](format.log), [strict mypy](mypy.log) | Pass; 501 formatted files checked, 499 configured source/test files type checked. |
| [Frontend assertions](frontend.log) | 12 named tests pass through `node frontend/tests/acquisition.test.cjs`. These are presentation checks, not browser interaction. |
| [Recovery browser harness discovery](browser-harness-list.log) | Existing managed-Chromium Playwright recovery test is discovered; both recovery spec/config syntax checks also pass. No browser launched. |

The broader selection uses the same exclusions as the preceding local-recovery milestone:

```bash
timeout 90s .venv/bin/python -m pytest \
  backend/tests/unit/test_workspace_recovery.py \
  backend/tests/unit/test_tracking.py \
  backend/tests/unit/test_tracking_models.py \
  backend/tests/unit/test_workbench_http.py \
  backend/tests/integration/test_shadow_tracking.py \
  backend/tests/unit/test_experiments_r4.py \
  backend/tests/unit/test_execution_r4.py \
  backend/tests/unit/test_submit_gate.py \
  --deselect=backend/tests/unit/test_experiments_r4.py::test_real_workflow_has_only_insufficient_or_unsupported_results \
  --deselect=backend/tests/unit/test_experiments_r4.py::test_synthetic_end_to_end_has_models_fills_rejections_and_artifacts \
  --deselect=backend/tests/unit/test_experiments_r4.py::test_same_research_replays_reproducibly \
  --junitxml=data/local-operation-review/20261029-legacy-null-binding/focused.xml
```

One initial frontend invocation named a nonexistent `app.test.cjs` and exited 1 before
running tests; its [diagnostic](frontend-missing-path.log) is retained. `node --test` on the
correct file reported only a [single file wrapper](frontend-wrapper.log), so it is not used
as evidence of 12 named checks. The direct invocation above executes all 12 and passes.
No test, policy, risk cap, credential or supervisor
control was changed. No exchange request, real order, source backfill or profitability
claim was added. Checks run in the existing virtualenv; no new clean-install claim.

The earlier supported managed Chromium installer succeeded, but its single recorded launch
failed at `third_party/crashpad/crashpad/util/linux/socket.cc:45` with
`setsockopt: Operation not permitted (1)` and SIGTRAP before page/listener interaction.
The prior complete suite stalled at `test_collector_reconnects_with_new_session_and_can_restart`
and hit its 120-second deadline (exit 124). [Original failures and artifacts](../README.md)
remain unchanged; neither attempt was repeated in this correction. No new screenshot,
real-listener workflow or complete-suite pass is claimed. The executable
[`frontend/browser/recovery.spec.cjs`](../../../frontend/browser/recovery.spec.cjs)
remains the browser acceptance harness.

The outstanding supervisor/human step is to run the default
[`tools/local_acceptance.py`](../../../tools/local_acceptance.py) in an environment
permitting managed Chromium, localhost sockets and the existing asynchronous tests. Inspect
its actual screenshots, trace, downloads and fresh-cycle/restart/cancellation evidence,
and obtain a complete-suite pass. Then independently cross-check
[`docs/v1_acceptance.md`](../../../docs/v1_acceptance.md). Empirical validation, certified
fees, authorized provider evidence and validated second-family support remain unresolved.
