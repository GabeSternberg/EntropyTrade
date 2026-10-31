# Continuous label partitions

The opted-in forward-validation schedule now continues beyond 128 acquisitions. Each storage
partition accepts at most 128 requests. When the next request arrives, the service waits for
unfinished requests to drain, seals the completed partition with an immutable checksummed
manifest and opens its successor. Seals chain to the preceding manifest. There is no deletion,
retiming or relocation of the original requests, batches or source responses.

Existing flat workspaces are partition `00000000`; their files remain in place. Successors
live in `runs/weather-labels/partitions/00000001`, and so on. Each seal records exact request
and batch file hashes, its original seal clock and predecessor version. Batches may be shared
by identical acquisitions. A separate 256-batch file guard per partition accommodates retained
orphan batches from interrupted final publication; this does not allow more than 128 requests.
Queue size, source destinations, timeouts, body limits and trading risk limits stay fixed.

Schedules publish their request ID before enqueueing. Temporary queue/rollover backpressure
retains that plan and retries after drain. A crash after sealing but before successor creation
reuses the original plan on restart. Filesystem/verification errors block with their reason;
pause, preserve the workspace, resolve the error and resume explicitly. Pause and shutdown
retain partial receipts. Terminal requests cannot be replaced by stale workers, and archived
request IDs return their original result without another source call.

In **Forward settlement labels**, refresh and select a **Label evidence partition**. The
selector shows every partition's status and bounded request count. All requests in the selected
partition are inspectable, including source refusals and interrupted acquisitions. Download
individual label evidence or the sealed partition manifest. The default label endpoint returns
the current partition; use `/api/weather/label-partitions` and
`/api/weather/label-partitions/00000000` to inspect older bounded pages. The manifest is at
`/api/weather/label-partitions/00000000/manifest`. A partition is sealed only when its successor
is needed; a full final partition can remain active until then.

Manual dataset freezing, following retained inputs and cohort assembly consume verified batches
across all label partitions. Each partition inventory is bounded and rechecked; snapshots retain
all relevant original batch versions and exact receipt bytes. Arbitrary unpartitioned label
lists still have the original 128-input guard. Snapshot raw-input storage remains capped at
256 MB; exceeding it is an explicit error, not evidence deletion. Repeated revision checks do
not increase independent event counts. Availability stays at the original receipt time, missing
publication/revision clocks remain unknown, and frozen calendars and protected exclusions still
apply. Collection can continue when model/history gates remain insufficient.

The workspace recovery CLI includes every partition, seal, schedule plan and source response.
Offline validation verifies the complete chain and inventory, all hashes, request/batch bindings,
pinned dataset selections and scalar source parsing. It never fetches a response or changes a
clock. Starting the website on a restored active schedule honors its earlier opt-in; pause before
export when the purpose is offline inspection. Recovery archives retain the existing 2 GB and
100,000-file limits. Operators must monitor disk use and preserve archives; this change does
not promise infinite storage or cross-process collection without the existing workspace lease.

Run the executable browser acceptance with fresh paths:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/frontend/browser/.browsers" npm --prefix frontend/browser run install:chromium
ENTROPYTRADE_BROWSER_EVIDENCE="$PWD/data/label-partition-review/NEW-browser" \
ENTROPYTRADE_BROWSER_WORKSPACE="$PWD/data/cache/NEW-partitions" \
  npm --prefix frontend/browser test -- label-partitions.spec.cjs --max-failures=1
```

This uses managed Chromium against a real localhost listener. Its 130 controlled batches
accelerate the scheduling clock and substitute explicitly marked source responses. They test
rollover, outage, cancellation, dataset assembly, restart and restore; they establish no elapsed
authentic operation, empirical fitting, returns or profitability. Separately run the authentic
procedure in `forward-validation.spec.cjs` with `--grep authentic` for original retained shadow
inputs and new read-only public source receipts. That short operating sample cannot establish
multi-day reliability or adequate empirical history. See the milestone evidence for executed
results and any outstanding acceptance steps. V1 remains incomplete.
