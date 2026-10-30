# Provider pricing refusal — October 30, 2026

Correction from supervisor checkpoint `194fbe9` on the existing designated branch
`supervisor/20261029-141757`. All Git writes remain with the supervisor. No external
credentials, real orders, execution activation, risk-cap changes or new market family.
V1 remains incomplete.

## Behavior and regression evidence

The old post-stage cumulative-cost check let an unpriced first tool response proceed
through **five** requests and experiment setup. Running the new first-response regression
against the old implementation reproduced `assert 5 == 1`. This was controlled OpenAI
HTTP through the actual PydanticAI adapter, not an external provider session.

The new non-streaming model wrapper checks every individual response before PydanticAI
dispatches tools, validates outputs, retries, merges suspended continuations or advances
research stages. A prior known cost cannot mask missing pricing. Refusal is sticky and
persists a sanitized `ResearchPricingError`, stage, response identities, receipt timestamps,
token usage and individual prices. The cumulative cost on a failed unpriced run is only
the known subtotal. Finite explicit zero prices remain accepted. The existing $2,
request/token/tool/deadline limits and credential/holdout boundaries remain in force.

Seven end-to-end regressions cover unpriced tool calls, malformed structured output and
valid output as the first response or after a priced response, plus refusal in the next
stage. They count actual controlled HTTP requests, verify zero experiments/probabilities,
preserve downloaded review bytes after restart and check that the refused tool never runs.
Seven additional boundary cases cover suspended continuation segments, sticky refusal,
explicit zero/positive cost and negative/nonfinite cost.

During development, the first implementation run had seven failures because the explicit
website projection omitted the new pricing evidence; that projection was corrected. The
next focused run passed 37/38 cases: FunctionModel replaced an entirely zero usage record
in the zero-price fixture. Giving that fixture nonzero token counts preserved its explicit
zero price. The final full suite passes all 1,047 cases, including all 14 new regressions;
see `pytest.log`/`pytest.xml`. Earlier development results are not represented as passes.

## Executed browser checks

The supported `npm --prefix frontend/browser run install:chromium` procedure succeeded
using the existing pinned Playwright installation and managed Chromium under
`frontend/browser/.browsers/`; no system Chrome or personal browser profile.

Both actual localhost procedures passed, with zero retries, skipped cases or page errors:

| Procedure | Duration | Screenshots | Downloads |
| --- | ---: | ---: | ---: |
| Provider opt-in, typed candidates, failures, cancellation/restart | 41.8 s | 8 | 14 |
| Research, snapshot/restore, shadow lifecycle and recovery | 57.0 s | 5 | 11 |

Provider HTTP replies are controlled only in the test-only listener/worker. SQLite jobs,
worker subprocesses, PydanticAI serialization, deterministic experiment gates, UI clicks,
all three tabs and downloads use the actual app. Pricing failures are inspected through
the UI and their JSON bytes match after restarting an unmodified credential-free server.
That server also persists `ResearchCredentialError` with zero requests. The broader
recovery procedure uses the established operating harness.

The first-pricing failure has one request, 100 input/100 output tokens, no tool dispatch
and unknown cost. The second-pricing failure has two requests, 200 input/200 output tokens,
one earlier priced tool dispatch and a **$0.00020 known subtotal**, with the second price
unknown. Both have null experiment IDs and no candidates. See
`pricing-artifact-verification.json`, the original downloads/screenshots in `browser/`,
and the checksummed raw research copies in `research/`.

Reproduction from this repository, using a **new** evidence path/workspace each time:

```bash
env -i PATH=/usr/bin:/bin TZ=UTC TMPDIR=/tmp \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/provider-review/NEW/browser" \
  ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW" \
  ENTROPYTRADE_BROWSER_PORT=43218 \
  timeout 240s node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs \
  --grep 'provider-backed website|local operation and recovery'
```

## Quality gates and environment

Ruff lint, Ruff format check (507 files), strict mypy (507 source files) and all 15
frontend presentation cases pass in the existing repository virtual environment.
The complete configured Python suite passes **1,047 tests in 338.02 seconds**, with zero
failures/errors/skips, a 600-second external deadline and no test deselection. See
`pytest.xml` and `pytest.log` for exact case results.
`verification.json` records final results and hashes of the reviewed implementation/tests.

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
node frontend/tests/acquisition.test.cjs
env -i PATH=/usr/bin:/bin TZ=UTC OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  timeout 600s .venv/bin/pytest --junitxml=NEW/pytest.xml
```

The initial sandboxed regression stalled; a credential-free diagnostic failed at
`socket.socketpair()` with `PermissionError: [Errno 1] Operation not permitted`. The
stalled test was interrupted. Subsequent controlled tests and Chromium/listener procedures
used the normal approved execution mechanism with socket permissions, a clean environment
and no inherited credentials. No permission policy, browser flags, event loop or assertion
was changed. There was no denied Chromium launch and no repeated denied socket attempt.

These results are current-environment software acceptance, not a new clean installation,
external provider access or empirical strategy validation. The previous clean-install
bundle remains separate. No human browser step remains for these two executed procedures.
Separately authorized external-provider verification, authentic fitted/outcome coverage,
certified effective fees, two-family empirical validation and independent V1 acceptance
remain outstanding. Return this correction for supervisor review before any next milestone.
