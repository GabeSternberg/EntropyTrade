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
- `source` (on `retry`/`refused` days with a retained batch, newest 8 days): what the latest
  retained portal receipt said. It has the batch version (re-checked against the server's
  copy), receipt clock, HTTP status, portal-wide `officialReports`/`preliminaryReports`/
  `noReports` counts, and per-station record count, `status`, `isOfficial`, `reportDate`,
  `issueTime` and `integer_high_present`. The single refusal "preliminary, missing or
  nonofficial" covers several of these states; portal-wide `officialReports: 0` means
  the source has not published yet (it was still preliminary for all 45 stations at
  09:08Z the next morning in the retained 2026-10-30 receipt). One station preliminary while
  others are official points at that station. The unverified high is never echoed, and the
  parser and its refusal text are unchanged, because frozen dataset audits replay that text.

Labels are only requested while a run's server is up. Until the cron runs on `main`, a day
that becomes due between dispatched runs waits for the next run.

If the website refuses to verify the evidence (HTTP 409), readiness reports
`verification_failed` with the message. It is never retried into a pass or repaired. These
are counts of retained evidence only, not model quality, calibration or returns.

Alerts are summarized as `open`, `acknowledged` or `resolved` from their lifecycle clocks
(`opened_at`, `acknowledged_at`, `resolved_at`); the log line lists unresolved alerts.
Unresolved alerts also carry their `evidence` (for reconciliation, each contract's
`close_time`, `expected_settlement_at`, `basis` and `last_attempt`); contract lists over 20
are truncated with `contracts_total`. Resolved alerts omit evidence.
Summaries written before this change listed every alert with `status: null`.

`workspace` reports the bytes the next snapshot will carry, by area (`jobs.sqlite`, `runs`,
`runs/weather-datasets`, `shadow`). Snapshots (schema `entropytrade-workspace-v2`) store
each distinct file content once, because immutable weather datasets copy shadow receipts
byte for byte; a restore still writes every path as its own checksum-verified file (no
hard links). Two budgets apply: `distinct_bytes` against the 2 GiB archive budget
(`snapshot_budget_bytes`) and expanded `bytes` against the 4 GiB restore budget
(`expanded_budget_bytes`). `budget_used` is the larger ratio. Its `status` is `ok`,
`warning` (at least 50%) or `critical` (at least 80%), and the job summary adds a
`::warning::` annotation for the last two. The footprint hashes file contents and excludes
the runtime files that snapshots skip. Archives are deflate-compressed. Per-path
`entropytrade-workspace-v1` archives (stored or deflated) from earlier runs still restore,
bounded by their original 2 GiB expanded budget.

### Storage runway

`runway` turns the footprint into a measured projection. The operator records the footprint
before starting the server and again after it stops, and divides the growth by the monitor
cycles completed in the window. The growth includes the discovery datasets and label receipts
the same window wrote. For each budget (`expanded_bytes`, `distinct_bytes`, `files`) it
reports `growth_this_run`, `per_cycle`, `remaining` and `cycles_left`. The smallest is the
`binding` budget.

- `days_left` and `exhausted_on` are **extrapolated** at `cycles_per_day_assumed`
  (`--cycles-per-day`, default 6: the 4-hourly cron at one cycle per scheduled window).
- `validation_end` is the third frozen calendar boundary, read from a published weather
  dataset manifest. The fit/calibration/validation partitions cannot be complete before it.
- `status` is `covers_validation_end`, `short_of_validation_end` (the job summary adds a
  `::warning::`), `measured` (no frozen calendar yet) or `unmeasured` (no start footprint,
  no completed cycles or no growth). A run with no cycles never projects.
- **One run's growth is uneven.** Discovery freezes a window's cycles in a later window, so a
  run that writes no dataset understates expanded growth, and the next run overstates it.
  Compare `per_cycle` across several runs before acting. For example, run `42239530977`
  (one cycle, no new dataset) measured 4.19 MB expanded per cycle, while run `42231627280`
  (five cycles, with discovery) measured 10.6 MB.

Why it matters: a workspace over any budget cannot be snapshotted, so the chain stalls, and
receipts are never deleted to make room. Expanded bytes grow about 2.5 times faster than
distinct bytes, because each discovery dataset stores a shadow cycle's capture twice (as
`receipts/NNNN/` and inside `shadow/<digest>/public/`) on top of the original. Replaying the
two retained authentic cycles in `data/shadow-review/20261029-model-integration` gives
dataset bytes of about 2.0 times their input cycle bytes (5,302,528 for 2,635,728). On
2026-11-06 the chain's per-cycle growth was about 9.2 MB expanded and 3.7 MB distinct (run
`42224274925`, after slim captures). Over runs `42231627280` and `42239530977` (six cycles),
growth was 57.3 MB expanded and 24.8 MB distinct: about 9.5 MB and 4.1 MB per cycle. The
chain's frozen calendar ends validation on **2027-02-03**. At six cycles a day, the expanded
budget lasts until about 2027-01-03 and the distinct budget until about 2027-01-21. Both are
extrapolations, and both fall short.

**Scheduled windows are 540 s** (before 2026-11-06: 1,500 s). The monitor polls when the
server starts and every 600 s, so a scheduled window now takes one cycle instead of three.
The gates do not count the extra polls: prospective evaluation keeps the earliest pre-close
observation per event, and fitting takes one timely example per event. At three cycles per
window (18 per day), the 4 GiB restore budget would be reached in about three weeks. At one
cycle per window, it would last about two months. Both figures are extrapolations, and
neither reaches the validation end on its own. The first 540 s chain run (`42239530977`)
completed exactly one cycle and finished in about 11 minutes. A manual dispatch still defaults to 1,500 s.
Removing the duplicate capture copy inside datasets, or moving sealed evidence to durable
storage, is still needed. That decision is tracked in issue #21 and has not been started.

#### Chain projection and runner disk

`chain_runway` is the same projection averaged over a **trailing 7 days of chained runs**,
so a run without discovery no longer overstates the runway on its own:

- Each run records two ledger rows: the footprint before the server starts and after it
  stops, with the monitors' total cycle count. The workflow uploads
  `runway-ledger.jsonl` next to the snapshot (in `forward-workspace`), and the next run passes
  it back with `--ledger-in`. It is operational metadata. It is never restored into the
  workspace and is not evidence.
- Growth runs from the oldest row in the window to this run's end, divided by the monitor
  cycles between them. The output adds `since`, `rows_in_window`, `runs_in_window`,
  `cycles_in_window` and `growth_in_window`.
- The ledger restarts when it does not continue this workspace: monitor cycles or clocks go
  backwards, as after a fork from an older snapshot or a fresh chain. A malformed ledger is
  discarded. In both cases `ledger_reset` gives the reason. Rows older than 30 days are
  retired, with at most 256 rows kept. A run that measured nothing carries the previous rows
  forward unchanged.
- The job-summary warning uses `chain_runway` when it is measured, and otherwise falls back
  to `runway`.
- The ledger starts with the first run of this version. Earlier runs' growth is in STATUS and
  issue #21; it is not backfilled.

`disk` reports `total_bytes` and `free_bytes` of the runner filesystem that holds the
workspace, measured after the server stops. A snapshot copies the whole workspace into a
staging payload before compressing it. A restored workspace therefore needs about its
expanded bytes free again at snapshot time, plus the archive. This measures whether a larger
restore budget (option 3 in #21) would fit. It does not change any budget.

#### Dataset cost per discovered input

`datasets` attributes this run's dataset growth to the inputs it froze. It compares the
published dataset directories before the server starts and after it stops. For each new
dataset it reports:
- the `inputs` its selection names, and their current retained `input_bytes`;
- its `bytes` and `files`, split by `parts`: `receipts` and `shadow` (the two capture copies),
  `labels`, `scalar_labels`, `shadow_replay`, `rows`, `features`, `manifest` and `other`;
- `bytes_per_input` and `ratio_to_inputs`.

Run totals add `bytes_per_input` and `ratio_to_inputs` across datasets. `staging_leftovers`
and `staging_bytes` count unfinished `.building-*` directories, which the footprint also
counts. The ratio is `null` unless every named input resolves to exactly one retained
directory. It is read-only and is not evidence.

**Why a discovery run grows by tens of MB.** Discovery runs on the schedule's own clock
(`--schedule-interval`, 3,600 s), not once per window. Most windows are 540 s, so a discovery
usually freezes the cycles that earlier windows retained since the last discovery. Sometimes
it freezes none. Example (from the printed job summaries):
- Run `42239530977` stopped at 15:14 with `next_discovery` 15:28, so it froze nothing.
- Run `42243733103` discovered at 15:32. Its dataset grew `runs/weather-datasets` by 23.1 MB.
- Per-cycle `shadow` growth was 3.55 MB, and roughly four or five cycles were waiting. That
  is 4.6–5.8 MB of dataset per input, or 1.3–1.6 times the cycle's bytes. This is an
  inference from clocks, not a measurement.
- Replaying the two retained authentic cycles measures **2.0 times** (`ratio_to_inputs`
  2.0; the `receipts` and `shadow` copies are over 90% of the dataset). Those cycles predate
  slim captures, so the current ratio may differ. The next run's `datasets` settles it.

So 23 MB was several cycles frozen at once, not an unusually costly dataset. `datasets` now
measures this directly in every run. The workspace also holds about 739 MB of datasets
against 217 MB of shadow cycles. That ratio is higher than the current per-input cost, which
suggests that datasets frozen before incremental discovery (PR #14) overlap. Those datasets
are immutable evidence and are not removed.

A snapshot is uploaded even when collection fails, so the next run continues from every
retained receipt. The run is still marked failed.

### Forward locations and station bindings

`configs/data/weather-forward.json` selects the daily-high series captured each cycle. Since
2026-11-06 it has four: Philadelphia (`KXHIGHPHIL`, CLIPHL), Chicago Midway (`KXHIGHCHI`,
CLIMDW), New York City (`KXHIGHNY`, CLINYC) and Dallas (`KXHIGHTDAL`, CLIDFW). Each added
location is backed by retained authentic evidence, checked by
`test_forward_station_bindings.py`:

- **Series and station.** The series is in the retained Kalshi catalog listing (PR #8). The
  station is named in retained contract rules ("New York City (CLINYC)", "Dallas (CLIDFW)",
  `data/public/{newyork,dallas}/manifest.json`).
- **Label source.** The settlement portal lists the station's `cliId`/ICAO/timezone in the
  retained receipt `data/weather-label-review/20261031/probe/primary-2026-10-29.json`.
  `weather/labels.py` `STATIONS` allowlists exactly those values.
- **Forecast coordinates.** These are the coordinates returned by the retained
  `api.weather.gov/stations/K…` receipt, **rounded to 4 decimals**. api.weather.gov
  `/points` redirects (301) a point with more decimals. The bounded client does not follow
  redirects, so every cycle then fails, and 5 consecutive failures pause the monitor (run
  `42213570196`). A test enforces at most 4 decimals. Oklahoma City (CLIOKC) is **not** added: its
  retained coordinates are a city-centre geocode, not the station.

The existing monitor's frozen strategy universe is unchanged, so new series make no shadow
decisions. They are still labelled: when discovery freezes a shadow cycle's capture, a captured
contract outside the monitor's universe takes the capture's own decision clock, exactly as a
public capture does (protected events excluded). In-universe contracts keep the shadow's sample
clocks. Before this rule (chain run `42217215001`), NYC/Dallas contracts were captured but never
became rows, so the schedule only targeted CLIMDW/CLIPHL; already-frozen discovery datasets stay
as they were. More independent station/days per date is the point: the fitting gate needs
60/20/20 independent fit/calibration/validation events.

Each `summary.json` (and the job-log line) carries `station_bindings`, computed read-only
from the newest retained weather capture. For each configured location it reports:

- `contracts`: the captured contracts;
- `named_stations`: the CLI station codes the rules name;
- `label_compatible`: the contracts the existing label gate (`compatible_rules`) accepts;
- `label_source_supported`: whether the label source supports the station/timezone;
- `status`: one of `matched`, `mismatch` (rules name another station), `unnamed`, `partial`
  or `no_contracts`.

The top-level `status` is `ok` only when every location is `matched`. A mismatched mapping
is never relabelled. The label gate already refuses it, and this section only makes that
visible without downloading the workspace.

Adding locations raises per-cycle storage. Going from 2 to 4 locations raised distinct growth
from about 4.8 to about 6.0 MB per cycle and expanded growth to about 12.9 MB per cycle (run
`42217215001`). Watch `workspace` growth per cycle before adding more.

### Capture layout (since 2026-11-06)

Each public weather capture keeps every response body exactly once, under `raw/NNNN.json`
(listed with URL, status, hash and receipt time in `capture.json`). Forecast observations cite
that same file: same bytes, same `raw_hash`. The forecast archive database is a parsing
intermediate built in a temporary directory and is not retained. The capture keeps only:

- `weather/manifest.json`: the archive summary (coverage, vintage/failure counts, snapshot hash);
- `weather/receipts.json` (`entropytrade-weather-receipts-v1`): every archive receipt with its
  URL, status, receipt and ingestion clocks, body hash, `raw_ref`, and the vintage or parse
  failure it produced.

Before this change each capture also kept `weather.sqlite`, a second copy of every forecast
body (`weather/raw/`) and a second observation file (`weather/observations.jsonl`). Replaying
the retained authentic 2026-10-29 two-location capture through the new code shrinks it from
2,346,335 to 939,526 bytes (19 to 14 files), with identical observation values, revision IDs
and raw hashes. Earlier captures are unchanged and still verify: readers only follow each
manifest's own checksums and each observation's `raw_ref`. If a body has no identical retained
response, it is copied to `weather/raw/` as before, never dropped.

The collector code lives in `families/weather_capture.py`. `families/public.py` is **frozen**:
`forward_data` binds every capture's `feature_version` to that file's hash, and
`verified_inputs` refuses a retained shadow cycle whose saved version differs. The first
attempt at this change edited `public.py` and failed 16 authentic replay tests with
"shadow source version mismatch". `test_forward_data_module_is_frozen_for_retained_shadow_cycles`
now pins the hash with that explanation.

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
- Gaps between windows are real gaps. With the default 4-hour cron and 540-second window, a
  monitor captures one cycle per window (three per 1,500-second manual dispatch). This is intermittent, not continuous,
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

### Durable local chain (no GitHub Actions dependency)

Actions artifacts expire after seven days and Actions can stall (issue #28), so
`entropytrade.operations.local_chain` keeps the same chain as permanent, hash-linked links in a
directory inside the repository (default suggestion `data/cache/chain`, git-ignored):

```bash
# 1. Download the newest forward-workspace artifact (run 42288775503 at time of writing).
uv run python -m entropytrade.operations.local_chain import-actions \
  --chain data/cache/chain --artifact-dir /path/to/artifact --source-run 42288775503
# 2. Collect (public egress required): restore head -> bounded window -> snapshot -> new link.
uv run python -m entropytrade.operations.local_chain run --chain data/cache/chain --seconds 540
# 3. Audit every checksum, previous-hash link and the HEAD pointer.
uv run python -m entropytrade.operations.local_chain verify --chain data/cache/chain
```

- `import-actions` verifies the artifact checksum and a full restore, then copies it unchanged
  as link 1 and records the source run in `lineage.txt`. It only seeds an empty chain.
- `run` fails closed on any tampered link, a held lock or an empty chain (use `--fresh` only to
  start a new chain deliberately; it is refused when links exist). A failed collection still
  publishes its verified snapshot, like the workflow. Links are never rewritten or deleted;
  the work directory is removed after each run.
- Collection is the existing `entropytrade.operations.forward` plus unreviewed fee capture:
  public unauthenticated GETs, no credentials, submissions disabled.
- **Do not run the local chain and dispatch the Actions workflow from the same snapshot**:
  the two chains would fork and their counts must never be added. Pick one head and stop the
  other. Run it from cron/systemd every 4 hours, or on a self-hosted runner.
- This is operator tooling; it does not satisfy the sustained-operation, history or storage
  gates by itself. Its collection step was not exercised against live sources in this session
  (no egress, issue #3); tests use a controlled collector with real snapshot/restore.

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
  A workspace over either snapshot budget cannot be snapshotted, so that run's receipts are not
  carried forward and the chain stalls. Act on a `warning`. Retained raw receipts are never deleted to make room.

## What this does not establish

A successful run proves that authentic receipts are being collected and retained. It does
not establish sufficient independent history, fitted real models, certified fees,
calibration, returns or profitability. Those gates, and V1, stay open.
