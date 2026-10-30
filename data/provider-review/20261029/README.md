# Provider research website milestone — October 29, 2026

Implemented from `9dff058` on designated `supervisor/20261029-141757`. No Git mutation,
supervisor-control edit, real credential access, external provider request, order or risk
change. **V1 remains incomplete.** This bundle is for independent supervisor review.

The existing PydanticAI evidence/hypothesis/quant/critic pipeline now runs through website
jobs and the existing deterministic experiment engine. Operator provider/model configuration
and fresh per-job consent are both required. Configuration is frozen in the request;
ordinary research and shadow workers remain credential-free. Failed research is durably
inspectable/downloadable without an experiment or mock fallback. Restart never silently
repeats billable work. Original data/settlement/holdout boundaries remain unchanged.

## Executed checks

- [Locked setup/browser receipt](locked-final/acceptance.json): exact commands, step clocks,
  source hashes and package inventory; its original one-failure suite report is preserved.
  Fresh offline installation from `uv.lock` and
  `frontend/browser/package-lock.json`. Only package artifacts and Playwright-managed
  Chromium were seeded; no virtualenv or credentials were reused.
- Ruff lint/format, strict mypy over 505 files and all 15 frontend presentation cases pass.
- [Final browser log](locked-final/browser.log) and [JSON report](locked-final/browser/playwright-results.json):
  both actual Playwright-managed Chromium procedures pass against real localhost listeners.
  Provider procedure: 49.2 seconds; broader recovery: about 1.2 minutes. Final source and
  receipts provide exact durations. No Computer Use, personal Chrome or HTTP page stubs.
- [Provider browser receipt](locked-final/browser/provider-browser-receipt.json): controlled
  provider HTTP yields three typed hypotheses and honest deterministic insufficiency from
  the original six-event real weather dataset. All result tabs, report/JSON downloads,
  redacted outage, active cancellation, interruption and identical reopened bytes pass.
  A second **unmodified** listener without credentials yields `ResearchCredentialError`
  with zero requests. Test-only provider transport is never an external-provider pass;
  production exposes no endpoint/worker/response-injection switch.
- [Recovery browser receipt](locked-final/browser/recovery-browser-receipt.json): synthetic
  probabilities, recorded real insufficiency, authentic shadow collection, pause/resume,
  offline snapshot/restore, active-cycle recovery, cancellation and restart. Collected
  evidence remains model/fee blocked; no observed fills or performance claim.
- [Provider offline verification](provider-offline-verification.json): 56 original files and
  jobs/registry logical rows match after the installed CLI snapshot/restore. Statuses remain
  completed, failed, cancelled, interrupted, failed. Unit tests separately verify pending
  consent recovers interrupted without retry. [Provider snapshot](provider-workspace.zip)
  and [broader recovery snapshot](recovery-workspace.zip) retain actual artifacts.
- [Complete suite](complete-suite/receipt.json), [JUnit](complete-suite/pytest.xml) and
  [console log](complete-suite/pytest.log): **1,033 passed in 373.42 seconds; zero failures,
  errors or skips**. The final run uses the same newly installed locked environment after
  restoring the two omitted original fee-citation documents. Application/test/fee code is
  unchanged; earlier driver receipts remain failed. The unchanged collector reconnect case
  passes within this complete suite. Focused passes never substitute for this full result.
- [Aggregate verification](verification.json) and [source comparison](source-comparison.json):
  all 1,474 final source/input hashes match checkout and installation after execution.
  All 11 current screenshots and 19 browser downloads match their receipt hashes; both
  browser receipts have zero page errors.
- [External provider check](external-provider-check.json): **BLOCKED**, no separately
  authorized research credentials. No real key was inspected or external provider called.

Controlled Python tests additionally exercise genuine OpenAI/PydanticAI serialization,
malformed output, HTTP outage, deadline, missing key, explicit consent/schema refusals,
key isolation and failed-research restore. These prove software behavior, never actual
provider availability, empirical fitting or profitability.

## Diagnoses and retained failed attempts

The retained collector reconnect stall is reproducible in the sandbox. See
[baseline stack](diagnostics/collector-baseline.log), [minimal executor stall](diagnostics/async-executor.log)
and [socketpair denial](diagnostics/socketpair.log): creation succeeds, send raises
`PermissionError: [Errno 1] Operation not permitted`, so asyncio cannot wake for a completed
executor task. The [approved credential-free diagnostic](diagnostics/approved-sockets.log)
prints `wake` and `executor-complete`; focused unchanged collector checks pass through
normal approved execution. No loop policy, test assertion or sandbox rule was changed.

The [first locked driver](locked/acceptance.json) remains **failed**. Its browser launch
crashed before interaction under a deeply nested TMPDIR. The [path diagnostic](diagnostics/temporary-path.log)
records a 122-byte Unix socket address rejected as `AF_UNIX path too long`, versus a
72-byte short-root bind that passes. Changing only the temporary root made both installed
browser procedures pass in [separate artifacts](locked/browser-short-temp/playwright-results.json).
The corrected driver creates/cleans a short `/tmp/entropytrade-*` root; durable evidence
stays inside this repository. No browser flags were relaxed and no denied launch was
repeated as a workaround.

The first full export also omitted original public inputs/research documents used by
existing tests: **207 failed, 820 passed, 6 errors in 341.96 seconds**.
[The explicit missing-fixture case](locked/missing-fixture.log) identifies the absent
`data/public/amsterdam/manifest.json`. Other failures likewise reflect missing stored
public rows/docs/databases. The driver now exports `data/public`, `docs/research` and the
original project specification unchanged. Tests and fixture values were never weakened.
The second fresh driver passed setup, static/frontend and both browser checks, then
reported **1 failed, 1,032 passed in 386.18 seconds**: the existing fee test cites
`.agents/skills/kalshi-docs/api-reference/market/get-series.md` indirectly through a module
constant. The explicit export had omitted this reference too. [The repair receipt](export-repair.json)
records adding the original series and rounding documents and synchronizing only the
driver export list, before rerunning all tests in that locked installation. No supervisor
control/skill instruction file was exported or changed; no fee coefficient was certified.
The final manifest separately records all additions. Both earlier failed receipts remain
intact; the aggregate result references the successful supplemental full-suite run.

The early controlled test harness also had a duplicate `run_id` argument and a reversed
restore call; their failed logs remain under `diagnostics/`, followed by corrections.

## Reproduce

From the repository root in an environment permitting normal local sockets and managed
Chromium, with `uv`, Node/npm and Python 3.12+ installed:

```bash
python3 tools/local_acceptance.py --output data/provider-review/NEW-NAME
```

For the exact offline provision used here, add package/browser artifact seeds:

```bash
python3 tools/local_acceptance.py --output data/provider-review/NEW-NAME \
  --uv-cache-seed data/local-operation-review/20261029-final-source/uv-cache \
  --npm-cache-seed data/local-operation-review/20261029-final-source/npm-cache \
  --chromium-seed frontend/browser/.browsers --test-seconds 900
```

All output/workspace paths must be new. Installation/cache directories are ignored source
artifacts and retained locally; logs, fingerprints, screenshots, traces, downloads and
workspace archives remain durable review evidence. The snapshots contain private research,
are not authenticated third-party archives, and require the normal trusted local restore
path. Run no external provider check without separately authorized research credentials.

No outstanding human page-interaction step remains for these scoped browser procedures.
External provider authorization/checking and independent supervisor review are still
required. Real fitting/source-matched outcomes, effective fee certification and empirical
two-family validation remain incomplete; preserve Bitcoin dates and select no new family.
