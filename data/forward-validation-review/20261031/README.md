# Continuous forward validation — October 31, 2026

Implemented in place on `supervisor/20261031-054650` from `9d9f921`. No Git mutations,
supervisor-control edits, credentials, order submission, risk-cap relaxation or new family.
**V1 remains incomplete; independent supervisor review is required.**

The existing website can explicitly enable a persistent forward-label schedule for a selected
immutable dataset. At most eight dates are acquired per request. Preliminary reports and
outages retry with bounded exponential backoff; verified dates receive daily revision checks.
A separate opt-in follows retained public/shadow history one existing bounded partition at a
time, freezes new immutable snapshots and enrolls unseen event/rule selections. It does not
start a shadow monitor or collect market data. Source availability and frozen research/model
boundaries are unchanged. See [operating guide](../../../docs/forward-validation.md).

Plans are saved before request creation. Before-enqueue, active-network and after-acquisition
interruptions reconcile using the same request identity. Pause cancels queued/active work;
restart honors earlier opt-in and preserves receipts/backoff. Offline workspace validation
checks the schedule digest, immutable target identity and completed request/batch references.
The finite 128-acquisition budget blocks for operator review, retaining the unpublished plan
through pause/restart; resume cannot bypass the budget. No receipt or snapshot is deleted.

## Executed browser evidence

The final [Playwright report](browser-verified/playwright-results.json) and
[log](browser-verified.log) execute both procedures through real localhost listeners using
repository-local Playwright-managed Chromium. There are **10 screenshots, 6 browser downloads,
4 byte-identical reopened/restored comparisons and zero page errors**. Downloads and screenshots
are independently [hash-checked](browser-hashes.json).

- [Controlled receipt](browser-verified/controlled/browser-receipt.json): twelve simulated dates
  split into eight/four date batches. Actual form interaction verifies explicit opt-in,
  preliminary backlog, outage/backoff, official reports and revisions, progress, pause/resume,
  insufficient-data freeze, shutdown/restart, offline snapshot/restore and identical paused
  downloads. Source HTTP and scheduling/receipt clocks are controlled in a test-only listener.
  These are **software checks, never authentic history or empirical performance**.
- [Authentic receipt](browser-verified/authentic/browser-receipt.json): import two original whole
  shadow cycles without retiming; freeze, opt in to following, acquire new public Weather
  Company reports, inspect honest gaps, pause, download, restart and restore offline with
  identical state downloads. No source response or clock is overridden in this procedure.
  New receipts verify the two October 29 station/day highs (Philadelphia 70 °F, Chicago 69 °F),
  and refuse both October 30 preliminary reports. Publication/revision clocks absent from the
  provider remain null. Availability starts at the NEW receipt, never the target date.

The authentic receipt embeds exact new source bytes, headers, rule bindings and parser results.
Its snapshots still report insufficient data: four independent events on two dates, two
source-matched scalar labels. No fitted empirical model, probabilities, fills, returns or
profit is established. Multi-day unattended authentic scheduling has **not** been observed;
future retry/revision transitions are controlled acceptance evidence.

The [first attempt](browser-attempt-1/playwright-results.json) failed because the new harness
expected machine status `insufficient_data` while the existing page renders “insufficient data.”
That failure/trace stays unchanged; assertions were corrected to the existing visible text.
[Attempt 2](browser-attempt-2/playwright-results.json) passes. Browser inspection then showed
the new backlog cramped in the sidebar. It was moved to the wide results area, with
[final layout acceptance](browser-final/playwright-results.json) passing. The verified run
executes the final backend after the storage-boundary correction; earlier successful runs
retain their earlier source scope. No denied browser launch was repeated.

## Quality and safety evidence

- [Ruff](ruff.log), [format](format.log), [strict mypy](mypy.log): pass, 546 backend source/test
  files. [Frontend](frontend.log): all 22 named checks pass by direct Node execution.
- [Final focused log](focused-final.log), [JUnit](focused-final.xml): **44 passed in 29.31s**.
  These cover twelve-date fairness, preliminary/official/revised reports, outage backoff,
  authentic shadow discovery, automatic unseen-date enrollment, immutable boundaries,
  newly protected targets, opt-in/scope limits, unsafe links/corruption, active cancellation
  with a partial receipt, before/after-enqueue recovery, blocked-budget pause/restart,
  same-origin/CSRF, real listener restart and byte-identical offline restore.
- The initial focused collection found a Python 3.12 runtime annotation error for
  `threading.Lock | None`, corrected with deferred annotations. The retained
  [next attempt](focused-attempt-2.log) passes 38 cases and fails one test setup assumption:
  each authentic capture already contains both dates. The assertion was corrected to the
  actual retained data; a separate controlled enrollment test verifies genuine new-date
  discovery. [Focused pre-boundary checks](focused.log) pass 42 cases in 26.83s. Earlier
  failures are not represented as passes.
- [Final full-suite log](pytest-verified.log), [JUnit](pytest-verified.xml): **all 1,271 tests
  pass in 553.51s**, with zero failures, errors or skips. This run includes the final
  storage-boundary correction and both added regressions. The earlier
  [1,269-case run](pytest-full.log) also passes in 572.18s, but predates those final changes
  and retains its earlier scope. The final full run executes alone after the browser runs.
- [Acceptance receipt](acceptance.json): all scoped implementation checks pass; V1 remains
  `complete=false`, with independent supervisor review pending. [Source fingerprints](source-hashes.json)
  verify 566 implementation/test/frontend/configuration files. [Read-only checkpoint audit](checkpoint-audit.json)
  finds no changed/untracked checkpoint candidate over 8 MB; nothing is staged.
- [Safety receipt](safety-receipt.json): all **68 original receipt files and five Bitcoin
  boundary implementation/manifest files** match the prior verified baseline.
- [Locally retained generated artifacts](retained-artifacts.json): original traces and workspace
  archives remain at their original paths under a scoped ignore policy. A checkout alone
  lacks those bytes; obtain/hash-verify them separately for independent trace/restore review.
  Reports, receipts, downloads, screenshots and manifests remain reviewable. Nothing is deleted.

The [restricted probe](socket-capabilities.json) fails at `socket()` with
`PermissionError: [Errno 1] Operation not permitted`; its socketpair step is not reached.
The standard approval path permits
localhost and asyncio, and is used for actual listener/browser/full-suite checks. No sandbox
setting, browser security flag, timeout, assertion or risk limit was weakened. The supported
managed-Chromium installation passes in the existing repository cache; no new clean install
is claimed. Prior locked installation acceptance retains its previous scope.

## Reproduction

```bash
.venv/bin/ruff check backend/src backend/tests
.venv/bin/ruff format --check backend/src backend/tests
.venv/bin/mypy
node frontend/tests/acquisition.test.cjs
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -vv
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/forward-validation-review/NEW-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW-forward-validation" \
  npm --prefix frontend/browser test -- forward-validation.spec.cjs --max-failures=1
.venv/bin/python data/forward-validation-review/20261031/verify_evidence.py
```

Use fresh evidence/workspace paths and an environment permitting actual browser/listener
execution. Hash verification is read-only and cannot substitute for executed acceptance,
source authenticity or empirical evaluation. Final release still requires enough authentic
independent history, certified effective fees, separately authorized provider verification,
two-family empirical evidence and independent acceptance. Another major family requires
user approval. This milestone is returned for review; no next phase starts.
