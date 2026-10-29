# Source-workspace leases and actual listener recovery — October 29, 2026

Implemented from `99ba77a` on designated `supervisor/20261029-124902`. No Git writes,
supervisor-control changes, credential access, risk changes or real orders. **V1 complete=false.**
Return this scoped correction for supervisor review; no next major phase is started.

The verifier previously constructed `Jobs` and `TrackingStore` before cache validation or
the lease, which could initialize or migrate its source. It now enters `snapshot_lease`,
requiring an existing source under `data/cache/` and a schema/evidence-validated snapshot
before constructing stores. That context keeps one source lease through snapshot,
inspection and comparison, without nested acquisition. A separate restored lease covers
initialization, comparisons, startup recovery and replay. The existing `snapshot()` API
uses the same context. The CLI is a thin wrapper around the strictly typed/tested module.

Nine new regressions verify busy, missing, empty, out-of-cache and unmigrated source refusal
before any store initialization; unchanged authoritative database bytes; leases during
snapshot validation, inspection, comparison and recovery; busy destination refusal and
exception-path release. SQLite may create runtime WAL/SHM during a read-only backup of
an existing valid WAL source; those are distinguished from database creation/migration.
All 34 existing corruption, lineage, legacy NULL, frozen-model, reservation and inherited
worker-lease recovery checks also pass.

## Executed checks on final unchanged source

[`verification.json`](verification.json) retains all commands, exit codes, timestamps and
643 source-file hashes. All source files remain unchanged during the gate. It fingerprints
application/tests/tools/frontend/config/vendor/bundled data and locks; documentation is
updated after checks. [`junit-summary.json`](junit-summary.json) cross-checks all 13 JUnit reports:
**311 passed, zero failures/errors/skips, three named R4 workflows explicitly deselected.**
The post-documentation [source comparison](source-comparison.json) also matches; retained
artifacts have a separate [checksum inventory](checksums.json).

| Check | Executed result |
|---|---|
| [Ruff](ruff.log), [format](format.log), [strict mypy](mypy.log) | Pass; 505 formatted files and 502 configured source/test files. |
| [Frontend](frontend.log) | All 12 named assertions pass. Presentation checks, not browser interactions. |
| [Source-proof regressions](unit__test_recovery_proof.log), [JUnit](unit__test_recovery_proof.xml) | 9 pass; no denied source can initialize/migrate stores, and both leases cover the required operations. |
| [Existing recovery regressions](unit__test_workspace_recovery.log), [JUnit](unit__test_workspace_recovery.xml) | 34 pass. |
| [Existing process workflows](integration__test_workbench_process.log), [JUnit](integration__test_workbench_process.xml) | All 6 unmodified real worker checks pass. |
| [Existing workbench listeners](integration__test_workbench_listener.log), [JUnit](integration__test_workbench_listener.xml) | All 3 cases pass, including actual recorded/synthetic workers, downloads, cancellation and restart. |
| [Existing Bitcoin history listener](integration__test_bitcoin_history_listener.log), [JUnit](integration__test_bitcoin_history_listener.xml) | Pass. Explicitly controlled history fixtures; not empirical Bitcoin validation. |
| [New recovery listener](integration__test_recovery_listener.log), [JUnit](integration__test_recovery_listener.xml) | Pass in 23.1 seconds with real ephemeral localhost HTTP, unmodified research/shadow subprocesses and no response/clock/worker doubles. |
| [Corrected authentic offline proof](../20261029-leased-authentic-final/verification.json) | Pass using the earlier retained workspace: 114 identical original evidence files, identical logical database rows/paused exports and both original 24-decision replays. No new source receipts in this offline proof. |

The other focused files cover tracking, frozen models, HTTP boundaries, controlled multi-cycle
outcomes, deterministic experiments/execution and submit refusal. The existing R4 workflows
`test_real_workflow_has_only_insufficient_or_unsupported_results`,
`test_synthetic_end_to_end_has_models_fills_rejections_and_artifacts` and
`test_same_research_replays_reproducibly` are explicitly deselected in this focused gate;
they are not presented as passing. Existing real worker/listener synthetic research paths
do execute in their separate processes. The full suite is unverified.

## Actual listener artifacts

[`listener-recovery/evidence/receipt.json`](listener-recovery/evidence/receipt.json) and
[`listener-recovery/workspace`](listener-recovery/workspace) retain the actual restored
workspace, original partial bytes, fresh raw receipts, capture/execution versions and
decision inputs. Original runtime paths in receipts are retained verbatim; these links
are the durable copied locations after the temporary test workspace is removed.

The test completes recorded real research and downloads JSON/text; completes and pauses
a real shadow cycle; observes a second monitor's real subprocess directory before shutdown;
snapshots/restores; verifies every restored manifest hash before startup; compares actual
restored research and paused-monitor HTTP bytes; inspects interrupted-cycle identity and
frozen binding; resumes through real controls; collects a fresh cycle; cancels an actual
running synthetic research worker; interrupts another request and restarts again. Paused
exports remain byte-identical across both restarts. Recorded/synthetic classifications and
holdout boundaries stay intact. Completed decisions also pass deterministic replay.

The restored active monitor's original cycle is **interrupted**, with its original ID/clock
and partial bytes retained. Its new cycle completes with **24 real contracts and 648
observations**, no acquisition/execution failures, ten sized books and uncertified fees.
All model-blocked decisions retain null predictions and intentions. Fills are empty,
performance is null, and submission remains disabled. This verifies forward collection
and durable operation; it establishes no fitted empirical model, certified fee or profit.

Actual [original paused download](listener-recovery/evidence/paused-original.json),
[restored paused download](listener-recovery/evidence/paused-restored.json),
[second-restart download](listener-recovery/evidence/paused-restarted.json),
[active recovered export](listener-recovery/evidence/active-recovered.json),
[review](listener-recovery/evidence/review.json),
[restored review](listener-recovery/evidence/review-restored.json),
[report](listener-recovery/evidence/report.txt),
[restored report](listener-recovery/evidence/report-restored.txt),
[manifest](listener-recovery/evidence/snapshot-manifest.json) and
[archive](listener-recovery/evidence/workspace.zip) are retained. No browser screenshot or
page interaction is implied by these HTTP downloads.

## Reproduction, earlier attempts and outstanding acceptance

```bash
python3 tools/recovery_gate.py --output data/local-operation-review/NEW-ISOLATED-REVIEW
```

Use the existing locked virtualenv and an environment permitting actual localhost sockets.
Each pytest file has a separate process/deadline; failures/timeouts retain logs and fail
the gate. The script sanitizes its child environment and uses no credential configuration.
It does not launch Chromium, retry the stalled complete suite or claim a new clean install.

The [earlier gate attempt](../20261029-leased-source-attempt-1/verification.json) passes all
311 tests but fails strict mypy on two extracted-verifier typing issues. Its full logs and
source fingerprints are preserved. The final source fixes the annotation and redundant
guard and retains actual restored download variables. The initial sandbox listener attempt
failed three cases at socket creation with `PermissionError: [Errno 1] Operation not
permitted`; its [observation receipt](../20261029-leased-source-attempt-1/sandbox-observation.json)
distinguishes the observed tool output from a raw log. Both gate runs then use the normal
approved execution mechanism; no sandbox or test policy is bypassed. Disposable pytest
temporary copies are excluded from durable evidence; listener workspaces/downloads remain.

The prior managed Chromium launch denial and complete-suite collector stall remain
unchanged and were not repeated. The executable Playwright recovery harness still needs
the supervisor/human to run `tools/local_acceptance.py` in a permitted environment and inspect
actual screenshots, trace, page interactions and complete-suite results. See
[`docs/local-recovery.md`](../../../docs/local-recovery.md) and
[`docs/v1_acceptance.md`](../../../docs/v1_acceptance.md). Empirical fitting/outcomes,
certified fees, authorized provider evidence and validated second-family support remain
explicit V1 gaps. Bitcoin validation boundaries are unchanged; no new family is selected.
