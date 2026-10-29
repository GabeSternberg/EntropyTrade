# Frozen model to continuous shadow integration — October 29, 2026

This is an implementation milestone on the designated `supervisor/20261029-120832`
checkout, based on `e8b7402`. The integration changes and initial receipts were already
present when completion verification resumed. All changes are left for supervisor
review; no branches, commits, merges or pushes were performed. **V1 is incomplete.**

## Delivered behavior

New weather modeling runs export checksummed, data-only JSON for climatology, raw
forecast and forecast-error distributions and supported Platt/isotonic calibrators.
The monitor resolves the executed StrategySpec, verifies the unique server-produced
export against its model reference and freezes its parameters in SQLite. Removing the
original artifact cannot replace or retrain that monitor. No executable deserialization,
model upload, live fitting or promotion is exposed. Legacy/missing/unsupported models
produce explicit refusals. Bitcoin forward model scoring remains unsupported.

Each bounded cycle retains authentic features and up to ten sized public books, plus
versioned series fee responses. The decision follows the final receipt; original feature
availability stays intact and hours-to-close is recomputed. The fixed-point YES/NO bids
use the established complement mapping and exact string quantities. Fractional strike
tickers are supported. Deferred contracts are explicit. Fee metadata is **uncertified**:
its type/multiplier does not establish the quadratic coefficient or effective interval,
so no fee policy is invented and no actual collected intention is approved.

Model identity, fit/calibration clocks, training-series scope, feature schema/version,
exact market/strike/rule identity, requested calibration and protected event boundaries
gate probabilities and decisions. Decisions reuse the existing deterministic DSL, risk
caps, conservative fee-inclusive reservations, durable controls, failure recovery and
official outcome linkage. Earlier decisions and raw evidence remain unchanged when a
later outcome arrives. All exports keep `submission_enabled=false`, no fills and null
performance. No order transport or credential access is introduced.

## Executed acceptance evidence

| Requirement | Executed evidence and scope |
| --- | --- |
| Frozen model identity and restart | `test_monitor_freezes_resolved_identity_and_model_across_restart` removes the original export, reopens SQLite and scores the same frozen model. Hash/provenance/spec changes and ambiguous artifacts refuse. |
| Data-only scoring fidelity | Nine model/calibrator combinations compare JSON round-trip distribution probabilities with the original fitted model. These are controlled software fixtures, not empirical weather fitting. |
| Causal forward scoring | Parameterized refusals cover future fit/calibration, schema/version, missing features, wrong model/adapter/series, protected events, tampering and incompatible exact contract semantics. JSON replay preserves the result. |
| Sized read-only books and fee evidence | Controlled capture tests assert actual quantities, complement prices, retained hashes/receipt clocks and uncertified fee versions; 401/429/500 responses withhold books. Exact allowlist tests refuse unrelated destinations. |
| Reservations across cycles/restarts | New frozen-scoring tests and existing reservation/risk tests retain intentions through SQLite restart, enforce fixed exposure/size caps and release only after a received official outcome. No fills are inferred. |
| Failure and later outcome linkage | Multi-cycle integration tests retain partial evidence, reject late results after pause, reconcile later official results and verify unchanged original result bytes and decision replays. Existing worker termination/backoff/recovery tests remain intact. |
| Browser inspection and lifecycle | The fresh [completion browser receipt](completion/browser/shadow-browser-receipt.json), [Playwright report](completion/browser/playwright-results.json), trace and three screenshots record actual managed Chromium page interactions, a real listener and unmodified workers. Research → start → pause → download → server restart → identical download → resume → second cycle → download passed in 21.7 seconds, with zero page errors. |
| Authentic public acquisition | Each of the two completion cycles has 24 weather contracts, 648 observations, eight source receipts, ten sized books and eleven execution receipts (one series, ten books), no acquisition/execution failures and 14 explicitly deferred contracts. Both have 24 blocked decisions with no fitted probabilities or intentions. These are authentic forward receipts, not historical validation or profitability. |
| Offline reproducibility | [Completion verification](completion/browser-verification.json) checks screenshot/download bytes, identical paused/restarted downloads, cycle digests, every artifact hash, original raw receipts, source fingerprints and deterministic decision replay of both copied cycles. The original successful bundle also verifies. |
| Python quality gates | Completion Ruff lint/format and strict mypy pass (496 files). **971 pytest tests pass in 275.90 seconds, with zero failures, errors or skips**; see [full log](completion/pytest-full.log) and [JUnit evidence](completion/pytest-full.xml). |
| Frontend checks | All 12 named presentation tests and application/browser JavaScript syntax checks pass; see [permitted-run log](completion/frontend-permitted.log). The sandbox's earlier `frontend.log` reported only a file-level success and is not used as proof of all twelve cases. |

Tests live in [tracking model tests](../../../backend/tests/unit/test_tracking_models.py),
[tracking boundary tests](../../../backend/tests/unit/test_tracking.py),
[multi-cycle integration tests](../../../backend/tests/integration/test_shadow_tracking.py)
and [model workflow tests](../../../backend/tests/unit/test_model_workflow_r2.py).
The [machine-readable completion summary](completion/results.json) and
[source inventory](completion/source-sha256.json) bind the executed working-checkout
checks to 509 source, test, configuration and dependency-lock files. The verifier also
checks that inventory when verifying the completion case.

The current sandbox refused a single socket-creation preflight with
`PermissionError: [Errno 1] Operation not permitted`. The unchanged full suite and browser
were then run through the normal approval mechanism in a permitted execution context.
The supported `npm --prefix frontend/browser run install:chromium` command succeeded
before launch; see [installation log](completion/chromium-install.log). No sandbox policy,
event-loop behavior, test, timeout or risk cap was weakened. No denied browser launch was
repeated. Earlier denied launches in other bundles remain failures.

## Reproduction

Run the complete gates from the repository root with the provisioned locked dependencies
and permitted localhost/asyncio sockets. The completion full-suite command uses a clean
environment and a 900-second external deadline; the repository's tests remain unchanged:

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
env -i PATH=/usr/local/bin:/usr/bin:/bin TZ=UTC PYTHONNOUSERSITE=1 \
  PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  timeout 900 .venv/bin/pytest -q
node --test frontend/tests/*.test.cjs
node --input-type=module --check < frontend/src/app.js
node --check frontend/browser/shadow.spec.cjs
.venv/bin/python data/shadow-review/20261029-model-integration/verify_evidence.py
.venv/bin/python data/shadow-review/20261029-model-integration/verify_evidence.py \
  --case data/shadow-review/20261029-model-integration/completion --browser browser
```

For a fresh browser run, install the managed Chromium as in the
[procedure](../../../frontend/browser/README.md), then use new absolute evidence and
workspace paths with `--grep 'continuous shadow'`. The completion run used:

```bash
env -i PATH=/usr/local/bin:/usr/bin:/bin TZ=UTC \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/shadow-review/NEW/browser" \
  ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/shadow-browser-NEW" \
  node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs --grep 'continuous shadow'
```

The harness refuses reused workspaces and receipts. Copied `completion/real-cycles/`
directories preserve original raw and result bytes from the stopped browser workspace.
The verifier operates on those retained copies, without network access or changing clocks.

## Preserved attempts and remaining limits

`browser/` is the first lifecycle attempt: the page flow executed but both cycles exposed
a decimal-strike ticker parser rejection. This is failed acquisition evidence. The parser
was corrected, a regression added, and `browser-final/` then recorded two successful
cycles. `real-cycles/` contains those original successful cycles. Completion verification
preserves both earlier attempts and adds a fresh successful browser run and copied cycles.
The original `pytest-full.log` ends without a summary and is **incomplete**, not a pass.

Actual collected candidates still lack enough authentic source-matched fitting data.
Fees require reviewed effective evidence. No new real probability model or historical
validation is claimed. Ridge/boosting and Bitcoin frozen scoring, fairer depth scheduling,
later corrections to finalized outcomes, hosted operation, provider-backed credentialed
research and clean-install/final release acceptance remain separate work. Bitcoin's frozen
future validation boundaries are unchanged; another major family requires user approval.
No human browser step remains for this scoped procedure. Return this integration for
supervisor review before another major milestone.

The highest-impact remaining gap is authentic source-matched fitting evidence plus
reviewed effective fee evidence. While forward data accrues, a useful next reviewed
milestone is reproducible operating readiness: prove a locked clean installation,
documented startup/shutdown and workspace backup/restore, then execute the browser
lifecycle and complete suite against that installation. Acceptance should preserve
monitor model bindings, completed cycle bytes, reservations and paused/active recovery
states through restoration, with no submission activation. This is a proposal for review,
not authorization to start another phase or select another family.
