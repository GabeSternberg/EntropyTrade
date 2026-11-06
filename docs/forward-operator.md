# Headless forward collection on GitHub-hosted runners

Scheduled cloud sessions have no public egress to Kalshi or the weather sources (issue #3).
GitHub-hosted runners do: the read-only [egress probe](../.github/workflows/egress-probe.yml)
received HTTP 200 from the Kalshi series/markets API, the Weather Company climate endpoint used
for settlement labels, api.weather.gov and Open-Meteo on 2026-11-05 (run `42129099670`).

`forward-collection.yml` uses that egress to run the **existing** private website workflow
headlessly, so authentic forward receipts can accrue without a human-operated machine.

## What one run does

1. Finds the newest run of this workflow **on the same branch** that uploaded an unexpired
   `forward-workspace` snapshot, downloads it, checks its SHA-256 and restores it with the
   existing verified `entropytrade.api.recovery restore`. If a previous snapshot exists but
   cannot be downloaded, verified or restored (for example after a `uv.lock` change), the run
   **fails**. It never silently starts a new chain. The first run on a branch, or a manual
   dispatch with `fresh: true`, starts a new empty workspace.
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

A snapshot is uploaded even when collection fails, so the next run continues from every
retained receipt. The run is still marked failed.

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
to a `claude/**` branch that changes the workflow file runs one verification window on that
branch's own chain. To run manually after merging, use **Actions → forward-collection → Run
workflow** (`seconds`, optional `fresh`).

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
- Private repository artifact storage counts against the account quota. Watch archive sizes in
  `snapshot.json` and lower the cron frequency if needed.

## What this does not establish

A successful run proves that authentic receipts are being collected and retained. It does
not establish sufficient independent history, fitted real models, certified fees,
calibration, returns or profitability. Those gates, and V1, stay open.
