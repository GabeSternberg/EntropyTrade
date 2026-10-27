# Real workbench browser acceptance

This harness automates all four procedures in `docs/workbench.md` against the actual
loopback HTTP server, durable queue and isolated research workers. It clicks the form,
tabs, details, downloads, cancellation and saved history. It stops/restarts its own server
and compares every completed run's browser downloads before and after restart.
It does not use Computer Use, personal Chrome, a saved browser profile, CDP, response
stubs, direct job submissions or replacement data. Application and safety code is unchanged.

From the repository root, with locked Python dependencies already installed:

```bash
uv sync --locked
npm ci --prefix frontend/browser --ignore-scripts --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium

stamp=$(date -u +%Y%m%dT%H%M%SZ)
env -i PATH="$PATH" TZ=UTC \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/workbench-review/$stamp/browser" \
  ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/workbench-browser-review-$stamp" \
  ENTROPYTRADE_BROWSER_DENY_PUBLIC=1 \
  node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs
```

The pinned npm lockfile and Playwright-managed Chromium are independent of Python's
application dependency lock. Chromium is installed only under the ignored `.browsers/`
directory. The configuration explicitly launches that executable in headless mode with
a fresh browser context. Both the evidence receipt and Playwright results record outcomes;
JSON/JUnit reports, traces, screenshots, DOM text, real run files and browser downloads
remain in the selected evidence directory. Existing receipts/workspaces are refused.
The server uses a credential-free environment allowlist. Port 43128 must be free; override
it with `ENTROPYTRADE_BROWSER_PORT`. Override the Python interpreter with an absolute
`ENTROPYTRADE_BROWSER_PYTHON` if the environment is elsewhere.

The optional `ENTROPYTRADE_BROWSER_DENY_PUBLIC=1` test requires macOS `/usr/bin/sandbox-exec`.
After the normal weather/Bitcoin captures, the harness restarts the real backend with OS
outbound connections denied. A new Bitcoin request must produce timestamped connection
failures, zero fabricated HTTP receipts/data and visible incomplete summaries on all three
tabs and its text download. The fault is explicitly labeled and never counts as successful
ingestion. The harness then restores normal backend execution before lifecycle testing.
On another OS, omit this variable; failure-path coverage is recorded as unexecuted unless
an actual fresh capture fails. A denied installer, browser launch or listener remains a
failure, with its exact error in logs/results; do not skip it or substitute HTTP-only tests.

Each workflow has a recorded outcome. Acquisition completeness is checked separately from
worker completion; partial public capture leaves workflow 3 failed while subsequent
lifecycle checks still execute. Calibration timestamps may be null for uncalibrated model
outputs; present calibration clocks and all fit clocks must precede the decision. All
exposed predictions must be validation records, and protected final holdout must remain
excluded. Synthetic results prove software behavior only. No V1 or trading approval follows
from this test. Run the unchanged full Python/frontend gates separately before review.

No commits, ref changes, merging or pushing are performed by this harness.
