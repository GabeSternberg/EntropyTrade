# Headless forward collection on GitHub-hosted runners

Scheduled cloud sessions have no public egress to Kalshi or the weather sources (issue #3).
GitHub-hosted runners do: the read-only [egress probe](../.github/workflows/egress-probe.yml)
received HTTP 200 from the Kalshi series/markets API, the Weather Company climate endpoint used
for settlement labels, api.weather.gov and Open-Meteo on 2026-11-05 (run `42129099670`).

`forward-collection.yml` uses that egress to run the **existing** private website workflow
headlessly, so authentic forward receipts can accrue without a human-operated machine.

## What one run does

1. Finds the most recently **completed** run of this workflow **on the same branch** (by
   completion time, not creation time) that uploaded an unexpired `forward-workspace` snapshot, downloads it, checks its SHA-256 and restores it with the
   existing verified `entropytrade.api.recovery restore`. If a previous snapshot exists but
   cannot be downloaded, verified or restored (for example after a `uv.lock` change), the run
   **fails**. It never silently starts a new chain. The first run on a branch, or a manual
   dispatch with `fresh: true`, starts a new empty workspace. A manual dispatch may instead
   name `continue_from_run` (see [continuing a chain on another branch](#continuing-a-chain-on-another-branch)).
2. Runs `python -m entropytrade.operations.forward` for a bounded window (default 1,500 s;
   900 s for verification pushes). The operator starts `entropytrade.api.server` on
   127.0.0.1 and uses only the browser's HTTP API:
   - If there is no monitor, it runs ordinary **recorded-mode, local-template** weather research
     (`Test forecast_high_f > 70`, no provider) and starts one shadow monitor on its first typed
     real candidate (10-minute poll). The candidate stays `INSUFFICIENT_DATA`; monitoring is not
     promotion. An existing active monitor is kept.
   - Once retained public/shadow inputs exist, it freezes one immutable weather dataset and
     enables one forward-validation schedule with **follow retained inputs** (hourly retry,
     eight dates per batch). An existing active schedule is kept.
   - A paused/blocked monitor or schedule (operator pause or the automatic repeated-failure
     pause) is reported as `operator_review_required`. **The operator never resumes or
     replaces it.**
   - It refuses to operate if the server reports `submission_enabled` as anything but false.
3. Stops the server with its normal SIGINT shutdown so unfinished cycles/requests are
   recorded as interrupted with their partial receipts, then snapshots the stopped workspace
   with `entropytrade.api.recovery snapshot`.
4. After the server stops, runs `entropytrade.execution.fee_admin --capture-due schedule
   rounding` against the same workspace. It fetches the official Kalshi fee schedule PDF and
   fee-rounding page only when the retained copy is stale (successful copy older than 24 h;
   failed attempt older than 3 h) and stores each attempt as an immutable **unreviewed**
   authentic receipt, so it travels with the chained snapshot. Nothing is certified; see
   [fee evidence](fee-evidence.md). The result (`fee-capture.json`: status, bytes, SHA-256,
   whether the bytes are a real PDF) is printed in the job log.
5. Uploads `forward-workspace` (archive, checksum, lineage: commit, run, previous run and lock
   hashes; 7-day retention) and `forward-summary` (`summary.json`, server log, snapshot
   receipt, fee-capture report; 90-day retention). The job summary shows the actions, monitor/cycle state,
   schedules, retained inputs, label requests and alerts.

### Evidence readiness in each run

`summary.json` and the operator's one-line job-log output include a read-only `readiness`
section, so chain progress is visible without downloading artifacts:

- `prospective`: for each monitor, the existing prospective-evaluation report's status,
  contract/pending/refused/matched counts, and matched independent events and dates against
  the report's own minimums (10 events on 5 dates), with `events_remaining`/`dates_remaining`.
- `settlement_labels`: distinct station/day labels across **every** label partition. An
  event verified by several revisions counts once; an earlier refusal later verified counts
  as verified. Events never verified are counted with their refusal reasons.

Each entry in `schedules` also carries a `backlog`, so zero settlement labels can be read as
"not yet due" or "stuck" without downloading the workspace:

- `dates`: one row per scheduled local day with `status`, `next_at`, `attempts`, `failures`,
  target count, stations and detail. A pending day first becomes due at the end of its local
  day (the latest station timezone); failed acquisitions back off from the schedule interval.
- `next_due_at`: the earliest due time of any pending/retry day (verified revision checks
  and refused days are excluded).
- `overdue_dates`: days already due at summary time while no label request was in flight.
  The label worker ticks every 0.2 s while the server runs, so a non-empty list at the end of
  a window means the schedule did not advance and needs review. It is reported, never repaired.

Labels are only requested while a run's server is up. Until the cron runs on `main`, a day
that becomes due between dispatched runs waits for the next run.

If the website refuses to verify the evidence (HTTP 409), readiness reports
`verification_failed` with the message. It is never retried into a pass or repaired. These
are counts of retained evidence only, not model quality, calibration or returns.

Alerts are summarized as `open`, `acknowledged` or `resolved` from their lifecycle clocks
(`opened_at`, `acknowledged_at`, `resolved_at`); the log line lists unresolved alerts.
Summaries written before this change listed every alert with `status: null`.

`workspace` reports the bytes the next snapshot will carry, by area (`jobs.sqlite`, `runs`,
`runs/weather-datasets`, `shadow`), against the 2 GB snapshot budget (`budget_used`). Its
`status` is `ok`, `warning` (at least 50%) or `critical` (at least 80%). The job summary
adds a `::warning::` annotation for the last two. It counts file sizes only and excludes
the runtime files that snapshots skip. Snapshot archives are deflate-compressed; archives
stored uncompressed by earlier runs still restore.

A snapshot is uploaded even when collection fails, so the next run continues from every
retained receipt. The run is still marked failed.

Runs on one branch are serialized by the concurrency group, so completion order is chain
order. Creation order is not: on 2026-11-06, dispatch `42167131442` was created before push
`42167132149`, but the push ran first. Creation order would have made the push run's
fresh-chain snapshot "newest" and orphaned the continued chain.

### Push runs are trials, not chain heads

A push that changes the workflow or operations code runs a **trial**: it restores the branch's
chain head (if any), collects for 900 s and uploads its snapshot as `forward-trial-workspace`
(3-day retention). Only `schedule` and `workflow_dispatch` runs upload `forward-workspace`, and
chain lookup skips `push` runs entirely, including push runs from older workflow versions that
used the chain name. Push runs also use their own concurrency group
(`forward-collection-trial-<ref>`). Both rules come from 2026-11-06:

- Push `42162670639` was the first run on `claude/vibrant-bohr-g16hbp`, found no snapshot and
  started a fresh chain. Later pushes on that branch continued it instead of the authentic chain.
- GitHub keeps only one *pending* run per concurrency group. Push `42167132149` queued behind
  a running trial and replaced continuation dispatch `42167131442`, which was cancelled
  before it started.

`lineage.txt` records `event` and `chain=head|trial`. Trial receipts are authentic, but they are
a fork: never add trial counts to chain counts.

Step conditions use step outputs and plain file tests, never `hashFiles()`. Hosted runners
abort `hashFiles()` after 120 s. In run `42162688233` that limit was hit on a 243 MB
`workspace.zip`, so a successful 14-cycle window's snapshot was never uploaded. The upload now
runs only when the snapshot step has written the archive, checksum and lineage
(`steps.snapshot.outputs.archive`).

## Safety boundaries

- Every network request is made by existing bounded adapters: fixed public URLs, unauthenticated
  GETs, request/byte/time budgets. No repository secret, research/provider key or exchange
  credential is referenced. The workflow token is read-only (`contents: read`,
  `actions: read`) and is used only to find and download the previous artifact.
- No order transport exists; submissions remain disabled; risk limits, fee certification,
  model binding and holdout boundaries are unchanged. Uncertified fees and missing fitted
  models still block intentions, so paper accounts record no fills.
- Receipt, decision and label clocks are the real receipt times on the runner. Nothing is
  backdated: a restored workspace keeps its original bytes, and normal startup does not
  manufacture missed polls between runs.
- Gaps between windows are real gaps. With the default 4-hour cron and 25-minute window, a
  monitor captures about three cycles per window. This is intermittent, not continuous,
  operation, and summaries must be read that way.

## Operating it

Scheduled runs only start after the workflow is on the default branch. Before that, a push
to a `claude/**` branch that changes the workflow file runs one verification trial (see
above); it never extends the chain. To run manually after merging, use **Actions → forward-collection → Run
workflow** (`seconds`, optional `fresh` or `continue_from_run`).

### Continuing a chain on another branch

Snapshots are found per branch, so a merge to `main` (or a new branch) would otherwise start an
empty chain and leave the accumulated receipts to expire after 7 days. Dispatch once with
`continue_from_run=<run ID>` to restore that run's snapshot instead. The step **fails closed**
unless the ID is numeric, the run is a completed `forward-collection.yml` run of this
repository, it has an unexpired `forward-workspace` artifact, and `fresh` is false. It never
falls back to the branch's own snapshot or a fresh chain. An error listing artifacts now
also fails the run, instead of silently selecting an older snapshot. Restore still requires
the same `uv.lock`/`pyproject.toml`.

`lineage.txt` now records `branch` and `previous_branch`, and the snapshot artifact carries the
source run's `previous-lineage.txt`, so the cross-branch hop stays traceable. Later runs on the
new branch continue from its own newest snapshot as usual.

**Do not push to the branch, or let a scheduled run start, while a continuation dispatch is
queued.** A GitHub concurrency group keeps at most one *pending* run, and a newer pending run
cancels the older one. That happened on 2026-11-06: push run `42167372741` cancelled queued
dispatch `42167131442` before it started. A cancelled continuation leaves the chain unchanged,
but it must be dispatched again. On `main`, dispatch soon after a scheduled run finishes, not
just before `:23` past a 4-hour mark.

Continuing copies evidence; it does not merge chains. After continuing, **stop dispatching the
source branch**, or the two chains diverge from a shared history and their counts must never be
added together. `backend/tests/unit/test_forward_workflow_chain.py` runs the actual step script
against a stubbed `gh`.

Inspect a chain locally (offline, after `uv sync --locked`):

```bash
# download forward-workspace from the newest run, then
sha256sum workspace.zip   # compare with workspace.sha256
uv run python -m entropytrade.api.recovery restore \
  --archive /path/to/workspace.zip --workspace data/cache/forward-inspect
uv run entropytrade-web --workspace data/cache/forward-inspect
```

Restore requires the same `uv.lock` and `pyproject.toml` as the commit in `lineage.txt`.
**Pause the restored monitor/schedule in the website before inspecting** if you do not want
the local copy to start collecting.

### Retention and failure handling

- Workspace artifacts expire after 7 days. Only the newest snapshot is needed to continue,
  but if the chain stops for longer than that, its evidence is lost. Download snapshots that
  matter and keep them with their checksum and lineage. Promote durable evidence into a
  reviewed evidence directory with a manifest, as earlier milestones did.
- If a dependency change breaks restore, the run fails closed. Either restore the last
  snapshot at its recorded commit and re-snapshot it after upgrading, or deliberately start a
  new chain with `fresh: true`. The new chain does not inherit any evidence from the old one.
- Repeated source failures pause the monitor through the existing five-failure rule. The
  next runs then report `operator_review_required` until someone reviews and resumes it.
- Private repository artifact storage counts against the account quota. Watch `workspace` in
  each summary and archive sizes in the snapshot step, and lower the cron frequency if needed.
  A workspace over the 2 GB budget cannot be snapshotted, so that run's receipts are not
  carried forward and the chain stalls. Act on a `warning`. Retained raw receipts are never deleted to make room.

## What this does not establish

A successful run proves that authentic receipts are being collected and retained. It does
not establish sufficient independent history, fitted real models, certified fees,
calibration, returns or profitability. Those gates, and V1, stay open.
