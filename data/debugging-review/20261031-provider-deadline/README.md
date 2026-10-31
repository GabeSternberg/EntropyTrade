# Provider deadline regression repair — October 31, 2026

This is a scoped debugging correction, not a V1 release or empirical validation.
All Git operations and independent review remain with the supervisor. Production
research timeouts, request/token/cost budgets, submission controls and risk limits
are unchanged. No credential, original source receipt or protected boundary was
changed. Only provider test support and provider regressions are repaired.

## Reproduction and cause

The original deadline fixture assigned 50 ms to the entire research pipeline and
then required a provider HTTP request. Agent/schema setup runs inside that budget;
expiry before the first request correctly produces a saved `TimeoutError` with
zero requests. The old fixture's HTTP assertion was timing-dependent.

The original isolated check passed in 4.28 seconds with normal local runtime
permissions. Adding a controlled 100 ms delay to agent construction reproduced
the exact reported `assert calls` / `assert []` failure in 4.79 seconds before
repair. [The reproduction log](reproduced.log) and [JUnit](reproduced.xml) retain
that failed check. Reproduction command, after adding the delayed-setup regression
and before changing the wire fixture:

```bash
UV_CACHE_DIR=/tmp/entropytrade-debug-uv-cache uv run --offline --no-sync pytest \
  'backend/tests/unit/test_workbench_provider.py::test_provider_job_runs_typed_research_then_deterministic_experiments_or_saved_failure[deadline-True]' \
  -vv --junitxml=data/debugging-review/20261031-provider-deadline/reproduced.xml
```

## Repair and regressions

The controlled stalled-HTTP case now captures the real `asyncio.Timeout` installed
by the pipeline and calls its public `reschedule()` method at the first HTTP
request. It expires immediately and cancels an unresolved response future. The
transport asserts that the deadline actually expired; it does not raise a fake
`TimeoutError`, replace the production timeout, extend a production limit or return
a fabricated successful response. The configured outer deadline remains 180 seconds.
The test-only factory wrapper delegates to the original factory and is scoped to
that case. It is restored with the provider-model patch on exit.

The ordinary and delayed-setup stalled-HTTP cases still require exactly one HTTP
request and an actual saved `TimeoutError`. A separate delayed-setup case uses an
unmodified real 50 ms timeout and requires **zero** HTTP requests. All deadline cases
require no completed response/stage, no experiments/probabilities/final holdout,
unchanged saved failure bytes after recovery and an available worker guard.
Success, outage, malformed-output, pricing refusal and credential-isolation checks
remain enabled.

## Executed verification

- [Focused provider/transport/operational/pricing tests](focused.log): **64 passed
  in 9.52 seconds**; [JUnit](focused.xml).
- [Ruff](ruff.log), [backend format](format.log): pass, 535 files formatted.
- [Strict mypy](mypy.log): pass, 535 source files.
- [Exact frontend check command](frontend-direct.log),
  `node frontend/tests/acquisition.test.cjs`: **22 named checks pass**.
- [Managed Chromium provisioning](chromium-install.log): supported Playwright
  `install chromium` command succeeds using the existing repository installation.
- [Real provider browser procedure](browser.log): **1 passed in 44.8 seconds**, with
  **8 screenshots, 14 hash-verified downloads and zero page errors**, including actual
  opt-in/form/tabs, pricing/outage refusal, active cancellation, listener restart,
  identical reopened downloads and missing-key failure. The [report verification](browser-verification.json)
  checks its exact identity, successful execution records/counts and all artifact hashes;
  it explicitly retains the other five required procedures as unexecuted.
- [Original receipt and boundary checks](safety-receipt.json): all 68 original
  receipts and five Bitcoin boundary files match the prior safety hashes.
- [Complete pytest suite](full-suite.log): **1,210 passed in 532.60 seconds**,
  process exit 0, no failures or skips; [JUnit](full-suite.xml). This includes the
  repaired ordinary/delayed transport deadlines and the real startup deadline.

[Source/configuration hashes](source-hashes.json) identify the tested provider code,
browser procedure and dependency configuration. [The verification summary](verification.json)
records executed results and explicitly incomplete release scope. The focused cases are
included in the complete-suite count, not additional tests.

The full command is `UV_CACHE_DIR=/tmp/entropytrade-debug-uv-cache timeout
--signal=INT --kill-after=15s 900s uv run --offline --no-sync pytest
--junitxml=data/debugging-review/20261031-provider-deadline/full-suite.xml`.
Stdout/stderr are retained in [full-suite.log](full-suite.log).

Browser execution uses the unchanged `provider.spec.cjs` and managed Chromium
through a real localhost listener. Its clean environment contains only PATH, UTC,
a short `/tmp`, the managed browser path and fresh repository evidence/workspace
paths. `ENTROPYTRADE_BROWSER_PORT=43254` avoids concurrent suite listener ports.
The case controls provider HTTP; it never accesses an external provider or real
credential. [Browser log](browser.log), reports, trace, screenshots and downloads
are retained under [browser/](browser/).

## Runtime and remaining scope

The first ordinary `uv run` could not write `/home/gabriel/.cache/uv`; subsequent
commands use a writable `/tmp` cache and the existing locked environment without
syncing dependencies. The initial restricted regression stalled and was interrupted
(exit 130). The existing capability probe confirmed `PermissionError(1, 'Operation
not permitted')` for localhost socket creation and socketpair send. Local runtime
execution then used the supported `require_escalated` approval path, which was
approved. No sandbox, socket implementation or launch policy was patched or bypassed.
The original restricted-runtime observation is retained in [restricted-environment.json](restricted-environment.json).
The denied Chromium launch was not repeated in the restricted execution context.
The early sandbox `node --test` result in `frontend.log` reports one file, not the
22 named checks; only `frontend-direct.log` is used as frontend acceptance evidence.

This is not a fresh installation or the six-procedure operating-acceptance driver.
V1 remains incomplete. Other current browser procedures, clean-install operating
acceptance, separately authorized external-provider evidence, sufficient authentic
model/backtest data, certified effective fees, two-family empirical validation and
independent supervisor release review remain outside this correction. Preserve
authentic forward collection and optional Bitcoin work with frozen boundaries;
another major market family requires user approval.
