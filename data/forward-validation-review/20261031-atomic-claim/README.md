# Atomic request claiming and cancellation — October 31, 2026

Corrected in place on designated `supervisor/20261031-054650` from `2f93999`.
All Git operations and independent review remain with the supervisor. **V1 remains incomplete.**
No supervisor controls, credentials, real orders, execution activation, risk caps, authentic
receipt clocks, protected boundaries or market-family selection were changed.

## Correction and deterministic regressions

The worker previously selected a queued dictionary outside the lock, registered ownership
without changing its durable status, and let acquisition unconditionally mark that copy
running. A pause could finish the queued request between selection and claiming, or between
registration and acquisition, then have its interrupted evidence replaced by the worker.

`LabelService.bounded` now reloads durable state under the service lock. Only queued work
can be claimed; registration and the running transition share that critical section.
`cancel` records intent synchronously as well as scheduling task cancellation, so startup
cannot proceed merely because the event loop has not yet delivered the callback. Acquisition
requires the registered task and checks durable status, cancellation and shutdown before
creating the HTTP client. `finish` refuses to replace terminal evidence. Ownership is released
on completion, cancellation, timeout and failure. Existing tests now enter through the same
bounded ownership/deadline path as production, retaining their original assertions.

Six new cases in [the lifecycle tests](../../../backend/tests/unit/test_label_lifecycle.py)
use two-party barriers rather than timing sleeps:

- Pause after queue selection but before claiming: zero acquisition starts and identical
  interrupted request/batch bytes. Completed and failed states receive the same checks.
- Pause or shutdown after registration but before startup: assert running status and active
  ownership together, then deliver cancellation without an asyncio yield. Zero source calls;
  interrupted evidence survives repeated cancellation, stale claiming, late completion and
  restart reconciliation.
- Repeated claiming cannot replace a running task's ownership; normal completion still
  acquires the two controlled source dates exactly once.

[Focused log](focused.log) and [JUnit](focused.xml): **50 passed in 30.09s**, including the
lifecycle, scheduling, partial-receipt shutdown, label/source and actual-listener tests.
The final complete-suite execution includes the subsequent test-only browser barrier helper.

## Executed browser regression

[Final Playwright report](browser-verified/playwright-results.json) and
[log](browser-verified.log): **both procedures pass in 61.85s**, through actual localhost
listeners with Playwright-managed Chromium. There are **11 screenshots, 6 browser downloads,
4 byte-identical reopened/restored state comparisons and zero page errors**.

- [Controlled receipt](browser-verified/controlled/browser-receipt.json): retains the original
  twelve-date preliminary/outage/official/revision workflow. A new cross-process test-only
  barrier holds startup after ownership registration. Actual page interaction pauses the
  running request; it becomes interrupted with zero source receipts. Browser inspection
  sees the interruption; exact request/result equality is checked after server restart and
  offline snapshot/restore. Existing twelve-label freeze and honest model insufficiency
  assertions remain. These sources and clocks are explicitly controlled software evidence.
- [Authentic receipt](browser-verified/authentic/browser-receipt.json): imports original whole
  shadow cycles without retiming and performs new public read-only source acquisition. It
  verifies two October 29 scalar highs and refuses two October 30 preliminary reports.
  Availability starts at the new receipts; missing publication/revision clocks stay unknown.
  Sparse history remains insufficient for empirical fitting, returns or profitability.

The [first attempt](browser/playwright-results.json) was intentionally interrupted after
the new cancellation check: the added scenario had already paused the schedule, while the
old final step waited for another Pause button. Exit status was 130; the report records one
interrupted test and one unexecuted test. Its partial receipt still says `running` and has no
finish timestamp; it is **not a pass**. Its screenshot, trace, report and partial receipt are
retained unchanged. The final harness avoids the duplicate pause, uses atomic barrier-file
publication, and adds interrupted-request equality after restart/restore. Fresh paths were
used for the successful rerun. No denied browser launch was repeated.

## Quality, provenance and limitations

[Ruff](ruff.log), [format](format.log) and [strict mypy](mypy.log) pass (547 backend files).
[Frontend checks](frontend.log) pass all 22 named checks. The final full suite passes
**all 1,277 tests in 555.99s**, with zero failures, errors or skips, in
[pytest.log](pytest.log), [JUnit](pytest.xml) and [acceptance.json](acceptance.json).
The original 68 receipt files and five Bitcoin boundary files match the
[previous safety baseline](safety-receipt.json).

[Source hashes](source-hashes.json), [browser hashes](browser-hashes.json),
[local artifact inventory](retained-artifacts.json) and the verification receipt bind this
correction to its source and evidence. Trace/workspace ZIP bytes remain locally retained
under the existing scoped ignore policy; obtain and verify those bytes separately for
independent trace/restore review from a fresh checkout. Hashes establish byte identity, not
authenticity, empirical adequacy or successful execution by themselves.
The [read-only checkpoint audit](checkpoint-audit.json) finds no staged paths or eligible
candidate above 8 MB. Eight generated local files totaling 53,784,457 bytes, including the
interrupted trace, remain ignored and retained at their original paths; nothing was deleted.

The [sandbox probe](socket-capabilities.json) reports `PermissionError(1, 'Operation not
permitted')` at localhost socket creation and socketpair send. Focused/full pytest and actual
browser/listener checks use the standard approved tool path for socket access. The supported
[Chromium installation](chromium-install.log) succeeds using the existing repository cache.
No sandbox setting or browser security option was changed. The existing environment was
reused; no new clean-install result is claimed.

This correction has no outstanding browser-interaction step. Independent supervisor review,
multi-day unattended authentic operation, enough independent point-in-time history, certified
effective fees, separately authorized external-provider verification and two-family empirical
release evidence remain open. No V1 completion or performance claim is made.

## Reproduction

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
node frontend/tests/acquisition.test.cjs
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -vv \
  backend/tests/unit/test_label_lifecycle.py backend/tests/unit/test_label_schedule.py \
  backend/tests/unit/test_weather_labels.py \
  backend/tests/integration/test_weather_labels_listener.py \
  backend/tests/integration/test_forward_validation_listener.py
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/forward-validation-review/NEW-atomic-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW-atomic-browser" \
  npm --prefix frontend/browser test -- forward-validation.spec.cjs --max-failures=1
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -vv
.venv/bin/python data/forward-validation-review/20261031-atomic-claim/verify_evidence.py
```

Use fresh evidence/workspace paths in an environment permitting localhost/browser execution.
Execute the browser and full suite sequentially. Return this single correction for review;
no next phase or Git mutation is authorized here.
