# Local operation and recovery — October 29, 2026

**Implemented; browser/full-suite acceptance incomplete; V1 complete=false.**
The latest [source-lease and actual-listener correction](20261029-leased-source-final/README.md)
passes 311 tests in 13 isolated files (three named R4 workflows deselected), static/frontend
checks and exact-source verification. Actual unmodified workers restore identical downloads,
preserve an interrupted shadow cycle, collect a fresh authentic cycle and verify cancellation/
restart. The corrected offline proof also preserves 114 original evidence files, logical rows
and both 24-decision replays. Browser/full-suite acceptance remains outstanding; the unchanged
denied launch and stalled suite were not retried. Earlier evidence below retains its scope.

The subsequent [legacy SQL NULL binding correction](20261029-legacy-null-binding/README.md)
passes 291 focused tests, including 34 recovery cases, and static/frontend checks. It
preserves the outstanding browser/full-suite acceptance steps; the evidence below predates
that correction.

Work stayed on designated `supervisor/20261029-124902` from `70cbc7a`. No Git mutation,
real orders, credential access, risk-cap change, source backfill or new market family.

[Artifact checksums](checksums.json) cover the retained receipts, reports, archives and
traces; copied installations/caches are excluded from versioned evidence.

The maintenance API/CLI snapshots consistent jobs and lineage SQLite plus all run/shadow
bytes under the exclusive server/worker lease. It verifies member paths/types/size budgets,
checksums, schema/integrity, references/lineage, frozen bindings and cycle digests before
publishing a new workspace. No existing archive/workspace is overwritten. Restarts retain
paused states and reservations and use fresh cycles for active monitors. Opaque serialized
models are copied without executing them. See [operation](../../docs/local-recovery.md)
and [acceptance matrix](../../docs/v1_acceptance.md).

## Executed results

| Evidence | Executed result and scope |
|---|---|
| [Final-source locked setup](20261029-final-source/acceptance.json) and [117-package inventory](20261029-final-source/installed-packages.log) | `uv lock --check --offline`, `uv sync --locked --offline`, npm's pinned offline install and the supported managed Chromium installer pass in a new environment. Package caches/browser distribution were copied explicitly; no pre-existing virtualenv, browser profile or credentials reused. This `--prepare-only` receipt deliberately reports browser/full suite unverified. |
| [Final source comparison](20261029-final-source/source-cli-fixed-comparison.json) | All 642 exported files match the current tree after the CLI correction and its regression, the named frontend invocation and README refresh. Dependency locks did not change. Original setup/source receipts remain intact. |
| [Final Ruff](20261029-final-source/ruff-current-source.log), [format](20261029-final-source/format-current-source.log), [strict mypy](20261029-final-source/mypy-current-source.log), [frontend](20261029-final-source/frontend-current-source.log) | Pass. Ruff checks backend and maintenance tools (501 files formatted); mypy checks 499 configured backend/test files. All 12 named frontend assertions pass through direct invocation of the existing test file. JavaScript syntax checks pass. |
| [Focused pytest log](20261029-final-source/focused-current-source.log) and [JUnit](20261029-final-source/focused-current-source.xml) | **280 pass, 3 explicitly deselected, 19.63s.** Includes all 23 new recovery cases, CLI subprocess round trip, controlled frozen models, nonempty reservations/risk boundaries, orphan-worker lease, corruption/incomplete evidence/registry and directory/manifest budget rejection, multi-cycle official outcomes, deterministic experiment/execution and submission tests. The three workflow cases excluded by name are recorded below; no complete-suite pass is claimed. |
| [Authentic restore in the fresh installation](fresh-authentic-current-source/verification.json), [manifest](fresh-authentic-current-source/snapshot-manifest.json), [restored export](fresh-authentic-current-source/restored-monitors.json), [archive](fresh-authentic-current-source/workspace.zip), [CLI result](20261029-final-source/authentic-cli-fixed-restore.log) | Pass offline. The original one-run/one-paused-monitor/two-cycle archive restores through the installed CLI; 114 non-database files and all logical database rows match. Both 24-decision cycles reproduce identically. The original October 29 receipts remain unchanged; no new capture is represented as having happened. Real probabilities, intentions, fees or profitability are not inferred. |
| [Initial offline authentic proof](authentic-verified/verification.json) | Direct API snapshot/restore also passes on the original stopped workspace. `authentic-workspace.zip` is an earlier successful smoke snapshot. These do not pass browser acceptance. |

The final focused command runs the recovery, tracking, tracking-model, workbench HTTP,
shadow integration, R4 experiment, R4 execution and submit-gate files. It explicitly
deselects `test_real_workflow_has_only_insufficient_or_unsupported_results`,
`test_synthetic_end_to_end_has_models_fills_rejections_and_artifacts` and
`test_same_research_replays_reproducibly` in `test_experiments_r4.py`. Controlled wire data,
models and eligible intentions in these software checks are not empirical evidence. Actual
authentic cycles are model/fee blocked and have no probabilities/intentions/fills/returns.

## Failed or incomplete attempts retained

- [Uncached network installation](20261029-recovery-attempt-1/locked-sync.log) fails DNS
  resolution for `files.pythonhosted.org` while downloading locked `librt==0.16.0`.
  Its [receipt](20261029-recovery-attempt-1/acceptance.json) records failure; no pass implied.
- `20261029-recovery-offline-attempt-2` fails during cache setup with
  `ValueError: package cache link escapes artifact cache`. The guard incorrectly rejected
  an already rebased relative artifact link; it was corrected. No installed checks ran.
  That preliminary version wrote no receipt before cache setup; no log is invented.
- [Preliminary offline setup](20261029-recovery-offline-attempt-3/acceptance.json) installs
  and passes Ruff/format/mypy, then stalls after two architecture tests in the existing
  collector reconnect test. It was interrupted (tool exit 130). The original unfinished
  receipt and [separate interruption observation](20261029-recovery-offline-attempt-3/interruption-observation.json)
  are retained. Browser installation/launch did not run in that attempt.
- The full [gate attempt](20261029-recovery-final/acceptance.json) passes locked setup,
  static/frontend checks, pinned npm and Chromium installation. Its **single** Chromium
  [launch fails](20261029-recovery-final/browser.log) at
  `third_party/crashpad/crashpad/util/linux/socket.cc:45` with
  `setsockopt: Operation not permitted (1)`, then SIGTRAP. The browser fixture fails
  before test/page/listener setup. [JSON](20261029-recovery-final/browser/playwright-results.json),
  [JUnit](20261029-recovery-final/browser/playwright-results.xml) and the launch trace are
  retained. No new screenshot or browser workflow is claimed; no permission-denied launch
  is repeated or bypassed.
- That same attempt's [full pytest log](20261029-recovery-final/pytest.log) contains a
  45-second stack showing `test_collector_reconnects_with_new_session_and_can_restart`
  waiting in the event loop and an executor worker. The external deadline exits 124 at
  120 seconds after only two architecture tests. This stack does not itself prove the
  cause; no complete suite or current collector pass is claimed. Existing tests/policy
  were not changed. The attempt's directory name “recovery-final” does not make it final
  acceptance: its source export predates the later registry/CLI/harness refinements.
- The first installed authentic **CLI** check exposed an argument-order bug: restore
  passed workspace/archive positionally in reverse order and refused with
  `workspace must be a subdirectory of repository data/cache`. No destination was
  published. Keyword dispatch and a real subprocess CLI regression fix it. The earlier
  [278-test selection](20261029-final-source/focused-final.log) covered direct functions;
  the subsequent 279-test run includes the fix. The final 280-test run also checks directory
  and manifest budgets, followed by another successful authentic offline proof.
  Earlier logs are retained, and no failed result was rewritten.

## Outstanding supervisor/human acceptance

In an environment permitting the existing test loopback/asyncio behavior and managed
Chromium, execute:

```bash
python3 tools/local_acceptance.py --output "$PWD/data/local-operation-review/NEW-REVIEW"
```

Use cache-seed options from the operating guide if offline. Run the **default** driver,
without `--prepare-only`, and allow the complete suite its normal budget. It performs
actual page interactions through a real localhost server and fixed workers: synthetic
and recorded research/results, tabs/downloads, paused shadow, active monitor stop,
snapshot/restore, identical paused download, fresh active cycle, cancellation and another
restart. Inspect screenshots/trace/downloads, server/worker evidence and source clocks.
Real fitted binding and reservation behavior remains covered by controlled tests until
authentic fitting/fee inputs exist. Do not claim a current browser pass from old screenshots
or HTTP/DOM doubles. Independently review `docs/v1_acceptance.md` before approving this
milestone or release. All Git operations remain with the supervisor.

Empirical fitting/outcomes, fee certification, authorized provider evidence and a validated
second family remain incomplete. Bitcoin's original validation clocks stay frozen. Hosted
operation, broader serializers, structural scanning and new families are deferred.
