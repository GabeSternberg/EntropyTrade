# Continuous paper/shadow operator alerts

The private website's **Continuous shadow tracking → Operator alerts** shows durable
incidents across all monitors, including paused monitors. Each incident links to its
monitor, exact cycle IDs or overdue contracts, detection clock and lifecycle. The monitor's
**Shadow evidence JSON** includes the same incident history. Existing simulated accounts,
source receipts, model/fee refusals and execution risk checks remain inspectable below it.

| Condition | Opens when | Recovery evidence |
| --- | --- | --- |
| Stale collection | An active monitor has no healthy committed collection for three poll intervals plus the existing 240-second worker budget (420 seconds at a 60-second interval). Creation is the baseline before the first healthy cycle. | A fresh healthy committed collection. Pausing suppresses new freshness incidents and preserves existing incidents. |
| Repeated failures | Three failed or explicitly incomplete collections since the last healthy collection. Interrupted workers and legacy cycles without collection metadata do not erase the streak. | A healthy committed collection. Resuming or resetting the existing backoff counter cannot clear an incident. |
| Unresolved reconciliation | A frozen tracked contract remains without an official binary outcome one hour after its original close time. This also applies to paused monitors. | The existing receipt/terms-validated worker commits the subsequent outcome. A missing outcome is never inferred from price or an elapsed clock. |

A healthy collection has a complete universe, no acquisition/outcome failures and no
initial/later execution-capture failures. Missing fitted models, certified fees or statistical
evidence remain honest decision refusals; they are not worker failures by themselves.
The existing five-failure automatic pause and all risk caps are unchanged.

**Acknowledge alert** records operator review once, under the existing same-origin/CSRF
boundary. An acknowledged incident remains visibly open. Recovery adds a separate resolution
event; the next occurrence gets a new ID and needs its own acknowledgement. There is no
manual resolve, order submission, fee certification or model promotion action here.

SQLite stores incident state and append-only lifecycle events in the same transaction as
cycle commits. Retry acknowledgement is idempotent and monitor scoped. Startup recovers
interrupted cycles and evaluates conditions; the runner also checks every five seconds
without requiring a browser or a due cycle. API polling evaluates conditions as well.
Detection/acknowledgement/resolution clocks are operator clocks, never historical source
availability. When the server is stopped, evaluation resumes on startup; this milestone
does not provide an external notification service.

Full monitor exports preserve incidents. Existing offline workspace snapshot/restore also
preserves and validates their references, chronology, acknowledgement/resolution transitions
and unique open incidents. Older workspaces migrate without inventing historical alerts,
models or paper fills. A newly detected legacy problem receives today's detection time.
Stop the server before maintenance; the existing workspace lease refuses simultaneous writes.

## Acceptance in a permitted environment

The [Playwright operator procedure](../frontend/browser/alerts.spec.cjs) uses managed
Chromium and actual localhost servers. It inspects all three alerts, acknowledges through
the page, downloads evidence, restarts the listener, verifies identical downloads, checks
controlled recovery/recurrence, snapshots/restores offline and compares reopened downloads.
The separate [two paper procedures](../frontend/browser/paper.spec.cjs) inspect controlled
synthetic accounting and authentic original-receipt refusal, including account/shadow
downloads, restart and offline account replay. Controlled health/outcome signals prove
operator software only. Authentic inspection must continue to show missing models/fees
and zero fills; no new authentic acquisition or empirical profitability is asserted.

From the repository root, use new workspace and evidence paths for every run:

```bash
npm ci --prefix frontend/browser --ignore-scripts --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  npm --prefix frontend/browser run install:chromium

stamp=$(date -u +%Y%m%dT%H%M%SZ)
env -i PATH="$PATH" TZ=UTC \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" \
  ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/operator-readiness-review/$stamp/browser" \
  ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/operator-browser-$stamp" \
  node frontend/browser/node_modules/@playwright/test/cli.js test \
  -c frontend/browser/playwright.config.cjs paper.spec.cjs alerts.spec.cjs --max-failures=1
```

Run `make check` and `node frontend/tests/acquisition.test.cjs` separately. A launch/listener
denial is a failed or unexecuted acceptance step. Test discovery, HTTP doubles and offline
replay cannot establish browser/download acceptance. Retain JSON/JUnit, traces, screenshots,
download hashes and listener logs. See the [executed evidence](../data/operator-readiness-review/20261031/README.md)
for this environment's precise results and outstanding checks. V1 remains incomplete.
