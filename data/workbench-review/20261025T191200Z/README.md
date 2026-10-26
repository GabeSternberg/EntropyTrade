# Acceptance continuation — 20261025T191200Z

Reviewed commit: `99e2fbc1b54d6af426496b3effbe7c47255650bd`, tree
`9c0cb3a82666def58d75594a13e3bd62fe906b63`. The designated branch was initially clean.
This attempt repairs a job-database deadlock discovered during acceptance, adds a bounded
concurrency regression, reconciles evidence/current documentation and restores
`PROJECT_CONTEXT.md`. The two-file code fix is uncommitted. No Git mutations or new product
features were made.

**Browser gate: blocked. V1: incomplete.** [Browser observations](browser.json) record no
connected browser sessions, “Computer Use was not approved to use Google Chrome” and
“Browser is not available: iab.” All four documented browser workflow groups remain
unexecuted. Browser job IDs, screenshots and browser downloads are empty. No browser or
permission workaround was attempted. Return for review with this blocker.

## Commit-bound automated verification

[Clean-export checks](clean-root/checks.json) retain commands, UTC start/end clocks,
exit codes, exact environment, Python pin and log hashes. The [export manifest](clean-root/export-manifest.json)
binds all 2,268 exported files to the reviewed commit. A read-only `git archive` export,
not a Git checkout operation, produced a root-level isolated copy. All exported files remained unchanged during baseline checks. The later candidate
overlay changes exactly two Python files and has a separate full manifest and source patch. A new virtual environment was populated from locked
dependencies using a repo-local clone of the existing uv cache; no credential access or
network package download was needed. No independent Git checkout or supervisor sign-off
is claimed. The temporary root export is removed after verification; manifests/logs persist.

- `uv lock --check`, `uv sync --locked` and installed entry-point help pass.
- Ruff lint and format inspect all 477 files; strict mypy checks 477 source files.
- The [ordinary sandbox full check](clean-root/make-check.log) records 728 passing tests
  and five failures caused by `PermissionError` from localhost socket binding.
- The listener-capable full rerun uses normal per-command approval and the same source,
  dependencies and environment: [receipt](listener-check.json), [full log](make-check-listeners.log).
  All three listener tests passed, then the baseline stalled with the main and queue threads
  in native SQLite close mutex waits. It was sampled and terminated; this is a failed gate.
  The first automatic review timed out; the explicitly permitted retry was approved.
- [JavaScript syntax](clean-root/javascript-syntax.log) and all nine
  [Node presentation tests](clean-root/frontend-check.log) pass, with zero skips.

The [stack sample](pytest-sample.txt) records the stalled native calls. The acceptance fix
serializes each Jobs connection's open/use/close across in-process threads/instances;
independent workers retain SQLite's transaction locks. A bounded four-thread regression
exercises 1,600 real connection cycles and terminal-state preservation, passing in 1.09s.
[Candidate checks](candidate-checks.json), the [source patch](candidate.patch) and
[candidate manifest](candidate-manifest.json) bind the full rerun to this uncommitted
candidate, rather than falsely attributing it to the reviewed commit. A ten-minute outer
process-group deadline bounds another stall. The fixed candidate completes the full
unchanged `make check`: Ruff lint/format, strict mypy across 477 files and **734 pytest
tests in 155.88 seconds**; JavaScript syntax and all nine Node presentation tests pass. No test, warning policy, risk cap or application permission was relaxed. The ordinary
sandbox failures remain recorded; approval for localhost tests does not grant browser access.
The [approval record](listener-approval.json) distinguishes the review timeout from execution.

Earlier local verification failures are retained: [interpreter discovery](interpreter-discovery/checks.json),
[empty cache](empty-cache/checks.json) and [ignored-directory export](ignored-cache-export/README.md).
The last run caused Ruff to skip files, was explicitly rejected as lint evidence, and was
replaced with the root-level export above. These attempts never establish a passing gate.
UTC clocks are retained as observed, including commands crossing into October 26 UTC;
pytest elapsed durations are reported separately rather than inferred from UTC subtraction.

## Retained workflow evidence

All 197 pre-existing receipt checksums passed before documentation changes; the
[verification log](retained-bundle-checksums.log) preserves that result. The
[revalidation receipt](retained-evidence.json) and [script](verify_retained.py) verify five
historical reviews and all 51 workflow artifacts against retained workspaces. They verify
public manifests and dataset/feature identities, validation-only probabilities, excluded
holdout, synthetic negative-control zero fills, unresolved Bitcoin settlement gates,
acquisition failure clocks, report summaries, original job IDs and HTTP export hashes.
The original inputs and receipt directories are unchanged.

Retained lifecycle evidence verifies a running synthetic job was cancelled during modeling,
a following recorded job completed, active/pending jobs became interrupted after restart,
and review/report exports remained identical. This is revalidation of earlier HTTP and
worker evidence, not new browser execution. No fresh public acquisition was claimed.
Neither family's forward captures establish historical probabilities or returns.

## Handoff

Current docs identify the committed implementation and the exact remaining V1 gates.
[Acceptance](acceptance.json) separates automatic checks, retained HTTP evidence and
unexecuted browser steps. [Handoff](handoff.json) records final source/document hashes and
unchanged commit identity. Once an approved browser is available, run every step in
[the documented procedure](../../../docs/workbench.md#browser-acceptance-procedure), retaining
UTC clocks, job IDs, screenshots and checksummed browser downloads. The supervisor must
verify the final reviewed commit from a clean checkout with locked dependencies and full
checks before integration. All Git operations remain the supervisor's responsibility.
