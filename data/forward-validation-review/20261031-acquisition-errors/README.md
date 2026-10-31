# Durable acquisition-error finalization — October 31, 2026

Corrected in place on designated `supervisor/20261031-054650` from `5d5e893`.
All Git operations and independent review remain with the supervisor. **V1 remains incomplete.**

The actual acquisition loop retained its queued selection while `bounded()` reloaded and
updated a different request dictionary. After an acquisition or later receipt-save error,
the loop finalized that stale selection and replaced previously persisted receipts with an
empty batch. Error finalization now reloads the request from durable state. The existing
terminal guard still refuses to replace completed, failed or interrupted request/batch bytes.
Only already saved responses are claimed as retained evidence; an unsaved second response
does not become a historical receipt. No acquisition deadlines, retry budgets or risk caps change.

## Reproduction and regressions

[Original-path reproduction](reproduction.log) and [JUnit](reproduction.xml) retain **two
expected failures**: both actual-loop cases lose the first saved receipt on the old path.
The source correction was restored before all passing verification below. No production
evidence was altered for reproduction.

[Five new cases](../../../backend/tests/unit/test_label_acquisition_errors.py) run the actual
loop, real bounded ownership, controlled HTTP and receipt persistence. One raises an acquisition
error at the second date; another raises a transient `OSError` before the second receipt save.
Both compare exact first-receipt bytes and timestamps, creation and selection evidence,
immutable batches, scheduler reconciliation, restart and read-only workspace validation.
The saved date becomes verified while the unsaved date retries. Three further cases ensure
a late loop error cannot replace any of the three terminal statuses. These simulated source
reports and clocks are software evidence, never empirical history or performance.

[Regressions](regressions.log): **5 passed in 4.87s**.
[Focused verification](focused.log) and [JUnit](focused.xml): **55 passed in 30.96s**, including
the existing claim/cancellation barriers, scheduling, source/holdout refusals, shutdown and
real-listener restart/restore procedures.

## Executed browser acceptance

[Playwright report](browser/playwright-results.json) and [log](browser.log): **both procedures
pass in 69.85s**, using Playwright-managed Chromium through actual localhost listeners.
The bundle retains **13 screenshots, six downloads and zero page errors**. All four reopened
schedule-download comparisons are byte-identical.

- [Controlled receipt](browser/controlled/browser-receipt.json): the twelve-date procedure
  retains preliminary/outage/official/revised and startup-cancellation checks. Both new
  failure modes produce two partially retained failed requests each. The receipt embeds the
  first durably saved request before each error and its finalized state. Actual page
  interactions expose `failed`, the error and retained verified/refused counts. All four
  failed requests and all eight request/batch file hashes match after both listener restart
  and offline snapshot/restore. The interrupted startup request also remains unchanged.
  The [acquisition-error screenshot](browser/controlled/acquisition-error-retained.png) and
  [save-error screenshot](browser/controlled/second-receipt-save-error-retained.png) show the UI.
- [Authentic receipt](browser/authentic/browser-receipt.json): original whole shadow cycles
  are imported without retiming, followed by new public read-only source requests. This run
  verifies Chicago October 29 (69 F), Philadelphia October 29 (70 F) and Philadelphia
  October 30 (74 F); Chicago October 30 remains refused as preliminary/nonofficial. All
  availability starts at the new receipts, with absent publication/revision clocks unknown.
  These three labels remain insufficient for empirical fitting, returns or profitability.

The supported [Chromium installation](chromium-install.log) succeeds using the repository
cache. The [sandbox probe](socket-capabilities.json) records `PermissionError(1, 'Operation
not permitted')` for localhost socket creation and socketpair send. Tests and the browser
use the standard reviewed tool path for socket support. No browser security settings or
sandbox controls were changed, and no denied browser launch was repeated.

## Quality, safety and limits

[Ruff](ruff.log), [format](format.log) and [strict mypy](mypy.log) pass (548 backend files).
[Frontend checks](frontend.log) pass all 22 named checks. The complete suite passes
**all 1,282 tests in 556.02s**, with zero failures/errors/skips, in
[pytest.log](pytest.log) and [JUnit](pytest.xml).

All 68 original receipt and five Bitcoin boundary files match the
[previous safety baseline](safety-receipt.json). [Source hashes](source-hashes.json),
[browser hashes](browser-hashes.json), [documentation hashes](documentation-hashes.json)
and the [acceptance receipt](acceptance.json) bind this correction to executed evidence.
The [local artifact inventory](retained-artifacts.json) retains four original trace/workspace
archives totaling 51,848,261 bytes under the existing ignore policy. Those bytes remain
local-only; independent trace/restore review from a fresh checkout requires obtaining and
hash-verifying them. Hashes establish byte identity, not authenticity or empirical adequacy.

This correction has no outstanding browser-interaction step. Existing locked dependencies
and browser binaries were reused; no new clean-install result is claimed. Independent
supervisor review, multi-day unattended authentic operation, sufficient point-in-time history,
certified effective fees, separately authorized external-provider verification and two-family
empirical release evidence remain open. No new family, credentials, real orders, execution
activation, Git mutations, fabricated history or performance claims are included. Return this
same correction for review before another major milestone.

## Reproduction

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
node frontend/tests/acquisition.test.cjs
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -vv \
  backend/tests/unit/test_label_acquisition_errors.py backend/tests/unit/test_label_lifecycle.py \
  backend/tests/unit/test_label_schedule.py backend/tests/unit/test_weather_labels.py \
  backend/tests/integration/test_weather_labels_listener.py \
  backend/tests/integration/test_forward_validation_listener.py
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/forward-validation-review/NEW-error-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW-error-browser" \
  npm --prefix frontend/browser test -- forward-validation.spec.cjs --max-failures=1
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -vv
.venv/bin/python data/forward-validation-review/20261031-acquisition-errors/verify_evidence.py
```

Use fresh browser paths and run browser/full-suite checks sequentially with permitted local
socket access. Reproduction failures above were observed before the fix; do not revert working
production code or overwrite existing evidence to reproduce them.
