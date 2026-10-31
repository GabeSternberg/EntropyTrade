# Continuous forward validation

Start the existing private website with `.venv/bin/entropytrade-web --workspace data/cache/workbench`.
Freeze and select a retained weather dataset. In **Continuous forward validation**, choose
a retry interval and dates per batch, check the explicit opt-in and click **Enable forward
validation**. Nothing is scheduled by default. This uses the existing read-only label service;
there is no order transport, credential lookup or model promotion.

A schedule can cover more than eight dates. Each request fetches at most eight source dates
and shares one response among matching stations on that date. Future dates wait until every
selected station's local day has ended. Source failures, missing/invalid reports and preliminary
reports stay visible and retry with exponential backoff from the chosen interval, capped at
one day. Official reports are revisited daily for corrections. A verified date means every
selected event on that date has a source-matched scalar label; it does not certify exchange
settlement, model accuracy, eligibility or profit. Earlier official receipts remain available
when a later check fails.

**Also enroll new retained public and shadow weather inputs** is a separate, default-off
option. It scans one existing bounded history partition (at most 128 captures/outcome cycles)
per retry interval, rotating through all partitions. It verifies existing receipts, freezes
a new immutable snapshot with available labels, and enrolls unseen event/rule selections.
It never starts a shadow monitor or acquires market data. Enable the existing shadow workflow
separately if new market/forecast receipts should accrue. New shadow cycles on a growing
partition are incorporated at its next scan; a pinned-only schedule handles its selected
dataset without following later inputs. Neither mode rewrites an existing snapshot.

The table shows pending, retry, verified and permanently refused dates, attempts, next checks,
source errors, the active batch ID and controls. **Pause forward validation** cancels a queued
or active request and retains earlier receipts. **Resume** reuses durable backlog state.
The process must remain running for scheduling; closing the browser has no effect. Normal
server shutdown cancels network activity, writes an interrupted batch and stops the thread.
A normal restart honors the persisted opt-in and retries unfinished dates after reconciliation
and backoff. It cannot recreate a completed request under a new ID after a bookkeeping crash.
Request selection is rechecked under the service lock before claiming. A queued request paused
in that interval cannot start; registering ownership and marking running happen together.
Pause/shutdown also cancels the interval before acquisition starts, without waiting for the
event loop's callback. Stale completion cannot replace interrupted or other terminal evidence.

At most eight schedules and 2,048 event/rule targets per schedule are supported. The workspace
guard stops at 128 acquisition requests to preserve the existing 128-batch reader budget.
Exhaustion blocks scheduling with an explicit
operator message, retaining its plan, receipts and backlog. Preserve/snapshot the workspace
and review partitioning before continuing; pause/resume cannot bypass the budget. Network
requests still have fixed destinations, no credentials/cookies/redirects, a 2 MB body cap,
15-second request timeout and a 120-second batch deadline. These limits are not risk limits.

**Download forward validation state** preserves pinned target versions, attempts, request and
batch references and opt-in/pause/resume history. **Download label evidence** retains exact
source bytes and receipt clocks. The existing workspace snapshot/restore commands include
both. Offline validation checks schedule hashes and source/request/batch references and
reparses scalar evidence without network, fitting or changing timestamps. Starting the app
on a restored *active* schedule honors the earlier opt-in; pause before export for an offline
inspection session. Publication/revision clocks missing from the provider stay unknown.
Known-at-the-time feature joins, frozen calendars and protected research exclusions remain
in force, including when a protection is added after scheduling.

Reproducible acceptance uses Playwright-managed Chromium through actual localhost listeners:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/forward-validation-review/NEW-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW-forward-validation" \
  npm --prefix frontend/browser test -- forward-validation.spec.cjs --max-failures=1
```

Use fresh paths. The controlled procedure labels its twelve-date source, clock, outages,
preliminary/official/revised responses and results as software evidence. The authentic
procedure imports original whole shadow cycles without retiming them and makes new public
source requests using real receipt clocks. Its sparse labels or failures cannot establish
empirical fitting or returns. Both procedures inspect the website, pause/restart, download
state, restore offline and compare reopened browser downloads. The pytest checks additionally
exercise active shutdown with a partial batch, crash windows, protections and request identity.
See [executed evidence](../data/forward-validation-review/20261031/README.md); discovery alone
never constitutes browser acceptance. V1 remains incomplete.

The [atomic-claim correction evidence](../data/forward-validation-review/20261031-atomic-claim/README.md)
adds deterministic two-thread barriers for the selection/claim and ownership/startup intervals.
The controlled browser procedure also pauses at a test-only startup barrier, inspects the
interrupted request with zero source receipts and verifies identical evidence after restart
and offline restore. The authentic procedure retains original clocks and makes new public
read-only requests; controlled cancellation is software evidence, not empirical performance.
