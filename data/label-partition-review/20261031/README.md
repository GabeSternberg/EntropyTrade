# Bounded immutable label partitions — executed milestone evidence

**V1 incomplete; independent supervisor review required.** Implemented in place on
`supervisor/20261031-073225` from `b62f9c6`, without Git mutations. Collection continues past
128 total requests through chained immutable partitions. See
[operation](../../../docs/label-partitions.md) and
[release matrix](../../../docs/v1_acceptance.md). No new family, credentials, submission
activation, real orders, risk-limit changes or supervisor-control changes are included.

## Controlled acceptance

[Focused JUnit](focused.xml) and [log](focused.log) pass **64 tests in 149.43s**. The new
service-level regression executes **260 controlled acquisitions** across request partitions
**128 / 128 / 4**, verifies exactly one source invocation per request, retains all 260 batch
versions and preserves original bytes/clocks through reopening. The rebuilt snapshot retains
all relevant versions, replays its audit, preserves the initial calendar/protected events and
counts only **one** independent scalar-label event. Its modeling status stays insufficient.

Other executed checks cover a crash immediately after seal publication, unchanged seal bytes,
reconciliation using the original schedule plan, busy-partition drain without blocking the
schedule, queued cancellation in the successor, source outage at the boundary, archived
idempotency/stale completion, and read-only offline validation. Corrupt requests/batches,
extra members, broken chains, unsafe selectors and symlinks fail closed. Existing partial
shutdown, cancellation races, failed-receipt retention, leakage and risk guards remain tested.

[Actual managed-Chromium report](browser-final/playwright-results.json) and
[execution log](browser-final.log) pass both selected procedures. The
[controlled browser receipt](browser-final/partition-controlled/browser-receipt.json)
records **130 unique scheduled requests** and [130 unique source calls](browser-final/partition-controlled/controlled-calls.jsonl):
129 completed batches, including one HTTP 503 outage, and one active cancelled acquisition.
Chromium enables the schedule, inspects progress/outage, selects the successor partition,
pauses acquisition, freezes a dataset with honest insufficiency, selects archived evidence,
downloads its seal/source batch and compares downloads after listener restart and offline
restore. No request is duplicated on reopening. All
[262 label-store file hashes](browser-final/partition-controlled/original-label-files.json)
match in both original and restored workspaces. Schedule, seal and archived-label downloads
are byte-identical across all three sessions.

The controlled procedure retains ten screenshots and nine downloads. These use explicitly
marked simulated source reports and accelerated clocks. The 260 service revisions and 130
browser batches prove software behavior; they do **not** prove elapsed authentic collection,
independent historical events, empirical fitting, returns or profitability.

## Separate authentic operating evidence

The [authentic browser receipt](browser-final/authentic/browser-receipt.json) imports
original whole shadow cycles without retiming them and performs a short newly opted-in source
acquisition with the real wall clock. Two public Weather Company HTTP 200 receipts were
received at **2026-10-31T11:51:08.121831Z** and **2026-10-31T11:51:08.208908Z**. Their original source bytes
remain in that receipt and the locally retained workspace archive. **Three station/day scalar
highs verify; one preliminary report is refused.** Missing provider publication/revision clocks
remain unknown and observation availability equals receipt time. This is authentic short-run
operating evidence, not 130 elapsed daily collections or adequate historical validation.

Chromium inspects source progress, pauses, freezes a dataset that still reports insufficient
data, restarts the actual listener, snapshots/restores offline and verifies identical reopened
schedule downloads. Four screenshots and three downloads are retained. Together both passing
procedures retain **14 screenshots, 12 downloads and zero page errors**. There is no outstanding
browser-interaction step for this scoped milestone. Multi-day authentic operation remains
unobserved; sufficient empirical history, fee certification, authorized provider verification,
two-family evidence and independent V1 acceptance remain open.

## Failures preserved and corrected

The initial development run was interrupted after 188.43s to replace repeated archived
inventory reopening with cached immutable metadata; [its log](partitions-development.log)
remains explicitly incomplete. Metadata caching still verifies file hashes on access and
full inventories during recovery. The next [service run](partitions-development-2.log) and
[first browser attempt](browser-attempt-1.log) both exposed **weather scalar label replay
audit mismatch** after successful rollover: construction used partition order while replay
used global batch-hash order. Canonical ordering in label assembly/partition enumeration
fixes this without relaxing replay checks. Failed reports, screenshots, requests and traces
remain at their original paths. The passing second attempt remains retained separately; final-browser execution repeats both
procedures after the last fail-closed fix.

The [initial restricted runtime](runtime-boundary.json) could not create localhost sockets; asyncio cross-thread
shutdown was also restricted. Supported Chromium installation succeeded from existing managed
binaries in [installation log](chromium-install.log). The actual tests/listeners/browser used
the standard reviewed tool path for socket support. No denied browser launch was repeated,
no browser security setting was changed, and mocked HTTP assertions are not presented as
Chromium acceptance.

A final review found that a missing terminal batch could be mistaken for an unpublished
request ID. The guard now distinguishes absent requests from damaged terminal evidence,
preventing refetch or duplicate publication. [Twelve integrity/lifecycle checks](integrity.log)
pass, with [JUnit](integrity.xml), including unchanged request bytes and the same blocked
schedule plan after batch loss. The earlier [full-suite log](pytest.log) stopped after
286 passes in 320.27s to run the completed guard; that interrupted run is not full acceptance.

## Quality, retention and limits

[Ruff](ruff-repository.log), [repository format](format-repository.log), [strict mypy](mypy.log) (551 backend files) and
[all 22 frontend checks](frontend.log) pass. Complete-suite execution is retained in
[pytest log](pytest-final.log) and [JUnit](pytest-final.xml): **all 1,292 tests pass in 679.34s**,
with zero failures, errors or skips.
The existing locked Python/npm environments were reused; this milestone makes no new
clean-install claim.

[Safety receipt](safety-receipt.json) verifies all 68 original receipt and five Bitcoin-boundary
files unchanged. [Local artifact inventory](retained-artifacts.json) verifies **213 files,
109,951,420 bytes**, including all three browser runs' trace trees and all passing procedures'
recovery archives. They remain local under scoped ignore rules. A checkout includes reports,
source bytes and hashes, not those ignored trace/archive bytes; independent trace/restore review
requires obtaining and hash-verifying them. Hashes establish byte identity, not authenticity or
empirical adequacy. The evidence verifier also requires the retained original/restored controlled
workspaces to recheck all 262 label-store hashes.

Each partition remains bounded at 128 requests with at most 256 batch files (including retained
crash-window orphans). Snapshot raw-input storage remains capped at 256 MB, recovery at 2 GB /
100,000 files, and schedule target/control budgets remain explicit. The app process must remain
running; disk exhaustion and verification failures stop collection safely and need operator
attention. A full final partition is sealed when its successor is needed. Active restored
schedules honor earlier opt-in; pause before an inspection-only export. No infinite storage or
multi-day reliability promise is made.

## Reproduction

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
node frontend/tests/acquisition.test.cjs
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -q \
  backend/tests/unit/test_label_partitions.py backend/tests/unit/test_label_schedule.py \
  backend/tests/unit/test_label_acquisition_errors.py backend/tests/unit/test_label_lifecycle.py \
  backend/tests/unit/test_weather_labels.py backend/tests/integration/test_forward_validation_listener.py \
  backend/tests/integration/test_weather_labels_listener.py
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/label-partition-review/NEW-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW-partitions" \
  npm --prefix frontend/browser test -- label-partitions.spec.cjs forward-validation.spec.cjs \
  --grep '130 controlled|authentic shadow' --max-failures=1
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -q
.venv/bin/python data/label-partition-review/20261031/verify_evidence.py
```

Use fresh browser evidence/workspace paths and socket-permitted runtime. New authentic receipts
may qualify or refuse differently; their availability must start at their actual receipt time.
The final command verifies this retained execution, its exact source/documentation/browser hashes,
local artifact bytes, original safety baseline and quality evidence; it is not a new acceptance run.
Return this milestone for independent review before further feature work.
