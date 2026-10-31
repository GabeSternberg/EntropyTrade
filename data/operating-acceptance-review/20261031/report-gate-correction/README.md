# Browser report completion correction — October 31, 2026

Implemented in place on `supervisor/20261031-014049` from `5e2bd03`.
**Operating acceptance and V1 remain incomplete.** The supervisor owns Git operations and
independent review. Existing evidence and source receipts are preserved.

The acceptance driver previously trusted zero process exits for discovery and execution;
its successful orchestration fixture emitted no Playwright reports. Completion now requires
discovery of six fixed file/title identities, separately discovered execution selection,
and actual passing results for every selected procedure in the JSON reporter output.
Nested suites are traversed. Global errors, missing/duplicate procedures, skipped or expected
failures, failed/interrupted/timed-out/flaky attempts, missing/empty results, malformed/absent
reports and inconsistent aggregate counts fail closed even when the process exits zero.
Execution must match selected discovery exactly. Report hashes and validation reasons are
retained in the receipt.

Full discovery always includes the required inventory, independently of `--browser-grep`.
A successful narrowed selection records `status="partial; required browser procedures
unexecuted"`, lists `unexecuted_browser_procedures` and keeps `acceptance_complete=false`.
Preparation also stays incomplete. An empty selection fails. A filter that actually selects
and successfully executes all required procedures can complete the browser coverage gate.
All other installation/quality/environment/suite gates still apply.

| Executed check | Result and evidence |
|---|---|
| Ruff lint | **Pass:** [command](ruff-command.json), [log](ruff.log); backend plus acceptance driver. |
| Ruff format | **Pass, 536 files:** [command](format-command.json), [log](format.log). |
| Strict mypy | **Pass, 535 files:** [command](mypy-command.json), [log](mypy.log). |
| Frontend assertions | **22 pass, none skipped:** [command](frontend-command.json), [log](frontend.log). |
| Focused pytest | **439 pass in 30.10s, zero failures/errors/skips:** [command](focused-command.json), [log](focused.log), [JUnit](focused.xml). Includes all 53 driver/parser cases and the previously applicable account/alert/risk/execution/replay/recovery/property checks. Fake child processes only verify driver contracts; they are not installation/browser evidence. |
| Actual full Playwright discovery | **Six procedures in five files:** [command](discovery-full-command.json), [log](discovery-full.log), [JSON](discovery-full/playwright-results.json), [JUnit](discovery-full/playwright-results.xml). `--list` executes no page interactions. |
| Actual narrowed discovery | **One alert procedure; five required procedures missing:** [command](discovery-partial-command.json), [log](discovery-partial.log), [JSON](discovery-partial/playwright-results.json). |
| Real report validation | [Results and hashes](report-validation.json): both new discovery reports parse; full discovery output is rejected as execution evidence. An unchanged historical successful weather report validates the execution schema only; the unchanged denied paper-launch report is rejected. Historical reports do not certify current-source browser workflows. |
| Source/evidence integrity | [Safety receipt](safety-receipt.json): all 68 original receipt files and five frozen Bitcoin boundary files match the earlier retained hashes. [Changed-source hashes](source-hashes.json) identify this correction. |

The regression cases cover complete and partial selection, partial preparation, full
coverage through a custom filter, zero-exit processes with absent/incomplete discovery or
execution reports, skipped/failed/empty results, environment refusal, browser-process failure,
source export compatibility and child credential exclusion. Existing tests and safety gates
remain enforced. Every early failure records unexecuted checks.

No browser launch, real localhost listener, socket-capability retry, fresh clean installation
or complete-suite retry was attempted for this correction. The existing environment denial
and full-suite stall remain documented in the [prior bundle](../README.md). No screenshots,
browser downloads, empirical returns, provider session or release pass is claimed here.

The outstanding operator/supervisor step is to run, in a permitted environment with
Playwright-managed Chromium and localhost/socketpair support:

```bash
python3 tools/local_acceptance.py --output data/operating-acceptance-review/NEW-NAME
```

Use a fresh output directory, the default full selection and no `--prepare-only`. Require
all six actual browser procedures, retained screenshots/traces/downloads and the complete
pytest suite, then independently cross-check the [V1 matrix](../../../../docs/v1_acceptance.md).
External provider, authentic empirical/model/fee and two-family release gates remain open.
No trading/risk/data-family functionality changed and no Git mutations were performed.
