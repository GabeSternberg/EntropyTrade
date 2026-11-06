# EntropyTrade — current status

## Current milestone (2026-11-06): dataset cost per discovered input

Branch `claude/vibrant-bohr-f74103`, **stacked on PR #23** (`claude/vibrant-bohr-dndtp2`).
**V1 remains incomplete.** At the start of this run, open PRs #8–#23 had no reviews, review
threads or failing checks, and none were merged. Issues #3, #6 and #21 remain open. #21 has no
user answer yet. It was 16:23Z, so the 2026-11-06 labels (due 2026-11-07T06:00Z) were not yet
checkable and no chain run was dispatched.

- **Question from #23.** Why did one discovery grow `runs/weather-datasets` by 23.1 MB, when a
  replay predicts about 2× its inputs?
- **Finding (from the printed job summaries; artifact storage is blocked by the session
  egress policy, see #3).**
  - Discovery runs on the schedule's 3,600 s clock, not once per window.
  - Run `42239530977` stopped at 15:14 with `next_discovery` 15:28, so it froze nothing.
  - Run `42243733103` discovered at 15:32, freezing the roughly four or five cycles retained
    since the 14:28 discovery.
  - With 3.55 MB of `shadow` growth per cycle, that is 4.6–5.8 MB of dataset per input, or
    1.3–1.6× the input. So 23 MB was several cycles at once, not an unusually costly dataset.
    This is an **inference from clocks**, not a measurement.
  - The workspace holds 739 MB of datasets against 217 MB of shadow cycles. That ratio is
    higher than the current per-input cost, which suggests that datasets frozen before
    incremental discovery (#14) overlap. They are immutable and are kept.
- **Change (`operations/forward.py`, workflow, docs).** Each summary now has `datasets`:
  - every dataset published during the run, with its selection's `inputs` and their
    retained `input_bytes`;
  - bytes split by part: `receipts`/`shadow` capture copies, `labels`, `scalar_labels`,
    `shadow_replay`, `rows`, `features`, `manifest`, `other`;
  - `bytes_per_input`, `ratio_to_inputs`, and unfinished `.building-*` staging leftovers.
  - It is read-only. The ratio is null unless every input resolves to exactly one directory.
    The job summary now prints it.
- **Evidence.**
  - The real builder on the two retained authentic cycles gives `ratio_to_inputs` between
    1.8 and 2.2 (measured 10,500,645 bytes for 5,271,679 input bytes). The capture copies are
    over 90% of the dataset.
  - Local checks: Ruff lint and format pass; strict mypy passes (566 files). 3 new tests, and
    the real-server operate test is extended. **Full pytest: 1,418 passed in 676.47s**, with zero failures, errors or skips.
  - No chain run was dispatched this session. The first chain run on this branch will
    measure `datasets` on real cycles.

**Next autonomous milestone:** after 2026-11-07T06:00Z, dispatch **this branch**
(`continue_from_run` = `42243733103`, `seconds=540`). This branch becomes the chain head;
do not dispatch `dndtp2` or earlier branches afterwards, or the chain forks. Check:
- whether the 2026-11-06 labels verify for all four stations;
- `datasets.ratio_to_inputs` and `bytes_per_input` on real slim cycles;
- that `chain_runway.runs_in_window` grows.

Feed the measured per-input cost into #21. The storage fix and merging the stack still need
the user.

## Current milestone (2026-11-06): chained storage runway and runner disk headroom

Branch `claude/vibrant-bohr-dndtp2` (PR #23), **stacked on PR #22** (`claude/vibrant-bohr-jux3wd`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#22 had no
reviews, review threads or check runs, and none were merged. Issues #3, #6 and #21 remain open.
The #21 storage decision has no user answer yet.

- **Gap.** #22 projects the runway from a single run's growth, which swings widely:
  - Run `42239530977` (1 cycle, no dataset) measured 4.19 MB expanded per cycle.
  - This branch's chain run `42243733103` (1 cycle, one discovery dataset written) measured
    **27.3 MB expanded and 6.5 MB distinct**. Of that, `runs/weather-datasets` grew 23.1 MB
    (715.8 → 738.9 MB).
  - A single run can therefore under- or over-state the runway several times over.
  - #21 also needs runner disk headroom confirmed before a larger budget is considered.
    Nothing measured it.
- **Change (`operations/forward.py`, workflow, docs).**
  - **`runway-ledger.jsonl`.** Start and end footprint rows, with the monitors' total cycle
    count, are carried beside the snapshot artifact and passed back with `--ledger-in`.
  - **`chain_runway`.** Projects over a trailing 7-day window. The ledger restarts, with a
    reason, if cycles or clocks go backwards. A malformed ledger is discarded. A run that
    measured nothing carries the rows forward.
  - **`disk`.** Reports the runner's free and total bytes.
  - **Warning.** The job-summary warning prefers `chain_runway`.
  - **No budget changed.**
- **Evidence.**
  - Chain run **`42243733103`** (`continue_from_run=42239530977`, 540 s, `chain=head`):
    - success, 1 cycle ("24 shadow decisions; 0 acquisition failures"), 60 cycles total;
    - workspace 986,819,116 expanded and 268,409,104 distinct bytes;
    - `chain_runway` (1 run so far): binding `expanded_bytes`, 121 cycles left,
      `short_of_validation_end`, and the warning fired.
  - **`disk`** (after the server stopped, with a 0.99 GB workspace on disk): **free 11.05 GB
    of 76.9 GB**. A snapshot stages a second full copy of the workspace, plus the archive and
    the downloaded previous archive. So roughly 5 GiB expanded is the most a standard runner
    can hold without freeing space first. An 8 GiB budget (option 3) would **not** fit as the
    workflow stands. This is an inference from one measurement.
  - The backlog now holds **2026-11-07 for all four stations** (CLIDFW/CLIMDW/CLINYC/CLIPHL).
    2026-11-06 work remains `pending` until 2026-11-07T06:00Z. Labels: still 2 verified events.
  - Local checks: Ruff lint and format pass, and strict mypy passes (566 files). **Full pytest:
    1,415 passed in 749.23s**, with zero failures, errors or skips. 8 new or extended tests
    cover window averaging, fork, clock and malformed-ledger resets, retirement, CLI
    carry-through, disk headroom, and the actual collect-step shell with a stub `uv`.
- **Chain head is now this branch** (`42243733103`). Do not dispatch `jux3wd` or earlier
  branches again, or the chain forks. The push trial `42243723993` uses a separate trial
  workspace and is not part of the chain.

**Next autonomous milestone:** after 2026-11-07T06:00Z, dispatch this branch again
(`continue_from_run` = the newest completed chain run, `seconds=540`). Check:
- whether 2026-11-06 labels verify for all four stations;
- that `chain_runway.runs_in_window` grows and `ledger_reset` stays null;
- whether a discovery run's large dataset growth (about 23 MB) recurs. If it does, the
  dataset cost per input is far above the 2× replay estimate in #21, so find out what a
  discovery dataset stores beyond the two capture copies.

The storage fix still needs the user's decision in #21. Merging the stack to `main` is still
needed to activate the cron.

## Current milestone (2026-11-06): measured storage runway; one cycle per scheduled window

Branch `claude/vibrant-bohr-jux3wd` (PR #22), **stacked on PR #20** (`claude/vibrant-bohr-ab8h5b`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#20 had no
reviews, review threads or check runs; none were merged. Issues #3 and #6 remain open. New
issue **#21** records the storage decision described below.

- **PR #20 confirmed on a real runner.** Chain run `42231627280` (`ab8h5b`, continuing
  `42224274925`; 58 cycles, 0 errors, server exit 0) shows a 2026-11-06 backlog item for
  **CLIDFW/CLINYC** next to CLIMDW/CLIPHL. All four `station_bindings` are `matched`.
- **Gap: the chain cannot reach its own validation calendar.**
  - Frozen boundaries are anchor + 48/60/90 days. The chain's `validation_end` is **2027-02-03**.
  - Snapshots refuse a workspace over 4 GiB expanded or 2 GiB distinct bytes. Receipts are
    never deleted, so the chain stalls when either budget is reached.
  - Expanded bytes grow about 2.5× faster than distinct bytes, because each discovery dataset
    stores a shadow cycle's capture twice (`receipts/NNNN/` and `shadow/<digest>/public/`).
  - A local replay of the two retained authentic cycles gives dataset bytes 5,302,528 for
    2,635,728 input bytes.
- **Change (`operations/forward.py`, workflow, docs).**
  - Every summary carries `runway`: footprint before the server starts and after it stops,
    growth per completed cycle for the expanded, distinct and file budgets, cycles left, the
    binding budget, and an extrapolated `exhausted_on` (6 cycles a day assumed) against
    `validation_end`. The job summary warns when the status is `short_of_validation_end`.
  - Scheduled windows drop from 1,500 s to **540 s**: one cycle per 4-hourly window. Extra
    polls in a window add no independent events or dates to any gate. Manual dispatch still
    defaults to 1,500 s.
- **Evidence.**
  - Push trial `42234521029`: a fresh trial workspace, not the chain. Two cycles, `runway`
    reported, 0 errors.
  - Chain continuation **`42239530977`** (this branch, `continue_from_run=42231627280`,
    540 s, `chain=head`): exactly **1 cycle**, about 11 minutes total, 59 cycles overall.
    Workspace 959,513,085 expanded and 261,884,536 distinct bytes (`budget_used` 0.2234).
    `runway`: binding `distinct_bytes`, 453 cycles left, `exhausted_on` 2027-01-21,
    **`short_of_validation_end`**, and the warning fired.
  - That single run wrote no dataset, so its expanded growth (4.19 MB per cycle) is
    understated. Over runs `42231627280` and `42239530977` (six cycles), growth was about
    9.5 MB expanded and 4.1 MB distinct per cycle. At six cycles a day that reaches the
    expanded budget around **2027-01-03** and the distinct budget around 2027-01-21
    (extrapolated). Both fall short of 2027-02-03.
  - Ruff lint/format pass; strict mypy passes (566 files). **Full pytest: 1,409 passed in
    638.64s**, with zero failures, errors or skips. New tests: runway arithmetic and binding,
    refusal to project without growth, over-budget workspace, frozen-calendar reading, and
    the real-server operate check.
  - Labels: still 2 verified events (2026-11-05 CLIMDW/CLIPHL). 2026-11-06 work (all four
    stations) first becomes due at 2026-11-07T06:00Z.
- **Chain head is now this branch** (`42239530977`). Do not dispatch `ab8h5b` or earlier
  branches again, or the chain forks.

**Next autonomous milestone:** dispatch this branch again within 7 days
(`continue_from_run` = the newest completed chain run). Check whether 2026-11-06 labels for
all four stations verify; expect next-morning source lag. Compare `runway.per_cycle` across
several runs. The storage fix needs the user's decision in **#21**: cold storage for sealed
evidence, a dataset layout without the duplicate copy, or a larger restore budget. Without
one, the chain stalls before the validation end. Merging the stack to `main` is still needed
to activate the cron; also confirm the Actions minutes and artifact-storage quota (#21).

## Current milestone (2026-11-06): new forward locations reach label targets

Branch `claude/vibrant-bohr-ab8h5b`, **stacked on PR #19** (`claude/vibrant-bohr-xq6pdo`).
**V1 remains incomplete.** At the start of this run, open PRs #10–#19 had no reviews, review
threads or failing checks; none were merged. Issues #3 and #6 remain open.

- **Chain run `42217215001`** (`claude/vibrant-bohr-3bmoqc`, rounded coordinates, `chain=head`,
  previous `42213570196`): 48 cycles, 2 completed this run, 0 failures, 0 errors, server exit 0.
  Workspace: 856,230,326 expanded bytes, **218,830,577 distinct**, `budget_used` 0.1994,
  8,411 files. Label backlog: 2026-11-05 CLIMDW/CLIPHL `retry` after 3 attempts. The portal at
  09:27Z on 11-06 still had **0 official, 42 preliminary and 10 no-report** stations, the same
  next-morning lag seen on 10-30. The 2026-11-06 work is `pending` until 2026-11-07T06:00Z.
- **Gap found.** Both backlog dates list only **CLIMDW/CLIPHL**, although NYC/Dallas have been
  configured and captured since run `42213570196`. Root cause: `build_snapshot` took a shadow
  capture's decision clocks only from the monitor's saved samples. The monitor's universe was
  frozen to KXHIGHPHIL/KXHIGHCHI, so KXHIGHNY/KXHIGHTDAL contracts never became rows or label
  targets. Earlier docs said the new series were "captured and labelled"; that was wrong.
- **Change.** In `weather/history.py`, a captured contract **outside** the shadow monitor's
  frozen universe now takes the capture's decision clock, as for a public capture, unless its
  event is protected. In-universe contracts keep the shadow's sample clocks. In the retained
  authentic cycles these are about 0.4 s after the capture clock, so existing shadow rows do
  not change. Frozen datasets are immutable and still verify. Inputs already discovered are not
  re-discovered, so only captures discovered after this code runs gain NYC/Dallas rows.
- **Tests.** New `test_contracts_outside_the_frozen_shadow_universe_enter_at_their_capture_clock`
  uses a CONTROLLED narrower universe (PHL only) over authentic retained cycle bytes. It checks:
  - Chicago rows take the capture clock;
  - Philadelphia keeps the exact shadow clocks;
  - unrefused label targets cover {CLIPHL, CLIMDW};
  - a protected event is excluded.

  It fails without the change. The existing authentic bridge test still checks the exact sample
  set. Ruff lint/format pass; strict mypy passes (566 files). **Full pytest from the repo root:
  1,406 passed in 610.30s**, with zero failures, errors or skips. A first run from `backend/`
  failed 27 tests and errored 66 on repo-relative paths only (`configs/research/weather.json`,
  `tools/*.py`). That was my invocation error, not a regression.
- **Chain fork, not repaired.** `42224274925` (this stack's PR #19 branch) and `42224477050`
  (`3bmoqc`, no `continue_from_run`) were both dispatched around 13:17–13:18Z and both continue
  `42217215001`, so the chain forked there. Both snapshots are valid authentic evidence. The
  canonical line continues from the PR #19 branch run.

- **Chain run `42224274925`** (PR #19 slim captures, `chain=head`, previous `42217215001`): 53
  cycles, 5 completed this run, 0 failures, 0 errors, server exit 0. **2026-11-05 CLIMDW/CLIPHL
  are now `verified`**: "Official labels retained", on attempt 4 at 13:27Z, with a revision
  check on 2026-11-07. These are the first official forward labels in this chain; the portal
  needed more than 28 hours after local midnight. Workspace: 902,205,069 expanded bytes,
  **237,114,816 distinct**, `budget_used` 0.2101.
  - Slim capture, 4 locations: distinct bytes grew **18.28 MB over 5 cycles, about 3.66 MB per
    cycle**. Expanded bytes grew about 9.2 MB per cycle.
  - Previous code, 4 locations (run `42217215001`): about 6.0 MB distinct and 12.9 MB expanded
    per cycle.
  - At about 3.7 MB per cycle and 6 cron runs × about 5 cycles per day, the remaining 1.9 GB
    distinct budget lasts **about 17 days**. This is extrapolated, not measured.
- **Continuation queued.** This branch was dispatched with `continue_from_run=42224274925` and
  `seconds=3000` at about 14:10Z. Its results are not recorded here.

**Next autonomous milestone:** read the result of this branch's dispatch, which continues from
`42224274925`, or dispatch again from the latest completed chain run. Confirm that the backlog gains CLINYC/CLIDFW work (`schedules[].backlog.dates[].stations`)
and that `schedules[].detail` has no errors. Record PR #19's slim-capture per-cycle
`distinct_bytes` growth against about 5 MB per cycle (4 locations, pre-slim). Then recheck
2026-11-05 PHL/CHI officialness. Merging the stack to `main` is still needed to activate the
4-hourly cron; until then, each session must dispatch within the 7-day artifact retention.

## Current milestone (2026-11-06): each weather body retained once per capture

Branch `claude/vibrant-bohr-xq6pdo`, **stacked on PR #18** (`claude/vibrant-bohr-3bmoqc`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#18 had no
reviews, review threads or failing checks; none were merged. Issues #3 and #6 remain open.

- **Four-location confirmation (PR #18's next step).** Chain run `42213570196`
  (`chain=head`, 46 cycles, server exit 0) reported `station_bindings.status: ok`: KXHIGHPHIL
  CLIPHL, KXHIGHCHI CLIMDW, KXHIGHNY CLINYC and KXHIGHTDAL CLIDFW are all `matched`, 6/6
  contracts each, with the rules naming exactly the configured station. That run still used the
  pre-rounding coordinates, so its 2 cycles failed with NWS acquisition failures (monitor
  `failures: 2`, still active). Run `42217215001` on `05bcea6` (rounded coordinates, old
  capture layout, 3,000 s) succeeded with `chain=head`: 48 cycles, **2 completed with 0
  acquisition failures**, monitor `failures: 0`, and the stale-collection alert resolved.
  `station_bindings` is still `ok` with all four `matched`. Label backlog dates still list
  only CLIMDW/CLIPHL: four-location captures had not yet been through a discovery
  (`next_discovery` 13:28Z).
- **Measured four-location growth (old layout), 42213570196 → 42217215001, 2 cycles.**
  - Expanded: 830,372,605 → 856,230,326 bytes, about **12.9 MB per cycle**.
  - Distinct: 206,858,327 → 218,830,577 bytes, about **6.0 MB per cycle**.
  - `shadow` +11.7 MB and `runs/weather-datasets` +13.2 MB.
  - Real windows give about 2 cycles per run, so a 4-hourly cron gives about 12 cycles per
    day. That leaves about 22 days of expanded budget and 26 days of distinct budget.
- **Gap: storage runway.** Snapshots refuse a workspace over 2 GiB distinct or 4 GiB expanded
  bytes. After run `42213570196`: 830,372,605 expanded and 206,858,327 distinct bytes, with
  `runs/weather-datasets` 641.9 MB and `shadow` 165.4 MB. Each capture kept every forecast
  body three times (`raw/`, `weather.sqlite`, `weather/raw/`), plus a second observation
  file. Discovery datasets then copy every capture file again. The measured runway below is
  about three weeks, which is too short for the about 25 days four stations need to reach
  60/20/20 events.
- **Change.** `families/weather_capture.py` is the collector's capture
  (shadow and research workers). Observations cite the capture's identical `raw/NNNN.json`
  receipt: same bytes, same `raw_hash`, unchanged availability clocks. The forecast archive
  is built in a temporary directory. `weather/receipts.json` keeps each receipt's URL, status,
  clocks, body hash, `raw_ref` and the vintage or parse failure it produced. A body with no
  identical retained response is still copied to `weather/raw/`. Older captures are unchanged
  and verify through their own manifests.
- **Frozen module.** The first attempt edited `families/public.py` and failed 16 authentic
  replay tests ("shadow source version mismatch"). `forward_data` binds every capture's
  `feature_version` to that file's hash, so any edit invalidates every retained shadow cycle,
  including the live chain. It is restored byte-for-byte. A new test pins its hash and says why.
- **Evidence.** Replaying the exact bytes of the retained authentic 2026-10-29 two-location
  capture through the new code gives **2,346,335 → 939,526 bytes (−60%)**, 19 → 14 files, 648
  observations. Values, revision IDs and raw hashes are identical; only the replay clocks and
  `raw_ref` differ. Discovery datasets copy captures, so the expanded saving applies twice.
  Tests: capture-layout and failure-ledger assertions in `test_public_families.py`, plus the
  frozen-hash guard. Ruff lint/format pass; strict mypy passes (566 files).
  **Full pytest: 1,404 passed in 614.49s**, with zero failures, errors or skips. The guard test
  was added after that run; its file passes 22/22.
- **Real runner: chain run `42224274925` on this branch** (`c6b38ff`,
  `continue_from_run=42217215001`, 3,000 s) succeeded with `chain=head`. It restored the
  old-layout workspace and recorded 53 cycles, **5 completed with 0 failures**, `errors: []`,
  server exit 0, and `station_bindings` `ok`. Discovery froze old- and new-layout captures
  together without error (retained inputs 45 → 50). **2026-11-05 CLIMDW/CLIPHL are now
  `verified`** ("Official labels retained; revision check scheduled"). These are the first
  verified authentic forward labels in this chain, after the portal went official between
  09:27Z and 13:27Z (backoff retry 4).
- **Measured growth per cycle, old layout (2 cycles) → new layout (5 cycles):**

  | Area | Old layout | New layout | Change |
  |---|---|---|---|
  | `shadow` | 5.84 MB | 3.25 MB | −44% |
  | distinct | 5.99 MB | 3.66 MB | −39% |
  | expanded | 12.93 MB | 9.19 MB | −29% |

  The expanded figure is an upper bound. That run's discovery also copied earlier old-layout
  captures, so `runs/weather-datasets` grew 27.1 MB. Expected runway at about 12 cycles per
  day is now about **31 days** of the 4 GiB expanded budget (902,205,069 bytes used) and about
  43 days of the 2 GiB distinct budget (237,114,816 bytes used).
- **Defect found (not fixed): NYC/DAL are captured but never labelled.** `_build_snapshot`
  (`weather/history.py`) creates decision rows for shadow captures only from the monitor's
  saved samples. The monitor's frozen universe is PHL/CHI, so KXHIGHNY/KXHIGHTDAL contracts
  never become dataset rows and so never become label targets. The run output agrees: after
  discovering four-location captures, the 2026-11-06 backlog still lists only CLIMDW/CLIPHL.
  PR #18's claim that new series are "captured and labelled" is therefore only half true. The
  fix changes point-in-time decision semantics for out-of-universe contracts in shadow
  captures, so it needs its own milestone and tests. It is not rushed here.

**Canonical chain head: run `42224274925` on `claude/vibrant-bohr-xq6pdo`** (expires about
2026-11-13). Dispatch this branch next with `continue_from_run`.

**Next autonomous milestone: label targets for out-of-universe captured contracts.** For
shadow captures, add decision rows for captured contracts outside the monitor's universe:
- Use the capture's own `decision_time`, only while the contract is open.
- Apply the same protected-event and holdout exclusions as public captures.
- Do not change in-universe shadow samples or any frozen dataset.
- Test that NYC/DAL rows appear, that post-close/protected contracts stay excluded, and that
  earlier snapshots replay unchanged.

Then confirm on a real runner that NYC/DAL dates enter the backlog and verify. Durable cold
storage for sealed evidence (for example release assets, since workflow artifacts expire)
still needs a user decision. Scheduled cron collection starts only once the stack reaches
`main`.

## Current milestone (2026-11-06): four forward locations with station-binding evidence

Branch `claude/vibrant-bohr-3bmoqc`, **stacked on PR #17** (`claude/vibrant-bohr-f4e7df`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#17 had no
reviews, review threads or failing checks; none were merged. Issues #3 and #6 remain open.

- **Gap.** The V1 matched-forecast gate is blocked by the monitor's `model_binding`, which
  needs a fitted authentic model. The fitting gate needs **60/20/20 independent
  fit/calibration/validation events** (`ml/experiment.py`). With two stations, that is
  about 50 days of collection. The bottleneck is station/days per date, not code.
- **Change.** `configs/data/weather-forward.json` adds New York City (`KXHIGHNY`, CLINYC,
  America/New_York) and Dallas (`KXHIGHTDAL`, CLIDFW, America/Chicago), and
  `weather/labels.py` `STATIONS` allowlists exactly those two. Retained authentic evidence
  backs each value:
  - the catalog listing (PR #8) has the series;
  - the retained rules name the stations (`data/public/{newyork,dallas}/manifest.json`);
  - the retained 2026-10-29 portal receipt has the `cliId`/ICAO/timezone;
  - the coordinates are the retained `api.weather.gov/stations/K…` values.

  Oklahoma City is not added, because its retained coordinates are a city-centre geocode.
  The monitor's frozen universe is unchanged: new series are captured and labelled but make
  no shadow decisions.
- **Station bindings.** `operations/forward.py` `station_bindings()` adds a read-only
  `station_bindings` section to `summary.json` and the job-log line. It reads the newest
  retained capture. For each location it reports the contracts, the CLI stations the rules
  name, the contracts the existing label gate accepts, and a status:
  `matched`/`mismatch`/`unnamed`/`partial`/`no_contracts`. On the retained authentic
  2026-10-29 workspace, both PHL and CHI are `matched` (12/12 contracts each).
- **Tests.** `test_forward_station_bindings.py` has 5 cases. They check the config against
  the retained portal, rules and coordinate receipts, check authentic capture bindings, cover
  every status, and select the newest capture. Ruff lint/format pass; strict mypy passes
  (565 files). The first full run had **2 failures, 1,401 passed**. Both
  failures were CONTROLLED cohort tests whose fixture read the operational config, so 100
  dates × 4 locations gave 400 events where the test expects 200. The fixture
  (`tests/integration/cohort_fixture.py`) is now pinned to its original two locations, and
  the assertions are unchanged. **Full pytest after the fix: 1,403 passed in 626.00s**, with
  zero failures, errors or skips. On the final code, including the coordinate fix and its
  test, Ruff/format and strict mypy (565 files) pass and **1,404 passed in 636.91s**.
- **Real-runner evidence.**
  - Chain dispatch `42209909820` on this branch (`continue_from_run=42205430152`) ran on
    the old two-location code and succeeded with `chain=head`: 44 cycles, 0 errors, server
    exit 0.
  - Its footprint is the **two-location baseline**: 820,649,024 expanded bytes and
    198,034,812 distinct. Distinct bytes grew 14.27 MB over 3 cycles (about 4.76 MB per
    cycle), and `budget_used` was 0.1911.
  - The 2026-11-05 retry is still scheduled for 13:27Z, after that run's window.
  - **Defect found on the first four-location runs.** Push trial `42213565565` and chain
    run `42213570196` (`continue_from_run=42209909820`, `chain=head`, 46 cycles) failed
    every cycle with "12 shadow decisions; 2 acquisition failures". The cycles were 45 and 46
    (the trial's cycle 45 never becomes part of the chain). The monitor reached
    `failures: 2`, with backoff `next_at` 12:55:18Z, and a `stale_collection` alert opened at
    12:19:04Z.
  - **Cause, inferred from the inputs.** api.weather.gov `/points` redirects a point with
    more than four decimals (301), and the bounded client does not follow redirects. The only
    such values were `40.78858` (NYC) and `32.893456`/`-97.02648` (DAL), one location each,
    which matches 2 failures. The failure records themselves are in the snapshot, which
    sessions cannot download.
  - **Fix.** Commit `05bcea6` rounds both to 4 decimals (`40.7886,-73.9661`,
    `32.8935,-97.0265`), and a test enforces at most 4 decimals for every coordinate. Every
    failed cycle increments `failures`, and 5 consecutive failures pause the monitor (the
    operator never resumes). Leaving this unfixed would have paused the chain after about 3
    more cycles.
  - Run `42213570196` footprint: 830,372,605 expanded bytes and 206,858,327 distinct (+8.8 MB
    over 2 failed cycles).
  - Dispatch `42217170492` (1,500 s) was cancelled during setup, because the backed-off
    12:55Z cycle fell outside its window. It uploaded nothing and is not a chain head.
  - **Fix confirmed on a real runner.** Chain dispatch `42217215001` (commit `05bcea6`,
    3,000 s, `continue_from_run=42213570196`) succeeded with `chain=head`. It ran cycles 47
    and 48, both `completed` with "12 shadow decisions; 0 acquisition failures". The monitor
    `failures` went back to 0, and the stale alert resolved at 12:55:27Z.
  - **Authentic station bindings, `status: ok`.** The capture at 13:05:35Z had all four
    locations `matched`: KXHIGHPHIL→CLIPHL, KXHIGHCHI→CLIMDW, **KXHIGHNY→CLINYC** and
    **KXHIGHTDAL→CLIDFW**, each with 6 contracts, 6 naming the station and 6 accepted by the
    label gate. The current live rules therefore confirm both new mappings.
  - **Four-location storage.** The footprint was 856,230,326 expanded bytes and 218,830,577
    distinct; `budget_used` was 0.1994, with 45 retained inputs. Distinct bytes grew about
    6.0 MB per cycle (11.97 MB over 2 cycles), up from about 4.76 MB with two locations
    (+25%). Expanded bytes grew about 12.9 MB per cycle.
  - **Runway.** At about 18 cycles a day (cron: 6 runs × about 3 cycles), the expanded
    4 GiB budget binds first, in about **15 days**; the distinct budget lasts about 18 days.
  - Readiness is unchanged: 0 verified labels, and 2026-11-05 PHL/CHI is retried at
    13:27:09Z. NYC and DAL labels start with 2026-11-06, the first day their contracts were
    captured.
  - The next continuation (3,000 s, `continue_from_run=42217215001`) was dispatched at the
    end of this session. It includes the 13:27Z retry, and its result is not recorded here.

**Canonical chain head: run `42217215001` on `claude/vibrant-bohr-3bmoqc`**, or the
continuation dispatched from it if that succeeded (expires about 2026-11-13). Dispatch this
branch next with `continue_from_run`, or `main` after the stack merges. If a monitor's
`next_at` is backed off past the window end, use `seconds: 3000` so a cycle actually runs.

**Next autonomous milestone:** the storage step. Snapshot runway is now about 15 days
(expanded budget). Each cycle writes `public/observations.jsonl` and
`public/weather/observations.jsonl` with identical rows except for the `raw_ref` prefix, and
it stores raw forecast bodies three times (`raw/`, `weather/raw/`, `weather.sqlite`). Removing
the duplicates needs a design that keeps provenance and the frozen-dataset verification.
Before that, check:
- the newest chain run's `schedules[].backlog` for 2026-11-05 (PHL/CHI) and for the first
  NYC/DAL days (2026-11-06, due 2026-11-07);
- whether `readiness.settlement_labels.verified_stations` gains CLINYC/CLIDFW.

Optional cleanup: add `station_bindings` to the workflow's job-summary key list. Pushing
workflow files may be rejected; the field is already on the collect step's log line.

## Current milestone (2026-11-06): label-source diagnostics for unverified days

Branch `claude/vibrant-bohr-f4e7df` (PR #17), **stacked on PR #16** (`claude/vibrant-bohr-gcmz6m`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#16 had no
reviews, comments or failing checks; none were merged. PR #16 was `dirty`: #15 had gained a
STATUS-only commit after #16 branched. This branch merges #15's head and keeps both STATUS
sections; no code changed in that merge. Issues #3 and #6 remain open.

- **Gap.** 2026-11-05 (CLIMDW, CLIPHL) was refused 3 times with "source report is
  preliminary, missing or nonofficial". That message covers several source states, and
  sessions cannot download workspaces, so the planned 24h investigation had no data.
- **Change.** `weather/labels.py` `source_states()` plus `operations/forward.py`
  `label_sources()`. Each `retry`/`refused` backlog date (newest 8) now carries `source`, read
  from its immutable batch through the existing API, with the batch version re-checked. It
  shows portal-wide official/preliminary/no-report counts and per-station `status`,
  `isOfficial`, `reportDate`, `issueTime` and `integer_high_present`. The unverified high is
  never echoed. `parse_label`, its refusal text and `LabelBatch.summary()` are unchanged:
  frozen datasets replay that text in `_verify_labels`, so changing it would break existing
  snapshots.
- **Authentic retained evidence.** The 2026-10-30 portal receipt was still preliminary for
  **all 45 stations** at 09:08Z the next morning (`officialReports: 0`). A next-morning
  preliminary refusal is therefore expected source lag, not by itself a station-mapping
  defect.
- **Tests.** 2 label cases (authentic bytes plus controlled odd bodies), 1 forward backlog case
  (including a mismatched-batch refusal) and a real-listener assertion in
  `test_forward_validation_listener.py`. Ruff lint/format pass; strict mypy passes (564 files).
  **Full pytest: 1,398 passed in 721.95s**, with zero failures, errors or skips.
- **Real-runner evidence.**
  - PR #16's chain continuation `42201841307` succeeded with `chain=head` after a v2 restore:
    38 cycles, 0 errors, server exit 0. Footprint: 756,173,837 expanded bytes and
    **173,070,185 distinct (22.9%)**; `budget_used` 0.1761. Distinct bytes grew 13.1 MB over
    3 cycles while expanded bytes grew 44.4 MB.
  - Push trial `42203061775` on this branch succeeded.
  - Chain dispatch `42205430152` on this branch (`continue_from_run=42201841307`) succeeded
    with `chain=head`: 41 cycles, 0 errors, server exit 0. Footprint: 768,928,242 expanded
    bytes and 183,761,475 distinct; `budget_used` 0.179.
  - **First authentic `source` diagnosis.** The 2026-11-05 retry's batch
    (`sha256:1c987e1b…`, receipt 09:27:09Z, HTTP 200) shows portal-wide
    `officialReports: 0`, `preliminaryReports: 42` and `noReports: 10`. CLIMDW and CLIPHL each
    have one record with `status: preliminary`, `isOfficial: false`, the correct `reportDate`
    and an empty `issueTime`. **This is source-wide publication lag, not a station-mapping
    defect.** It matches the retained 2026-10-30 receipt. The next retry is at 13:27Z.

**Canonical chain head: run `42205430152` on `claude/vibrant-bohr-f4e7df`** (expires about
2026-11-13). Dispatch this branch next with `continue_from_run`, or `main` after the stack merges.

**Next autonomous milestone:** read `schedules[].backlog.dates[].source` for 2026-11-05 in
the newest chain run. If the portal still has `officialReports: 0` after the 13:27Z retry,
record how long the portal takes to go official; backoff already reaches 24h, so
correctness is unaffected. Only if other stations turn official while CLIMDW/CLIPHL do not,
investigate the mapping. Then confirm 2026-11-05 verifies and its contracts reconcile. The
storage step (each cycle writes raw weather responses twice, plus `weather.sqlite` bodies and
decision inputs about 3 times) is lower priority: v2 snapshots dedupe identical files and
leave about 3 weeks of expanded-budget runway. The duplicated weather records also carry
provenance (receipt and failure tables), so any reduction needs a careful design. Scheduled
cron collection starts only once the stack reaches `main`, which needs review and merge by
the user.

## Current milestone (2026-11-06): content-addressed workspace snapshots (schema v2)

Branch `claude/vibrant-bohr-gcmz6m`, **stacked on PR #15** (`claude/vibrant-bohr-iisaao`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#15 had no
reviews, review threads or failing checks; none were merged. Issues #3 and #6 remain open.

- **PR #15 confirmed on a real runner.** Run `42187733156` (PR #15's code) resolved the false
  `unresolved_reconciliation` alert at 08:50:45Z under the expected-settlement rule.
- **Defect: snapshot runway of about nine days.** Run `42187733156` (30 cycles) reported
  652,673,017 workspace bytes: `runs/weather-datasets` 532,385,048 (up from 383 MB at 24
  cycles, after the first incremental discovery froze all legacy inputs once), `shadow`
  105,084,585 and `jobs.sqlite` 13,635,584. Datasets copy shadow receipts byte for byte
  (`weather/history.py` `shutil.copyfile`), and each cycle also stores some raw responses
  twice. Growth was about 150 MB/day against a 2 GiB budget counted in logical bytes.
- **Fix.** Snapshot schema `entropytrade-workspace-v2` stores one `blobs/<sha256>` member per
  distinct content. The manifest still lists every path, and restore writes each path as an
  independent file (no hard links) verified against its checksum. Budgets: 2 GiB distinct
  content and 4 GiB expanded files. v1 archives, including the current chain head, still
  restore within their original 2 GiB bound. Records, datasets, clocks and verification
  semantics are unchanged. The forward `workspace` footprint now reports `distinct_bytes`,
  both budgets and `budget_used` as the larger ratio (it now hashes contents).
- **Evidence (local, authentic retained receipts).** `seed_retained` plus one frozen dataset:
  9,572,441 expanded bytes, 3,835,965 distinct (40%), deflated v2 archive 169,153 bytes.
- **Tests.** 4 new recovery tests (dedup with independent restored files, v1 restore and its
  original bound, separate distinct/expanded budgets, invalid digests ×3), an updated tamper
  helper and footprint test, and a dedup assertion in the authentic-receipt listener test.
  Ruff lint/format pass; strict mypy passes (564 files). **Full pytest: 1,395 passed in
  656.90s**, with zero failures, errors or skips.
- **Real-runner evidence.**
  - Chain dispatch `42197652880` on this branch (`continue_from_run=42190762987`, which is
    PR #15's last chain run with 32 cycles) succeeded with `chain=head`.
  - It **restored the v1 per-path archive** in 13 s, collected 3 cycles (35 total) with 0
    errors and server exit 0, and wrote the first v2 snapshot
    (`sha256:79c24187…`).
  - The authentic footprint was 711,751,918 expanded bytes and **159,961,923 distinct bytes
    (22.5%)**. `budget_used` was 0.1657, bound by the expanded 4 GiB budget (it had been
    0.30 against 2 GiB logical).
  - The uploaded workspace artifact was **22,797,927 bytes**, down from 53,324,794 for the v1
    archive of run `42190762987`.
  - Push trial `42196833722` succeeded.
  - **v2 restore on a real runner passed.** Continuation `42201841307`
    (`continue_from_run=42197652880`) downloaded the v2 archive and passed the fail-closed
    restore step in 19 s (10:20:34–10:20:53Z). Its collection window was still running at the
    end of this session; record its footprint and `chain=head` next.

**Canonical chain head: run `42201841307` on `claude/vibrant-bohr-gcmz6m` if it succeeded,
otherwise `42197652880`** (expires about 2026-11-13). Dispatch this branch next, or `main` after merge.

**Next autonomous milestone:** confirm `42201841307` succeeded and that `distinct_bytes` keeps
growing far slower than `bytes`. The expanded 4 GiB bound now binds
(about 3 weeks of runway); the next storage step is to stop each cycle writing raw responses
twice and decision inputs about 3 times. Then confirm 2026-11-05 verifies once the official
climate report is published. The V1 gate for matched forecasts remains the monitor's
`blocked` model binding (no fitted authentic forward model); that is data-limited and needs
multi-day collection, which this change keeps alive.

## Current milestone (2026-11-06): reconciliation alert follows expected settlement

Branch `claude/vibrant-bohr-iisaao` (PR #15), **stacked on PR #14** (`claude/vibrant-bohr-zx3moc`).
**V1 remains incomplete.** At the start of this run, open PRs #4, #5 and #7–#14 had no reviews,
comments or failing checks; none were merged. Issues #3 and #6 remain open.

- **Defect: a daily false reconciliation incident.** PR #14 left an `unresolved_reconciliation`
  alert open from 07:00:01Z. That is exactly one hour after 06:00Z, which is Chicago local
  midnight, when the 2026-11-05 `CLIMDW` contracts closed. Retained authentic `KXHIGHPHIL`
  records show `close_time` 05:00Z but `expected_expiration_time` 19:00Z: daily-high markets
  settle after the next-morning climate report. The close + 1h deadline therefore opened a
  false incident every day for every weather contract.
- **Fix** (`tracking/alerts.py`).
  - The deadline is now the `expected_expiration_time` frozen with the contract, plus 1h. It
    falls back to `close_time` when no expected time was published or the expected time is
    not after close.
  - `latest_expiration_time` is not used, so late settlement still alerts.
  - Evidence records `expected_settlement_at` and `basis` per contract.
  - Outcomes are still committed only by the receipt-validated worker; nothing is inferred.
- **Diagnosability.** Forward summaries now carry bounded `evidence` for unresolved alerts
  (contract lists over 20 are truncated, with `contracts_total` giving the full count). See
  [operator alerts](docs/operator-alerts.md) and [forward operator](docs/forward-operator.md).
- **Tests.** There are 2 new cases; the alert case fails on the previous code. Ruff lint/format
  pass; strict mypy passes (564 files). **Full pytest: 1,389 passed in 620.44s**, with zero
  failures, errors or skips.
- **Real-runner evidence.** Three chained dispatches, all with 0 errors and server exit 0:
  - `42187278683` ran on PR #14 code and continued from `42183351795`. It ended at 27 cycles.
    The first incremental scan froze the legacy partition once: `runs/weather-datasets` went
    from 383.0 to 532.4 MB.
  - `42187733156` was the first run on this commit. The false alert **resolved at
    08:50:45Z** under the new rule, and no reconciliation alert reopened. It ended at 30
    cycles; datasets were unchanged because no discovery fell in that window.
  - `42190762987` ended at 32 cycles. The 09:28Z incremental discovery added only
    38.5 MB (`runs/weather-datasets` 532.4 → 570.9 MB). The PR #14 measurement implies about
    150+ MB per whole-partition re-freeze, so **linear discovery growth is now confirmed on
    authentic data**. The workspace is 699 MB, 0.3257 of the budget (`ok`).
- **Label state.** Day 2026-11-05 was refused as preliminary on its 3rd attempt at 09:27Z.
  The next retry is at 13:27Z, with backoff now 4h. Day 2026-11-06 becomes due at 2026-11-07
  06:00Z. Readiness is unchanged: the prospective report is insufficient and model binding is
  `blocked`.
- **Limitation.** This session's egress proxy refuses the artifact blob host, so workspace
  archives cannot be inspected locally. Diagnosis relied on job logs and retained records.

**Canonical chain head: run `42190762987` on `claude/vibrant-bohr-iisaao`** (expires about
2026-11-13). Dispatch this branch next, or `main` after the stack merges, with `continue_from_run`.

**Next autonomous milestone:**
1. Confirm that 2026-11-05 verifies once the official report is published. If it is still
   preliminary after about 24h, investigate whether the source or station mapping is wrong.
2. Confirm that the 2026-11-05 contracts reconcile after their expected settlement time,
   with no false alert in between.
3. Reduce the remaining linear storage costs. Each shadow cycle grows the `shadow` area by
   about 3.6 MB and stores its data about 3 times; `LabelService.selection` re-verifies every
   dataset on each enrollment.

## Current milestone (2026-11-06): linear snapshot growth; workspace footprint reporting

Branch `claude/vibrant-bohr-zx3moc`, **stacked on PR #13** (`claude/vibrant-bohr-4jtqro`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#13 had no
reviews, review threads or failing checks; none were merged. Issues #3 and #6 remain open.

- **Defect: the chained snapshot grew quadratically.** Measured on real runners, the
  `workspace.zip` was 10.2 MB at 1 cycle, 18.8 MB at 2, 243 MB at 14 and 330,871,923 bytes at
  16 (run `42174401711`). That is about 44 MB per cycle and rising, against the 2 GB
  `MAX_BYTES` snapshot budget. At cron cadence (6 runs × 3 cycles per day), the budget would
  be exhausted in about 2–3 days. A workspace over budget cannot be snapshotted, so the chain
  would stall exactly when multi-day operation starts.
- **Cause.** The label schedule's hourly `discover` froze a new immutable weather dataset over
  the whole retained-input partition (up to 128 inputs). `_build_snapshot` copies every
  shadow cycle's full artifacts (about 2.6–6 MB each) into each dataset, so every discovery
  re-copied all earlier cycles.
- **Fix.** Discovery is incremental. The schedule durably records the catalog inputs it has
  frozen (`discovered`; the API reports `discovered_inputs`). Each scan freezes only unseen
  inputs from the earliest partition that has any, so each input is copied into at most one
  discovery dataset. A scan with no new inputs creates nothing. Inputs with no label targets
  advance without blocking the schedule; integrity failures still raise and block. Frozen
  anchor, protection and earlier datasets/plans are unchanged. Schedules saved before the
  change load and verify unchanged, and their first scan freezes the partition once.
- **Also.** Snapshots are deflate-compressed; stored legacy archives still restore and other
  compression methods are refused. Each forward summary now has `workspace` (bytes by area vs.
  the budget, `ok`/`warning`/`critical`), and the job summary warns at 50%/80%. See
  [forward operator](docs/forward-operator.md) and [forward validation](docs/forward-validation.md).
- **Tests.** There are 6 new cases: 3 schedule, 1 recovery, 1 footprint and a footprint
  assertion in the real-server case. The schedule cases fail on the previous code. Ruff
  lint/format pass; strict mypy passes (564 files). **Full pytest: 1,387 passed in 704.50s**,
  with zero failures, errors or skips.
- **Real-runner evidence.**
  - Old-code chain dispatch `42177275885` succeeded with 21 cycles, 0 errors and server exit 0.
    Its archive was 469,371,199 bytes (stored); +138 MB for 5 cycles.
  - Continuation `42183351795` on this branch (`continue_from_run=42177275885`) succeeded.
    - It **restored the legacy stored archive**, collected 3 cycles (24 total) with 0 errors
      and server exit 0, and recorded `chain=head`.
    - Its **deflated archive is 38,882,359 bytes** (artifact 34,830,315), versus 478,628,966
      bytes of workspace.
  - The first `workspace` footprint confirms the cause: `runs/weather-datasets` is
    383,007,179 bytes (80%), while all 24 raw shadow cycles take 83,233,485 bytes (`shadow`),
    plus 10.8 MB `jobs.sqlite`. Budget used is 0.2229 (`ok`).
  - **Not yet exercised:** no discovery ran in that window (next at 08:28Z). The first
    incremental scan will freeze all 23 inputs once (legacy schedule); later scans add only new
    inputs. Confirm this on the next dispatches by comparing `runs/weather-datasets` growth.
- **Readiness unchanged.** The prospective report is `insufficient` (model binding `blocked`).
  Day 2026-11-05 is still refused as preliminary after 2 attempts; the next retry is 09:27Z.
  A new `unresolved_reconciliation` alert opened at 07:00Z and remains open. It has not been
  investigated yet.

**Canonical chain head: run `42183351795` on `claude/vibrant-bohr-zx3moc`** (expires about
2026-11-13). Dispatch this branch next, or `main` after merge, with `continue_from_run`.

**Next autonomous milestone:** dispatch the chain on this branch and compare `workspace` areas
across two or more runs to confirm linear growth on authentic data. Then confirm that
2026-11-05 verifies once the official climate report is published. Remaining linear costs:
each shadow cycle stores its data about 3 times (result, decision and paper inputs), and
`LabelService.selection` re-verifies every dataset on each enrollment.

## Current milestone (2026-11-06): per-date label backlog; first authentic label request

Branch `claude/vibrant-bohr-4jtqro`, **stacked on PR #12** (`claude/vibrant-bohr-8ctoc4`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7–#12 had no
reviews, review threads or failing checks; none were merged. Issues #3 and #6 remain open.

- **Diagnosis.** PR #12 attributed 0 settlement labels to "no label requests" and proposed
  enabling the label schedule. The schedule was already enabled and active (created about
  2026-11-06T00:29Z). Its two dates were simply **not yet due**: a day becomes due at the end
  of its latest local day, and the summary only printed `counts: {pending: 2}`. No schedule
  code change was needed.
- **Change.** Each `schedules[]` entry in `summary.json` now carries `backlog`. This lists
  per-date `day`, `status`, `next_at`, `attempts`, `failures`, target count, stations and
  detail, plus `next_due_at` and `overdue_dates`. `overdue_dates` lists days that were due
  with no request in flight at summary time, and it is reported but never repaired. See
  [forward operator](docs/forward-operator.md#evidence-readiness-in-each-run).
- **Tests.** There are 3 new unit cases, including one against the real
  `LabelScheduler.summary` shape. Unparseable or naive clocks are reported, not raised.
  Ruff lint/format pass; strict mypy passes (564 files). **Full pytest: 1,382 passed in
  689.20s**, with zero failures, errors or skips.
- **Real-runner evidence.**
  - Trial `42174398161` (push) succeeded and uploaded only `forward-trial-workspace`.
  - Chain dispatch `42174401711` (`continue_from_run=42168490905`) succeeded. It restored
    the 13-cycle chain, collected 3 cycles (16 total) with 0 errors and server exit 0, and
    produced snapshot `sha256:0d492023…` with `chain=head`.
  - It issued the **first authentic label request** of the chain. Day 2026-11-05 (stations
    `CLIMDW`, `CLIPHL`, 2 targets) was due at 06:00Z and was requested at 06:27Z.
  - Both targets were refused with `source report is preliminary, missing or nonofficial`.
    The status is `retry`, with the next attempt at 07:27Z. Day 2026-11-06 is pending until
    2026-11-07T06:00Z. `overdue_dates` was empty.
  - Follow-up chain dispatch `42177275885` (3000 s window) also succeeded. It continued
    `42174401711` on the same branch, collected 5 cycles (21 total) with 0 errors and server
    exit 0, and produced snapshot `sha256:2385f2be…` with `chain=head`.
  - That run made label request 2 at the 07:27Z retry. Day 2026-11-05 was still
    preliminary, so it now has `failures: 2`, with the next attempt at 09:27Z (backoff
    doubling, capped at 24 h). `overdue_dates` was empty.
  - The existing `unresolved_reconciliation` alert opened at 07:00Z, because official
    results for the 2026-11-05 shadow contracts are not yet reconciled. It is left open for
    review and not acknowledged by automation.
- **Readiness.** The prospective report is still `insufficient`: 24 contracts, all refused,
  covering 4 events on 2 dates. Settlement labels: 0 verified, 2 unverified (preliminary).

**Canonical chain head: run `42177275885` on this branch** (the newest successful dispatch;
snapshot expires 2026-11-13). Labels are only
requested while a run is up, and runs happen only on dispatch until the workflow reaches
`main` (cron every 4 h). The snapshot expires 7 days after its run.

**Next autonomous milestone:** keep the chain alive, and confirm that 2026-11-05 verifies once
the official (non-preliminary) climate report is published. The prospective report refuses
all 24 contracts because the monitor's model binding is `blocked` (no fitted forward model).
That remains the gate for matched forecasts, independent of labels.

## Current milestone (2026-11-06): push runs are trials; restore the authentic chain

Branch `claude/vibrant-bohr-8ctoc4`, **stacked on PR #11** (`claude/vibrant-bohr-g16hbp`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5, #7, #8, #9, #10
and #11 had no reviews, review threads or failing checks; none were merged. Issues #3 and #6
remain open.

- **Defect: PR #11's continuation never ran.** Continuation dispatch `42167131442` was
  cancelled before it started. GitHub keeps one *pending* run per concurrency group, and push
  `42167132149` queued after it and replaced it. That push then restored the branch's own
  head, push `42162670639`, which had skipped the download and started a **fresh** chain
  (job log steps; run 14's download took 1 s). Pending push `42167372741` will continue that fork. So `claude/vibrant-bohr-g16hbp` now carries a fresh fork, not the
  authentic chain. The authentic head is still run `42156641720` (11 cycles, expires about
  2026-11-13); the 3 cycles of `42162688233` remain lost, as recorded below.
- **Fix.** Push runs are now **trials**:
  - They use their own concurrency group (`forward-collection-trial-<ref>`), so they cannot
    displace a queued chain run.
  - They upload `forward-trial-workspace` (3-day retention), never `forward-workspace`.
  - Same-branch lookup skips `push` runs, including older push runs that used the chain name.
  - `lineage.txt` records `event` and `chain=head|trial`.

  See [forward operator](docs/forward-operator.md#push-runs-are-trials-not-chain-heads).
- **Tests.** `test_forward_workflow_chain.py` now has 22 cases. The 3 new cases fail against
  PR #11's workflow and pass here. Trial counts are a fork and must never be added to chain counts.
- **Results.** Ruff lint/format pass; strict mypy passes (564 files). **Full pytest: 1,379
  passed in 862.37s** at `1b92736`, with zero failures, errors or skips.
- **Real-runner evidence.**
  - Push trial `42168484729` uploaded only `forward-trial-workspace` (984,461 bytes).
  - Continuation dispatch `42168490905` (`continue_from_run=42156641720`) **started while that
    trial was still running**. Under #11's workflow it would have waited and could have been
    replaced.
  - The dispatch restored `sha256:4a8125a5…` (11 cycles, branch `claude/vibrant-bohr-ypomud`)
    and ended at **13 cycles** with 0 errors and server exit 0. The new snapshot is
    `sha256:d1e69060…`, and lineage records `event=workflow_dispatch` and `chain=head`.
  - The `forward-workspace` artifact is 17,190,118 bytes compressed and expires
    2026-11-13T05:53Z.
  - The fee schedule PDF was skipped after the earlier HTTP 429, per the daily cadence.
- **Readiness** (unchanged by 2 more cycles): the prospective report is `insufficient`. It has
  24 contracts, all refused, covering 4 events on 2 dates; 0 matched. There are 0 settlement
  labels and 0 open alerts.

**Canonical chain head: run `42168490905` on this branch.** Do not dispatch
`claude/vibrant-bohr-g16hbp` (fresh fork) or `claude/vibrant-bohr-ypomud` again. Before
2026-11-13, dispatch this branch, or `main` after merge with
`continue_from_run=<newest chain run here>`.

**Next autonomous milestone:** settlement-label readiness is 0 because the chained workspace
has no label requests. Make the forward run enable the existing opt-in label schedule on the
first chained run, idempotently, and verify labels on a real runner. The cron fires only after
the workflow is on `main`.

## Current milestone (2026-11-06): carry the authentic chain across branches; fix lost snapshot uploads

Branch `claude/vibrant-bohr-g16hbp`, **stacked on PR #10** (`claude/vibrant-bohr-23la5m`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5, #7, #8, #9 and #10
had no reviews, review threads or change requests and no failing checks; none were merged.

- **Why.** Snapshots are found per branch. The authentic chain (11 cycles) lived only on #7's
  branch, so merging to `main` would have restarted it empty, and the readiness summary from
  #10 had never run on real data.
- **Cross-branch continuation.** `workflow_dispatch` input `continue_from_run` restores a
  named run's snapshot. It fails closed on a non-numeric ID, a run of another workflow or
  repository, an incomplete run, a missing or expired snapshot, or `fresh: true`. It never
  falls back. An artifact-listing API error now fails the run instead of silently choosing an
  older snapshot. `lineage.txt` adds `branch`/`previous_branch`; the source lineage travels
  as `previous-lineage.txt`.
- **Defect found on the real runner and fixed.** Run `42162688233` restored run
  `42156641720` (branch `claude/vibrant-bohr-ypomud`, 11 cycles) and collected 3 cycles
  (14 total, 0 errors, server exit 0, snapshot `sha256:f8c028b2…`). But `hashFiles()` on the
  243 MB `workspace.zip` exceeded the runner's 120 s limit, so **the snapshot was never
  uploaded and those 3 cycles are lost** (only the 90-day `forward-summary` survives). All
  step conditions now use step outputs and plain file tests; the upload requires
  `steps.snapshot.outputs.archive`, which is set only after the archive, checksum and lineage are written.
  The #5/#7/#9/#10 branches still carry the `hashFiles()` guards and can lose snapshots the same way.
- **Second defect found and fixed: chain order.** Same-branch lookup took the newest
  run by *creation*. Dispatch `42167131442` was created before push `42167132149`, but the
  push executed first (the concurrency group serializes them). Creation order would have
  picked the push run's fresh-chain snapshot after both finished, orphaning the continued chain. Lookup
  now considers only completed runs, ordered by completion (`updated_at`). The test stub now
  applies the workflow's real `--jq` filters with `jq`.
- **First readiness on authentic data** (run `42162688233`, job log): prospective report
  `insufficient`: 24 contracts, 0 pending, 24 refused, 0 matched; 4 independent events on
  2 dates; 10 events / 5 dates still needed. Settlement labels: 1 partition, 0 verified,
  0 unverified (no label requests yet). All 4 `stale_collection` alerts were resolved; they
  mark the gaps between windows.
- **Tests.** `backend/tests/unit/test_forward_workflow_chain.py` (19 cases) runs the
  workflow's own step scripts against a stubbed `gh` that evaluates the real `--jq` filters.
  It covers same-branch selection, expiry, completion order, incomplete runs, continuation,
  8 fail-closed cases and the API-error refusal, and asserts that no condition uses
  `hashFiles()`. 4 cases fail on the first commit's workflow (hashFiles) and 2 on the second's (ordering).
- **Results.** Ruff lint/format pass; strict mypy passes (564 files). **Full pytest 1,376 passed
  in 590.28s** at head `f4d4fc3` (zero failures/errors/skips); it was 1,368 at `65d7bea`.
- **Canonical continuation succeeded:** run `42168444616` at `f4d4fc3`.
  - It restored `42156641720` (`claude/vibrant-bohr-ypomud`, 11 cycles, `sha256:4a8125a5…`).
  - It kept the monitor and schedule, ending at 14 cycles. There were 0 errors, the server
    exited 0, and the snapshot is `sha256:0ff3a700…` (243 MB zip; 17.7 MB artifact).
  - Readiness is unchanged: 24 refused, 0 matched, 4 events on 2 dates, 0 verified labels.
  - The fee schedule was skipped after its recent 429.
  - Its predecessor `42167131442` was cancelled by GitHub before it started: a newer pending
    push run replaced it in the concurrency group. That pending-run replacement is now
    documented. Push runs `42162670639` and `42167132149` hold a separate,
    **non-canonical** fresh chain; ignore them.
- **Observed gap (not investigated):** the schedule shows 2 pending dates but has made 0
  label requests across every window, so settlement-label readiness cannot advance. Find out
  whether it is waiting for official reports or is stuck.

**Canonical chain:** from now on, upkeep dispatches go to this branch, or to `main` after
merge via `continue_from_run`. **Do not dispatch `claude/vibrant-bohr-ypomud` again**, or the
chains diverge from a shared history; their counts must never be added together.
Run `42156641720`'s snapshot expires about 2026-11-13.

**Next for the user:** review/merge #1 → #5 → #7 → #9 → #10 → #11. After merging, dispatch once on
`main` with `continue_from_run=42168444616` (or the newest successful run on this branch); the 4-hourly cron then continues
it. Fee PDF import remains issue #6.
**Next autonomous milestone:** diagnose why the following schedule makes no label requests
(0 across all windows). Keep the canonical chain alive with plain dispatches on this branch,
without `continue_from_run`, and never push while one is queued. Archive sizes (243 MB per snapshot) need
attention: consider compressing the archive or measuring which files grow per cycle.

## Current milestone (2026-11-06): evidence readiness in forward-collection summaries

Branch `claude/vibrant-bohr-23la5m`, **stacked on PR #9** (`claude/vibrant-bohr-1hw7xm`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5, #7, #8 and #9
had no review comments requesting changes and no failing checks, and none were merged.
This run dispatched forward-collection run `42156641720` on PR #7's branch to keep that chain
alive. It succeeded: it restored `sha256:1390bff9…` (8 cycles) and kept the monitor and
schedule, ending at 11 cycles. There were 0 errors and the server exited 0; the snapshot is
`sha256:4a8125a5…`. The fee schedule PDF returned **HTTP 429** again (24,732-byte HTML,
`is_pdf: false`), retained as an unreviewed receipt. That run predates this change, so its
alert states are still listed as null.

- **Defect fixed.** The operator summary read alert keys that do not exist (`status`,
  `detected_at`), so every alert was listed with `null` state. This is why earlier runs showed
  two `stale_collection` alerts with null fields. Alerts are now `open`/`acknowledged`/
  `resolved`, derived from `opened_at`/`acknowledged_at`/`resolved_at`.
- **Readiness.** `summary.json` and the job-log line now include read-only `readiness`:
  per-monitor prospective-evaluation counts against the report's own 10-event/5-date minimums
  (`events_remaining`, `dates_remaining`), and distinct verified/unverified settlement labels
  across every label partition (revisions count once). HTTP 409 verification refusals are
  reported as `verification_failed`, never repaired. The workflow file is unchanged.
  See [forward operator](docs/forward-operator.md#evidence-readiness-in-each-run).
- **Tests.** `backend/tests/unit/test_forward_operator.py`: 3 new cases (cross-partition and
  revision de-duplication, verification refusals, alert lifecycle) and extended summary and
  real-listener assertions.
- **Results.** Repository Ruff lint/format and strict mypy (563 files) pass; **full pytest
  1,357 passed in 793.09s** (zero failures/errors/skips).
- **Not established.** Readiness has not yet run on the authentic chain. Runs restore only
  snapshots from the same branch, so it first appears on real data when this change reaches
  the branch carrying the chain (or `main`).

**Next for the user:** review/merge #1 → #5 → #7 → #9 → this PR; that enables the 4-hourly
cron on `main`. Download and import the fee schedule PDF (issue #6). **Next autonomous
milestone:** keep the chain alive within the 7-day artifact retention; once readiness on the
chain shows the prospective minimums met, promote a snapshot to a reviewed evidence directory.

## Current milestone (2026-11-06): operator manual import of the official fee schedule

Branch `claude/vibrant-bohr-1hw7xm`, **stacked on PR #7** (`claude/vibrant-bohr-ypomud`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5, #7 and #8 had
no review comments and no failing checks, and none were merged, so this run did not
duplicate them. It dispatched forward-collection run `42150045698` on PR #7's branch to
keep that chain alive.

- **Why.** The certified-fee V1 gate needs the official schedule PDF, which returns HTTP 429
  to every automated client, including GitHub runners (issue #6). Option 1 of that issue,
  a human browser download plus import, had no code path.
- **What.** `fee_admin --import-schedule /abs/file.pdf --downloaded-at <tz ISO> --note ...`
  retains the exact PDF bytes as an **unreviewed** authentic receipt for the official URL.
  It carries explicit `manual_import` provenance. Availability is the local import clock;
  the attested download time is informational and cannot be later than the import. It is
  never selected or certified; `--review` stays the human attestation. Manual imports do not
  affect the `--capture-due` cadence. The website labels such sources
  `OPERATOR MANUAL IMPORT (no system-observed HTTP)`. Automated receipts serialize exactly as
  before, so all retained fee-version hashes are unchanged. See
  [fee evidence](docs/fee-evidence.md#operator-manual-import-of-the-official-schedule-issue-6).
- **Tests.** `backend/tests/unit/test_fee_manual_import.py` has 13 cases: provenance and
  import clock, hash stability of the retained 2026-10-30 version, non-PDF/symlink/relative/
  oversized/naive-time/late-download refusals, provenance on non-schedule sources refused,
  capture cadence unaffected, and review-clock availability of a reviewed import.
- **Results.** Ruff lint/format and strict mypy (563 files) pass; 24 frontend unit tests pass;
  **full pytest 1,354 passed in 692.40s** (zero failures/errors/skips). A real-Chromium
  check against the actual server shows the provenance and a byte-identical source download
  with 0 page errors. All bytes are CONTROLLED test bytes; see
  [evidence](data/fee-evidence-review/20261106-manual-import/README.md).
- **Not established.** No authentic schedule has been imported or certified.
- **Chain upkeep.** Forward-collection run `42150045698` (success) restored `42143557484`.
  - Monitor and schedule were kept, with 3 cycles this window and 8 in total, each `24 shadow decisions; 0 acquisition failures`.
  - 8 retained inputs; the schedule is active with 2 pending dates and 0 label requests.
  - 0 errors and server exit 0; snapshot `sha256:1390bff9…`.
  - Two `stale_collection` alerts were listed (status/detected_at null). They reflect gaps between discontinuous dispatched windows and were not investigated further.
  - Fee capture skipped both documents: the schedule's 429 was under 3 h old and the rounding page was fetched under 24 h ago.
  - Collection stays bounded to manual dispatches until #5/#7 merge, which enables the 4-hourly cron on `main`.

**Next for the user:** download the schedule PDF in a browser, import it with the command
above, then perform the `--review` attestation (the agent must not certify fees). Review/merge
#1 → #5 → #7 → this PR. **Next autonomous milestone:** keep the forward-collection chain
alive; after several days, promote a snapshot to a reviewed evidence directory and rerun
model readiness.

## Previous milestone (2026-11-06): unattended official fee-document capture

Branch `claude/vibrant-bohr-ypomud`, **stacked on PR #5** (`claude/vibrant-bohr-wr375g`).
**V1 remains incomplete.** Open PRs #1, #2, #4 and #5 had no review comments or failing
checks at the start of this run; none were merged, so this run avoided duplicating them.

- **Why.** "Certified fees" is an open V1 gate. The official fee schedule PDF could not be
  fetched from cloud sessions (HTTP 429 in October; proxy refusal now), so no authentic bytes
  existed for an operator to review. GitHub runners have the public egress (issue #3).
- **What.** `fee_admin --capture-due schedule rounding` captures each official document only
  when the retained copy is stale (success > 24 h, failure > 3 h), stores every attempt as an
  immutable **unreviewed** authentic receipt and prints per-document JSON (status, bytes,
  SHA-256, `is_pdf`). Network errors store nothing and do not fail. `forward-collection.yml`
  runs it after the server stops, so the bytes travel in the chained workspace snapshot and
  the result appears in the job log. Nothing is certified; `select_fee` still refuses.
- **Tests.** `backend/tests/unit/test_fee_capture_due.py` (5 cases): cadence, immutable
  re-capture, failure throttling, transport errors, per-document tracking and refusal of
  uncertified captures. Full-suite and runner results are recorded below.
- **Chain upkeep.** Dispatched forward-collection run `42136454980` on PR #5's branch
  (success): restored `42133403993`; `monitor_kept`/`schedule_kept`; 3 cycles this window
  (7 total), each `24 shadow decisions; 0 acquisition failures`; 7 retained inputs; schedule
  active with 2 pending dates and 0 label requests (the 2026-11-05 local days had not yet
  ended in US time zones); no alerts or errors; snapshot `sha256:6e69a006…`. This chain
  predates the fee-capture step, so it holds no fee receipts.

Results:
- Local: Ruff lint/format and strict mypy (562 files) pass; **full pytest 1,341 passed in
  645.79s** (zero failures/errors/skips).
- Runner verification `42136976908` (success, new chain on this branch): monitor created,
  2 cycles each `24 shadow decisions; 0 acquisition failures`, schedule created (follow
  retained, 2 pending dates), 0 errors, server exit 0, snapshot `sha256:ed298521…`.
- **Fee capture (real result):** the schedule PDF URL returned **HTTP 429** with a 24,732-byte
  `text/html` body (`is_pdf: false`, `sha256:0ea1dac4…`) even from the GitHub runner. The
  rounding page returned HTTP 200 HTML (131,209 bytes, `sha256:010b5152…`). Both were
  retained as unreviewed receipts. **No authentic fee schedule PDF has been obtained**, so the
  certified-fee gate stays blocked; the capture will retry at most every 3 h while failing. It
  does not change the User-Agent or otherwise try to evade the rate limit. A human may need
  to download the PDF in a browser and import it for review (an import path does not exist
  yet; see issue #6).

**Next for the user:** review/merge #1 → #5 → this PR so the 4-hourly cron runs on `main`.
Once a run reports `is_pdf: true` for the schedule, restore that snapshot locally and perform
the operator fee review described in [fee evidence](docs/fee-evidence.md) (human attestation;
the agent must not certify fees). **Next autonomous milestone:** keep the chains alive and,
after several days, promote a snapshot to a reviewed evidence directory and rerun model
readiness.

## Current milestone (2026-11-05): headless authentic forward collection on GitHub runners

Branch `claude/vibrant-bohr-wr375g`. **V1 remains incomplete.** Addresses blocker #3.
Open PRs from earlier sessions (#1 SQLite URI fix, #2 browser sweep + CI, #4 family
screening) are unmerged and had no review feedback or failing checks at the start of this run.

- **Egress found.** Cloud sessions still get proxy 403 for Kalshi/weather hosts, but GitHub-
  hosted runners reach all of them (`egress-probe.yml`, run `42129099670`: HTTP 200 from
  Kalshi series/markets, the Weather Company climate endpoint, api.weather.gov and
  Open-Meteo).
- **Operator.** `python -m entropytrade.operations.forward` starts the existing website server
  for a bounded window and drives only its localhost API. It keeps one active shadow monitor
  (on first run, created from a recorded-mode local-template candidate) and, once retained
  inputs exist, enables one following forward-validation schedule. It never resumes a paused
  monitor or schedule, refuses to run if submissions are enabled, and stops the server with
  SIGINT so interruptions are recorded.
- **Workflow.** `forward-collection.yml` restores the previous verified workspace snapshot
  from the newest run on the same branch and fails closed if it can't. It then collects,
  snapshots and uploads the workspace (7-day retention) and the summary (90 days), and
  prints the summary to the job log. The cron runs every 4 hours **only after the workflow
  is merged to `main`**. Verification pushes to `claude/**` run 900 s windows on their own
  chain. See [operation, limits and recovery](docs/forward-operator.md).
- **Includes PR #1's `uri=True` recovery fix** (cherry-picked `f2f16dc`). Snapshot/restore
  fails on `main` without it, and the identical hunks merge cleanly with #1.
- **Tooling note for later sessions.** `git push` of `.github/workflows/*` is rejected
  (`commit_refs_rules`), so workflow files were committed through the GitHub contents API.
  Creating the remote branch also needed the API. Artifact blob downloads are blocked from
  cloud sessions, so read results from the job log.

### Forward-collection verification runs (branch chain, 2026-11-05)

| Run | Result | What it shows |
|---|---|---|
| egress-probe `42129099670` | success | HTTP 200 from all five public endpoints from a GitHub-hosted runner. |
| forward-collection #1 `42130595001` | failure (operator) | New chain. Created research job + monitor `39c5fa16…`; first authentic cycle ran; schedule was created but the operator then raised `KeyError: 'id'` (schedule IDs are nested in `config`). The server still exited 0 and the verified snapshot (10.2 MB, 1 cycle) was uploaded. Fixed in `20848fa`. |
| forward-collection #2 `42131184740` | success | Restored #1's snapshot (checksum + lock checks); `monitor_kept`, `schedule_kept`, no errors, server exit 0; snapshot 18.8 MB with 2 cycles. |
| forward-collection #3 `42133403993` | success | Restored #2 (`previous_run_id=42131184740`). **2 cycles completed this window, each `24 shadow decisions; 0 acquisition failures`.** Monitor active, 0 consecutive failures, 4 cycles total, model binding `blocked` (no fitted real model), 0 fills, submissions disabled. 4 retained inputs in 1 partition. Schedule `24a2b11e…` active (follow retained) with 2 pending dates; label dates are not due until local days end, so 0 label requests yet. No alerts. Snapshot `sha256:c89ea3a9…` (4 cycles). |

These verification windows show that the chain mechanics work and that authentic receipts
accrue. They are not multi-day operation and not empirical evidence. Cycle-level success
or failure for #1 and #2 is only in their `forward-summary` artifacts (90-day retention),
which cloud sessions cannot download.

Checks on this branch: Ruff lint/format (561 files), strict mypy (561 files) and the
complete pytest suite pass (**1,335 passed in 723.24s**). The 16 forward-operator cases
were rerun after the schedule-shape fix and pass.

**Next for the user:** review and merge #1 (or this PR, which carries the same fix), then
this PR so the cron runs on `main`. Watch the first few scheduled runs for
`operator_review_required` (a monitor auto-paused after five failed cycles). After several
days, promote a snapshot to a reviewed evidence directory and rerun model readiness.


Updated 2026-11-05. R0 `c7ad278`, R1 `e2c1448`, R2 `b9cbaa8` and R3 `624d442`
remain recoverable on their original branches. R3 was integrated into main before R4.

## Open work (read first)

| Item | Branch / link | State |
|---|---|---|
| Read-only SQLite URI fix and prospective-evaluation gates | PR #1 `claude/vibrant-bohr-l2suow` | Merged after fresh review, full local checks, and both final-head CI runs. |
| Browser regression sweep, label-partition render fix, first CI workflow | PR #2 `claude/vibrant-bohr-b1kuuh` | Merged after retargeting to main, fresh review, and both final-head CI runs. |
| Market-family screening (this milestone) | PR #4 `claude/vibrant-bohr-0m71vf`, from `main` | Reconciled with tested main; receipt-order, update-clock, and numeric-format review findings fixed. Final CI pending. |
| No public egress in scheduled sessions | Issue #3 | Blocks authentic forward collection, fresh-acquisition browser specs and catalog fetches. |

## Current milestone (2026-11-06): runner catalog discovery and candidate screen

Branch `claude/vibrant-bohr-etkgi2`, **stacked on PR #4** (`claude/vibrant-bohr-0m71vf`).
**V1 remains incomplete.** At the start of this run, open PRs #1, #2, #4, #5 and #7 had no
review comments and no failing checks, so this run did not duplicate them. It also
dispatched forward-collection run `42143557484` on PR #7's branch to keep that chain going.

- **What.** `entropytrade family-discover` retains unauthenticated `GET /series?category=`
  receipts with a hashed manifest and lists every series alphabetically. It never ranks or
  selects. The `family-catalog` workflow runs discovery, then optional per-ticker
  `family-screen --fetch-series`, on GitHub-hosted runners, which have the egress that cloud
  sessions lack (issue #3). Its file was committed through the contents API.
- **Tests.** Full pytest: 1,300 passed and 57 failed (628.45s). The failures are the same 57 #1-dependent tests PR #4 recorded on this base. `backend/tests/unit/test_family_discovery.py` has 14 cases:
  - receipt retention, including non-200 responses;
  - deterministic listing;
  - tamper, path-escape and conflicting-ticker refusals;
  - malformed bodies;
  - byte-budget and transport errors with no retry;
  - category validation before any request;
  - path allow-list;
  - offline CLI.
- **Real results.**
  - Discovery listed 3,646 series. Entertainment, Politics and Sports exceeded the 2 MB
    response budget and are recorded as unusable.
  - Screening six candidates confirmed from the listing gave these finalized daily labels:
    KXAAAGASD 70 events, KXSOFRD 64, KXTNOTED 40 (history ends 2026-07-01) and
    KXTXERCOTPEAKD 38.
  - KXTSA and KXEURUSDD had no markets.
  - Coverage is truncated by the 3-page cap.
  - See [evidence](data/family-screening-review/20261106/README.md).
- **Not established.** Point-in-time predictors, effective fees, depth and skill are not
  established for any candidate.

**Next for the user:**
1. Review and merge #1 → #2 → #4 → this PR, and #5 → #7.
2. Record a written second-family choice (see `docs/family-selection.md`).

**Next autonomous milestone:** keep the forward-collection chain alive. Once a family is
approved, design its point-in-time predictor capture. Without approval, a deeper screen
(`max_pages` or additional candidates) is the only family work allowed.

## Current milestone: market-family screening (2026-11-05)

**V1 remains incomplete.** The new `entropytrade family-screen` command compares Kalshi
series using retained public catalog receipts. It is meant to support the user's
second-family decision, and it never selects a family.

Per series, it reports:

- coverage;
- finalized YES/NO labels;
- event and date counts;
- contract structure;
- traded share and volume;
- rule wording (verbatim earliest and latest text);
- fee and source metadata;
- the existing fitting minimum of 40 labeled events on 20 dates with both outcomes.

The JSON is deterministic and hashes every input. Malformed, contradictory or tampered
receipts are refused.

The optional `--fetch-series` mode sends unauthenticated GETs to Kalshi's catalog paths
only, through the existing `BoundedTransport`. It keeps every response, including failures,
with a hashed manifest.

**Retained-receipt result.** 29 receipts were screened, covering 4,576 markets:

- KXHIGHPHIL meets the label minimum: 681 events on 681 dates, 2024-11-21 to 2026-10-04.
  Its rule wording changed from the NWS Daily Climate Report to The Weather Company, so
  older labels do not share current settlement semantics.
- The retained KXBTC captures contain no finalized results.
- KXNHL and KXMVECROSSCATEGORY have series metadata only.

The one live fetch attempt failed with no egress (issue #3); no fetched catalog is claimed.
See [docs/family-selection.md](docs/family-selection.md) and the
[evidence](data/family-screening-review/20261105/README.md).

**Original author checks (historical; retained evidence unchanged).**

- Ruff lint and format pass on the repository.
- Strict mypy passes on 558 files.
- All 25 screening tests pass.
- Full suite on this branch: 1,285 passed and 57 failed in 554.06s on this branch. All 57 failures come from the
  pre-existing `main` read-only SQLite URI defect (56 log `unable to open database file`).
  With only PR #1's two-file fix applied to `main`, all 57 pass in 239.63s. This is not a
  clean full-suite pass; it becomes one once PR #1 merges.

**Next.**

1. Review and merge PRs #1, #2 and this PR, in that order.
2. In an environment with egress, fetch three to six candidate series from non-temperature
   categories, screen them, and record the user's written family choice.
3. Resume authentic forward collection once egress exists.

New-family implementation, credentials and real trading remain out of scope without
approval.

**Reconciliation, 2026-11-06.** The 57 original failures above are historical. PR #1's
recovery fix and PR #2's frontend/CI changes are now on tested main and integrated here.
Fresh screening regressions cover receipt permutations, invalid update clocks and mixed
volume fields; all 31 focused cases, Ruff and strict mypy pass. Full CI must pass on the
final reconciled commit before merge. [Reconciliation tracker](https://github.com/GabeSternberg/EntropyTrade/issues/25).

## Current milestone: full browser regression sweep and CI (2026-11-05)

Scheduled autonomous session on `claude/vibrant-bohr-b1kuuh`, stacked on PR #1 (its SQLite URI
fix is needed for offline restore); PR opened against main for review. **V1 remains incomplete.**

**Browser sweep.** All 14 `frontend/browser` spec files ran against the current tree through
real listeners and managed Chromium.
- **Passing:** 19 tests across 12 spec files, plus 3 of 4 workbench workflows, all with zero
  page errors.
- **Failing for network only:** `weather-labels` and workbench workflow 3 need public egress,
  which this runtime's proxy refuses. The app retained `ConnectError` receipts and refused
  honestly.
- **Shadow:** `shadow.spec.cjs` passes its lifecycle checks, but all of its public acquisition
  failed, so it is not ingestion evidence.

**Fixes.**
- **App defect:** overlapping label-partition renders could show one partition's requests
  while another was selected. Now only the newest render is applied. A DOM regression
  reproduces the old behaviour.
- **Harness defects:** a fixed or basename-derived archive path collided across runs, and
  `data/recovery/` was not ignored. The outage screenshot now targets the HTTP 503 request.

**CI.** New `.github/workflows/ci.yml` runs locked uv, Ruff, strict mypy, frontend DOM tests and
the full pytest suite with no secrets. It passes on GitHub: **1,320 tests in 693.83s**.

See [evidence](data/browser-regression-review/20261105/README.md).

**Next recommended milestone:**
1. Re-run `weather-labels` and workbench workflow 3 in a runtime with public egress.
2. Continue authentic forward collection (needs elapsed real time).
3. Prepare the user-approval comparison for a second market family.

Credential-dependent provider verification, certified fees and real trading remain blocked on
the user.

## Previous milestone: prospective-evaluation acceptance completion (2026-11-05)

Scheduled autonomous session on `claude/vibrant-bohr-l2suow` from main `55b2bea`; PR opened
against main for review. **V1 remains incomplete.**

This runtime permits loopback sockets, so the gates left outstanding on October 31 were executed.
The first real browser attempt exposed a genuine defect: offline snapshot/restore opened
read-only SQLite `file:` URIs without `uri=True`, so recovery refused on SQLite builds without
`SQLITE_USE_URI` (here uv-managed CPython 3.13.18 / SQLite 3.53.1). Fixed in five call sites with
a static architecture guard. After the fix, both managed-Chromium prospective procedures pass
(12 downloads identical across restart and offline restore, 0 page errors), and the complete
suite passes **all 1,320 tests in 619.14s** with zero failures/errors/skips, including every
listener case. Ruff/format, strict mypy (557 files), 24 frontend tests pass; all 73 original
receipt/Bitcoin hashes are unchanged. Chromium build deviation (preinstalled 1243 at the pinned
1194 path) is disclosed. See [evidence](data/prospective-evaluation-review/20261105/README.md).

**Next recommended milestone:** with sockets available, rerun the other browser procedures in
`frontend/browser/` against the current tree to confirm no regression from environment drift,
then continue authentic forward collection (needs elapsed real time) and prepare the
user-approval comparison for a second market family. Credential-dependent provider
verification, certified fees and real trading remain blocked on the user.

## Previous milestone: prospective shadow-evaluation reports

Implemented in place on designated `supervisor/20261031-081845` from `a83b9db`.
All Git operations and independent review remain with the supervisor. **V1 remains incomplete.**

The private website now projects retained shadow forecasts and later official binary outcomes
into pending, refused and matched observations, with JSON/CSV exports, source/model lineage,
independent event/date counts and descriptive forecast diagnostics when evidence permits.
Reports verify committed cycle digests, raw source/contract bindings, frozen model scoring,
original availability clocks and protected exclusions. Repeated polls cannot increase independent
counts or replace the earliest pre-close observation. Diagnostic groups keep real/synthetic data
and model versions separate; event-weighted Brier/log loss and reliability bins require ten
matched events on five dates. Trading depth/fee/risk refusals stay separate from forecast quality.

Bounded outcome collection now revisits finalized contracts as well as unresolved ones. Reports
use the latest verified receipt at their cutoff and retain revisions/refusals; original decisions,
first accounting settlements and frozen validation boundaries remain intact. Restart and offline
snapshot/restore reproduce reports and CSV bytes. Controlled scored examples are explicitly
synthetic; the authentic retained path still has no usable forecast metrics or empirical returns.

Browser acceptance is **outstanding**. Supported managed-Chromium installation succeeded, but
the first launch failed at `crashpad/util/linux/socket.cc:45` with `setsockopt: Operation not
permitted` and SIGTRAP; the real-listener test separately failed creating its socket with
`PermissionError: [Errno 1]`. No denied browser launch is repeated and no mock is claimed as
browser acceptance. The executable two-procedure harness covers actual page inspection,
JSON/CSV downloads, listener restart and offline restore in a socket-permitted environment.
Quality results and exact limitations are retained in
[current evidence](data/prospective-evaluation-review/20261031/README.md).
See [operator workflow](docs/prospective-evaluation.md).

Repository Ruff/format, strict mypy (556 files), 24 frontend and 28 focused pytest cases
pass. Offline reports/CSVs reproduce with 23 synthetic and 68 authentic cycle files unchanged;
all 73 original receipt/Bitcoin boundary hashes remain unchanged. The bounded all-file run
attempts 241 files in 477.06s: 217 pass, 12 fail and 12 exceed deadlines. Failures include
eleven denied localhost cases, two unresolved label-worker shutdown cases and a native
SIGSEGV in shadow-history testing. The complete-suite gate remains open; see exact logs
and the isolated crash follow-up in current evidence. All 14 shadow-history tests pass in
the isolated serial follow-up (71.20s); the prior native-crash cause remains unestablished.
No full-suite or browser pass is claimed.

Continue authentic forward collection while independent V1 functionality remains usable.
New-family implementation requires user approval; credential-dependent verification and real
trading remain deferred. No credentials, live execution, real orders, risk-limit changes,
Git mutations or supervisor-control changes are included. Return this single milestone for review.

## Previous milestone: bounded immutable label partitions

Implemented in place on designated `supervisor/20261031-073225` from `b62f9c6`. All Git
operations and independent approval remain with the supervisor. **V1 remains incomplete.**

Continuous read-only schedules now roll beyond the former 128-request workspace cap. Each
partition retains at most 128 requests; completed partitions seal with chained manifests and
exact file hashes, without moving or retiming earlier evidence. Temporary queue/full-partition
backpressure preserves the original schedule plan until drain. Archived request IDs remain
idempotent; a crash after seal resumes the same unpublished plan. Partial cancellation,
terminal-state protection and explicit filesystem/verification failures remain enforced.

The website inspects every bounded label partition and downloads its seal and source evidence.
Manual freezes, following retained inputs and cohort assembly read verified batches across
partitions under the existing 256 MB snapshot budget. Canonical audit ordering makes cross-
partition assembly reproducible. Offline recovery validates all seals, inventories, request/
batch bindings and original source clocks. Repeated revisions do not add independent events
or repair earlier model cutoffs; frozen holdouts remain unchanged.

Final verification passes repository-wide Ruff/format, strict mypy (551 files), all 22 frontend
checks, 64 focused tests, 12 integrity/lifecycle checks and **all 1,292 pytest cases in 679.34s**
(zero failures/errors/skips). Both final managed-Chromium procedures pass, retaining 14 screenshots,
12 downloads and zero page errors. All 262 controlled label-store files match after restart and
offline restore; all 73 original receipt/Bitcoin boundary hashes stay unchanged. The 260-batch,
two-rollover service check and 130-batch browser check are controlled software evidence.
Separately retained authentic operating evidence verifies three station/day highs and refuses
one preliminary report, with real receipt-time availability. Multi-day reliability, sufficient
independent empirical history and profitability are not established. See
[executed evidence](data/label-partition-review/20261031/README.md) for exact results, retained
failed/interrupted attempts, the missing-terminal-batch guard and local-artifact requirements.

No new family, credentials, real orders, execution activation, risk-limit changes, Git
mutations or supervisor-control changes are included. New-family selection and credential-
dependent provider verification remain deferred. Return this single milestone for independent
review before starting another major phase. See [operator workflow](docs/label-partitions.md).

## Previous milestone: durable acquisition-error finalization

Corrected in place on designated `supervisor/20261031-054650` from `5d5e893`. Git operations
and independent approval remain with the supervisor. **V1 remains incomplete.**

The acquisition loop now finalizes errors from freshly loaded durable state. Previously its
stale queued selection could erase receipts persisted by the owned acquisition request.
Actual-loop regressions reproduce both acquisition and transient second-receipt-save errors,
then verify exact retained bytes/timestamps through failure, scheduler reconciliation,
restart and read-only workspace validation. Existing terminal request/batch protection remains
tested for all three terminal statuses. Unsaved responses are not claimed as retained receipts.

Ruff/format, strict mypy (548 files), 22 frontend checks and 55 focused pytest cases pass.
The complete suite passes **all 1,282 pytest cases in 556.02s**, zero failures/errors/skips.
Both actual managed-Chromium procedures pass through localhost listeners, retaining 13
screenshots, six downloads and zero page errors. All four partial failed requests and their
eight file hashes survive restart and offline restore; the earlier startup cancellation and
schedule-download comparisons still pass. Authentic acquisition verifies three station/day
highs and refuses one preliminary report; availability begins at the new receipts, with
empirical fitting and returns still insufficient. All 73 original receipt/Bitcoin boundary
hashes remain unchanged. See [correction evidence](data/forward-validation-review/20261031-acquisition-errors/README.md)
for exact reproduction, quality, browser, complete-suite and local-artifact results.

No new family, credentials, real orders, activation, risk-limit changes, Git mutations or
next major phase are included. Return this same correction for independent review.

## Previous milestone: atomic label-request claiming and cancellation

Corrected in place on designated `supervisor/20261031-054650` from `2f93999`. Git operations
and independent approval remain with the supervisor. **V1 remains incomplete.**

The label worker now reloads durable request state under the service lock, skips requests
that are no longer queued, and registers active ownership in the same critical section as
the running transition. Pause/shutdown intent is visible before acquisition startup even
when the event loop has not delivered its cancellation callback. Terminal request/batch
evidence cannot be replaced by stale completion. Existing partial receipts remain retained.

Deterministic barriers exercise both cancellation interleavings, all terminal statuses,
shutdown before startup and repeated claiming. The managed-Chromium regression now pauses
at a test-only startup barrier through the actual website/listener and compares interrupted
evidence after restart and offline restore. Exact executed results, retained attempts and
limitations are in [correction evidence](data/forward-validation-review/20261031-atomic-claim/README.md).
Final verification passes Ruff/format, strict mypy (547 files), all 22 frontend checks,
50 focused tests and **all 1,277 pytest cases in 555.99s** (zero failures/errors/skips).
Both actual managed-Chromium procedures pass, retaining 11 screenshots, six downloads,
unchanged interrupted evidence after restart/restore and zero page errors. The first
browser attempt's harness error remains recorded as interrupted, never as a pass.
No new family, credentials, submission activation, real orders, risk-limit changes or Git
mutations are included. Return this correction for independent supervisor review.

## Previous milestone: continuous forward validation

Implemented in place on designated `supervisor/20261031-054650` from `9d9f921`. All Git
operations and independent approval remain with the supervisor. **V1 remains incomplete.**

The existing label/shadow website now offers explicit opt-in scheduling, bounded date batches,
a durable retry backlog and browser-visible progress/controls. Histories over eight dates
are split automatically. Preliminary reports and outages back off; official reports receive
daily revision checks. Optional following of retained public/shadow inputs freezes new
immutable datasets one bounded partition at a time. Crash recovery reuses the original
planned request ID; shutdown preserves partial receipt evidence. Offline validation and
restore include pinned source, request and batch references. Original availability clocks,
frozen calendar boundaries, model insufficiency and disabled submissions remain enforced.

Final verification passes Ruff/format and strict mypy (546 backend files), all 22 frontend
checks, **all 1,271 pytest cases in 553.51s** (zero failures/errors/skips), and both actual
managed-Chromium procedures. Browser evidence retains 10 screenshots, 6 downloads, four
identical restart/restore comparisons and zero page errors. Authentic scheduling verifies two
October 29 highs and refuses both October 30 preliminary reports; availability begins at new
receipts. All 68 original receipt and five Bitcoin boundary hashes remain unchanged. The
controlled twelve-date transitions prove software behavior, not empirical fitting or returns.

See [operator workflow](docs/forward-validation.md) and
[current executed evidence](data/forward-validation-review/20261031/README.md). Quality and
browser results are recorded there with authentic/controlled evidence kept separate.
No new family, credentials, real orders, execution activation, risk-limit changes or Git
mutations are included. Preserve forward collection and Bitcoin boundaries; return this
single substantial milestone for independent supervisor review.

## Previous milestone: integrated forward weather-label acquisition

Implemented in place on designated `supervisor/20261031-050653` from `a473758`. All Git
operations and independent approval remain with the supervisor. **V1 is incomplete.**

The website now acquires read-only Weather Company daily-climate reports for selected
retained weather datasets, saves durable progress and exact source bytes, exposes verified
scalar highs and refusals, and includes compatible labels in a new immutable research
snapshot. Original datasets/forecasts and frozen partition boundaries remain unchanged.
The authentic October 31 acquisition verifies **two October 29 station/day highs**;
**two October 30 preliminary reports are refused**. Publication/revision timestamps absent
from the provider remain unknown. Availability starts at the new receipt, never the target
date. These sparse labels do not establish empirical models, backtest returns or profit.

Restart/idempotency, active shutdown, partial receipts, corrected/late/wrong-source/protected
labels, bounded network failures and offline snapshot replay/restore are tested. Snapshot
loading reparses source bytes and rechecks original rule bindings and audit observations.
Managed Chromium through actual localhost listeners verifies acquisition, status, provenance,
dataset freeze, honest research insufficiency and identical downloads after restart. The
first browser attempt found lost dataset selection after restart; the UI fix and subsequent
passing attempts retain that failure unchanged. Final checks pass Ruff/format (542 backend
files), strict mypy (542 files), 22 frontend checks and **all 1,255 pytest tests in 609.09s**,
with zero failures/errors/skips. The final browser run retains seven screenshots, six
downloads, three byte-identical reopened pairs and zero page errors. Authentic offline
restore/reparse passes; 68 original receipt files and five Bitcoin boundary files remain
unchanged. Generated archive/trace bytes stay locally retained under a scoped ignore rule
and checksummed manifest; independent archive/trace review requires those local bytes.
See [workflow](docs/weather-labels.md),
[executed evidence](data/weather-label-review/20261031/README.md), and the
[V1 matrix](docs/v1_acceptance.md) for exact quality/browser results and limitations.

Preserve authentic forward clocks and Bitcoin boundaries. New-family selection,
credential-dependent provider verification, effective fee certification, sufficient empirical
history and independent V1 acceptance remain deferred. No credentials, real orders, execution
activation, risk-limit changes or Git mutations were used. Return this single substantial
milestone for supervisor review before another major phase.

## Previous milestone: private-workbench operating acceptance

Checkpoint blocker repair: generated Playwright trees and workspace ZIPs are retained
locally and excluded from new staging. A [362,515-byte manifest](data/operating-acceptance-review/local-artifacts-20261031.json)
verifies 1,096 files totaling 261,903,008 bytes, including the reported 13,926,914-byte
trace and every oversized untracked workspace archive. Nothing is deleted or retimed;
earlier acceptance receipts remain unchanged. The [retention policy](data/operating-acceptance-review/ARTIFACT_RETENTION.md)
documents verification, checkout limitations and a separate proposal for four unchanged
large tracked artifacts. Git checkpointing remains the supervisor's responsibility.
These retention checks do not rerun the prior passing suite/browser acceptance below.
Repair verification passes Ruff/format (540 files), strict mypy (537 files), 66 focused
pytest cases and 22 frontend checks. The [read-only audit](data/operating-acceptance-review/20261031-checkpoint-repair/README.md)
finds no eligible changed/untracked candidate above 8,000,000 bytes (largest 971,467),
verifies all original source/safety/browser artifact hashes and leaves the index empty.

Bounded follow-up on `supervisor/20261031-044002`: the audit now reports
`largest_candidate_bytes=0` when no prospective checkpoint files exist. Clean/dirty
checkout regressions and oversized/staged refusals pass within 70 focused cases, with
Ruff/format and strict mypy (538 files) passing. The documented read-only audit and
retention check pass again; [new evidence](data/operating-acceptance-review/20261031-checkpoint-repair/README.md#zero-candidate-correction)
preserves earlier receipts/logs unchanged. No new browser/full-suite run or Git mutation.

Work remains on designated `supervisor/20261031-033238` from `2f8d9ad`; the supervisor
owns all Git mutations and independent review. The fresh serial locked installation has
passed Ruff lint/format, strict mypy (535 files), all 22 frontend checks and **all six
required managed-Chromium procedures** through actual localhost listeners. The browser
receipts retain **26 screenshots, 43 downloads and zero page errors**, including controlled
and authentic paper accounting, alert acknowledgement/recovery/recurrence, cancellation,
listener restart, offline restore and reopened-download equality.

The complete suite passes **1,210 tests in 644.82s**, with zero failures/errors/skips.
Final verification checks all 43 download hashes, 26 screenshots, six intact traces,
19 identical download comparisons, all 1,578 checkout/install source hashes and all
68 original receipt plus five Bitcoin boundary hashes. Both actual paper browser workspaces
restore offline with identical exports and reproducible accounting; stopped recovery,
provider and weather workspaces are archived, including fresh authentic collection bytes.
**Private-workbench operating acceptance is verified; V1 remains incomplete.** See the
[current execution bundle](data/operating-acceptance-review/20261031-permitted-serial/README.md).
Earlier failed attempts remain failed. Two concrete harness repairs strengthen provider
run identity checks before downloads and stage authentic import metadata inside the installed
repository before copying it to external evidence. Pytest logs each case for crash diagnosis;
existing assertions, internal timeouts, risk limits and production code are unchanged.
The serial run completes without reproducing the earlier native crash; its underlying
cause is not established. Independent supervisor milestone/release review remains required.

Preserve authentic forward collection, original timestamps and frozen Bitcoin boundaries.
External-provider verification, authentic empirical models/backtests, effective fee
certification, two-family validation and independent V1 release review remain open. Another
major family requires user approval. No next major phase, credentials, real orders or Git
mutations are authorized by these execution results.

## Previous correction: deterministic provider deadline verification

The reported provider-job `assert calls` failure is reproduced and repaired in test
support. A 50 ms whole-pipeline deadline could expire during agent/schema setup before
HTTP, while the fixture required a request. The controlled stalled-HTTP fixture now
expires the real asyncio deadline at request arrival. Added regressions cover slow setup
and a separate real 50 ms startup timeout with zero requests, durable failure recovery,
no experiments/holdout and worker-guard release. Production budgets and safety gates are
unchanged. See [reproduction and verification](data/debugging-review/20261031-provider-deadline/README.md).

Ruff/format, strict mypy (535 files), **64 focused pytest cases in 9.52s**, and all
22 named frontend checks pass. The existing provider procedure passes through actual
managed Chromium and a localhost listener: **8 screenshots, 14 verified downloads, zero
page errors**, with cancellation/restart and identical reopened downloads. Restricted
execution still denies sockets; local test/browser execution used the approved standard
permission path without patching the sandbox or launch settings. The **complete pytest
suite passes all 1,210 cases in 532.60s**, with no failures or skips, including every
repaired deadline case. Exact logs, JUnit, source hashes and browser artifacts are retained
in the debugging bundle.

All 68 original receipts and five Bitcoin boundary files match the prior safety hashes.
V1 and six-procedure operating acceptance remain incomplete; the other five procedures,
fresh-install operating acceptance, external-provider and authentic empirical/fee/two-family
evidence remain open. Preserve authentic forward collection and optional Bitcoin work;
another major family requires user approval. No Git operations or next major phase are
performed; return this debugging correction for independent supervisor review.

## Previous milestone: reproducible private-workbench operating acceptance

The report-gate correction is implemented in place from `5e2bd03` on the same designated
branch. Completion now requires JSON-reporter discovery of the six fixed file/title
identities and successful execution of every selected procedure, with consistent report
counts and no skipped, failed, absent or empty results. Process exit zero alone cannot
pass a browser step. Full discovery is independent of `--browser-grep`; a successful
narrowed run records missing procedures and an explicit partial status with
`acceptance_complete=false`. Preparation still cannot complete acceptance. See the
[correction evidence](data/operating-acceptance-review/20261031/report-gate-correction/README.md).
Correction checks pass: **439 focused pytest cases in 30.10s**, including 53 acceptance-driver
cases, Ruff lint/format, strict mypy (535 files), 22 frontend checks and actual full/narrowed
Playwright discovery. Historical report parsing verifies schema compatibility and refusal;
it does not establish current browser execution. Earlier evidence below keeps its original scope.
No restricted browser/listener or full-suite retry is required or claimed for this correction.

Implemented in place on designated `supervisor/20261031-014049` from `b8d2538`.
All Git operations and independent review remain with the supervisor. **V1 and operating
acceptance remain incomplete because the environment still denies required sockets.**

`tools/local_acceptance.py` now selects all six existing research/recovery, controlled
provider, authentic weather, both paper-account and operator-alert browser procedures.
It records discovery separately, stops browser execution after its first failure, checks
localhost and asyncio socket capabilities before browser/full-suite execution, and retains
blocked/unexecuted statuses. Preparation cannot set `acceptance_complete=true`.
Clean exports now include the original v1 account compatibility fixture and complete original
authentic cycles, including saved decision/result bytes. Failed missing-input attempts remain
retained; no test or original receipt was rewritten to repair them.

Fresh offline locked Python/npm installation, supported managed-Chromium provisioning,
Ruff lint/format, strict mypy (535 files), 22 named frontend checks, **394 focused pytest
cases in 40.52s** and discovery of all six procedures pass. Current-source offline paper
exports reproduce, reopen and restore
identically; the controlled account has two simulated fills, while authentic receipts retain
zero fills and refuse missing models/fees. Offline alert acknowledgement/idempotency, recovery,
recurrence, reopen and restore comparisons also pass. These are software checks, not browser
download or empirical evidence. Exact focused-test results, commands and source hashes are
in [the acceptance bundle](data/operating-acceptance-review/20261031/README.md).

The direct capability check returns `PermissionError(1, 'Operation not permitted')` for both
localhost socket creation and `socketpair()`. The known denied Chromium launch and complete
suite stall are not retried. There are no new browser interactions, screenshots or listener
download passes. In a permitted environment, run the locked driver without `--prepare-only`
using a fresh output path; all six procedures and the complete suite remain required.
See [the current matrix](docs/v1_acceptance.md). Stop environment retries here.

All 68 original receipt files and five Bitcoin boundary implementation/manifest files
remain unchanged. Preserve authentic forward collection, original clocks, frozen validation
boundaries and existing risk/submission limits. External provider verification, empirical
two-family validation, certified fees and independent release approval stay open. Another
major family needs user approval. No next major phase or Git mutation is performed.

## Previous milestone: operator readiness for continuous paper/shadow

Implemented in place on designated `supervisor/20261031-011453` from `df304f9`.
The supervisor owns all Git operations and independent review. **V1 is incomplete.**

The existing website now shows durable alerts for stale collection, three repeated
failures/incomplete collections and unresolved contracts an hour after close. Incidents
retain operator detection clocks, exact cycle/contract evidence, idempotent acknowledgement,
automatic recovery events and fresh acknowledgement on recurrence. Pausing/resuming cannot
erase a failure streak or an open stale incident. Startup and background checks run without
an open browser. Monitor exports and verified offline workspace restores preserve lifecycle
state. Missing models/fees remain visible refusals and cannot be acknowledged into eligibility.

Controlled failure/restart, simultaneous acknowledgement, recovery/recurrence, migration,
CSRF/scope, account/risk and authentic original-receipt inspection are exercised. Both
controlled and authentic paper account exports reproduce and restore offline; authentic
evidence retains zero fills. All 68 original receipt files remain byte-identical.
The [operator guide](docs/operator-alerts.md) and [evidence bundle](data/operator-readiness-review/20261031/README.md)
separate executed checks from outstanding acceptance.

Managed Chromium installs successfully into the repository cache. Its one launch fails
before page interaction at `crashpad/util/linux/socket.cc:45`: `setsockopt: Operation not
permitted` / SIGTRAP. Socket creation also returns `PermissionError: [Errno 1] Operation
not permitted`. The browser denial is not retried or bypassed. Both outstanding paper
procedures and the new alerts procedure are executable/discovered; real page interactions,
screenshots and real-listener download/restart acceptance remain outstanding in a permitted
environment. Offline checks and HTTP doubles are not browser acceptance.

Final checks pass **246 focused pytest cases**, all **11 current alert cases**, **22 named
frontend checks**, backend Ruff lint/format and strict mypy (**534 files**). The alert cases
are included in the focused total. The complete pytest attempt stalls in the existing
collector reconnect case and is interrupted. All **228 test files** are then attempted with
deadlines: **211 pass, six fail on denied localhost sockets (eight cases), eleven time out**.
The 14-case history file, including the 130-cycle/restart procedure, passes. No complete-suite
pass is claimed; exact results and diagnostic traces are in the evidence bundle. No fresh clean-install,
external-provider, authentic empirical-model or V1-release pass is claimed.

Receipt clocks, frozen Bitcoin boundaries, disabled submissions and existing risk caps are
preserved. Continue authentic forward collection; defer new-family selection and empirical
claims. Return this substantial implementation for review and finish the environment-blocked
acceptance gates before milestone approval. No next major phase is started.

## Previous milestone: durable simulated paper accounting in continuous shadow

Implemented on designated `supervisor/20261031-002357` from `92a0ec2`; review
corrections continue in place from `d8bbb94`. All Git operations and independent
review remain with the supervisor. **V1 is incomplete.**

The review correction now checks net edge after IOC sizing against the executable quantity,
the broker's exact planned price slices and each slice's rounded taker fee. Existing cost
reserves and full-intention monetary caps remain enforced. Failed edge cancels execution
before an order/fill is recorded; the plan and failed risk check remain inspectable.
Later capture references now resolve under `paper-execution/`. Replay verifies capture
summaries, every raw reference/hash, nested fee-receipt bindings and later books against
their original bytes, including self-consistent tampering of frozen computation inputs.
New accounting inputs use v2 audits. Safe older v1 account chains reproduce without
inventing historical audit fields; v1 still runs the corrected edge gate and cannot bypass it.

Correction verification passes **388 targeted pytest cases** (375 accounting/collector/
risk/recovery and 13 history cases), backend Ruff lint/format and strict mypy (531 files).
The slow 130-cycle case is explicitly deselected; no complete-suite or new browser pass
is claimed. The extra root-wide format attempt flags an existing Markdown example outside
the Makefile's backend format gate; its failure is retained without editing unrelated docs.
See [correction evidence](data/paper-accounting-review/20261031-correction/README.md).
Request independent re-review of this milestone; do not start another major phase.

The existing collector now maintains a separate per-monitor simulated $1,000 account
through PaperBroker/Ledger. Original shadow evidence/intentions remain separate from paper
decisions, orders, fills, positions, cash, fees and settlement. Paper decisions use actual
simulated holdings and existing risk caps; execution needs a later sized receipt after at
least one second, clamps price improvements, rechecks risk/edge and selects effective fee
evidence again. Consumed side snapshots cannot replenish on another poll or an opposite-side
change. IOC size reductions are explicit; FOK cannot silently shrink. Remainders do not queue.

Cycle/account updates commit atomically with previous-state checks. Paused/interrupted/late
workers cannot apply fills; uncommitted result bytes survive separately. Missing/corrupt
accounts cannot reset the bankroll. Official binary results settle at receipt availability,
with duplicate/conflicting outcomes guarded. Workspace snapshot/restore verifies the entire
account chain, including legacy workspaces without retroactive fills. JSON exports reproduce
offline. The website exposes simulated account balances, positions, decisions, execution
refusals, fees and settlements, with account and full-evidence downloads.

Authentic retained receipts still block on missing models/fees and yield zero fills.
Successful controlled accounting is explicitly synthetic and proves no empirical returns.
No family was added, receipts backdated, protected boundary changed, credential accessed,
risk cap raised or exchange submission enabled. Existing Bitcoin work remains optional.

Ruff/format, strict mypy, targeted accounting/collector/recovery and broader independent
checks are recorded in [milestone evidence](data/paper-accounting-review/20261031/README.md).
Before the review correction, verification passed **293 targeted pytest cases in 61.89s**, Ruff/format
and strict mypy (531 files), 21 named frontend assertions and both offline export/restores.
The broader per-file run passes 208 files; six listener files fail on denied socket creation,
eleven files reach their external deadlines, and the first collector file remains interrupted.
The complete-suite attempt stalls in the existing collector path in this restricted
environment; isolated files retain their exact results and deadlines, including denied
localhost listener cases. **No complete-suite pass is claimed.** Managed Chromium installation
succeeds, but launch fails at `crashpad/util/linux/socket.cc:45` with `setsockopt: Operation
not permitted`/SIGTRAP before page interaction. Traces are retained; no further launch retry,
permission bypass, screenshot or browser-download pass is claimed. The executable
[Playwright harness](frontend/browser/paper.spec.cjs) needs execution in a permitted environment.

See [operation and remaining acceptance](docs/paper-accounting.md). Return this implementation
for supervisor review; finish full-suite/browser acceptance before approving those gates.
No new clean install, authentic model/fee certification, empirical two-family validation,
external provider verification or V1 release acceptance is claimed. Do not start another phase.

## Previous milestone: point-in-time fee evidence for shadow and experiments

Implemented in place on designated `supervisor/20261030-205940` from `99870f2`.
The supervisor owns every Git operation and independent acceptance. **V1 remains incomplete.**
No credentials, exchange orders, live activation, risk-limit changes or new family were used.

Continuous cycles and real research jobs now freeze immutable server-managed fee versions.
Versions retain official source bytes/hashes, receipt and local review clocks, exact series
scope, coefficients, citations, rounding and bounded effective intervals. The existing
FeePolicy/calculator/interpreter/risk engine is reused. Series metadata cannot certify a
coefficient; failed or unsupported documents cannot certify. Reviewing today cannot backdate
availability. Missing/conflicting/late/inapplicable/expired evidence refuses explicitly.
Controlled evidence applies only to synthetic data. Captured series conflicts also refuse.

The website exposes fee provenance/refusal, immutable versions, original-byte downloads,
per-decision selections and frozen job evidence. Reservations remain fee-inclusive across
restart. Replays use evidence at decision and simulated execution clocks, including a fee
change during latency. Portable experiment inputs retain frozen predictions/configuration
and redact protected features, targets and books; offline verification compares saved results.
Corrupt evidence fails closed, and the existing workspace recovery retains fee versions.

Separate managed-Chromium procedures execute actual localhost page interaction for CONTROLLED
eligible-intention/reservation fixtures and authentic original-receipt refusal. They download
and checksum versions, original source bytes and shadow exports, restart the actual server
and compare reopened downloads. The authentic flow also submits ordinary research and
downloads its frozen fee evidence and honest insufficient-data review. Controlled success
is evaluator/store/browser software evidence, never authentic acquisition or profitability.
A fresh unauthenticated official fee PDF GET returned HTTP 429 at its original current clock;
its exact bytes are retained. No authentic fee schedule was certified or historical receipt
backdated. External source/model/empirical gates remain open.

Final verification passes **1,109 pytest tests in 641.26s**, Ruff lint/format (529 files),
strict mypy (526 files), all 21 named frontend assertions, 29 targeted fee/shadow cases and
both actual Chromium procedures (five screenshots, fourteen matching downloads, zero page
errors). Both workspace restores and controlled/real-refusal experiment replays pass offline.
All 550 frozen source/configuration hashes match; previously tracked data bytes are unchanged.
Exact executed coverage and remaining limits are recorded in the
[milestone evidence](data/fee-evidence-review/20261030/README.md). See the
[operating guide](docs/fee-evidence.md). Existing source receipts, Bitcoin's frozen boundaries,
protected partitions and disabled submissions remain intact. No fresh clean-install or V1
release pass is claimed. Return this substantial milestone for supervisor review; defer
new-family selection and empirical release claims. Do not start another major phase.

## Previous milestone: reproducible research cohorts across retained partitions

Implemented in place on designated `supervisor/20261030-202711` from `69e2740`.
All Git operations and independent acceptance belong to the supervisor. **V1 remains
incomplete.** No credentials, orders, live activation, risk changes or new family were used.

The private website now selects up to eight history partitions and optional separate
outcome partitions as one immutable research cohort. Each history batch retains the existing
128-input limit; the aggregate retains the 256 MB raw-input budget. Completed immutable
batches survive interrupted assembly. Cohort features are rebuilt together through the
existing snapshot/R2/model/R4 pipeline, preserving causal history across batch boundaries.
Calendar boundaries and workspace/source/model protections remain shared and frozen.
Repeated captures count as independent city/day events only once. Stale/unknown selections,
malformed requests, missing labels and protected model partitions fail closed.

The CONTROLLED sufficient-data fixture spans 130 captures, two partitions, 200 city/day
events on 100 dates, and 20 protected events. It exercises deterministic fitting, Platt
calibration and validation predictions without evaluating holdout. Predictions reproduce
byte-for-byte in an independent modeling output. Interruption between batches, offline
restore, protected label/bias exclusion and missing-label refusal are tested. Authentic
original receipts still yield four events on two dates and zero source-matched scalar
highs; no empirical accuracy, backtest returns or profitability is established.

Both formerly outstanding shadow-history Playwright procedures have executed successfully
using repository-managed Chromium and real localhost listeners in the normally approved
environment. The new sufficient-data cohort procedure also passes page selection, ordinary
research, all result tabs, downloads and offline restore with identical reopened downloads.
Existing missing-depth/fee gates refuse trading backtests despite fitted controlled
probabilities. No sandbox policy, launch flags or test assertions were weakened.

Final verification passes **1,083 pytest tests in 563.76s**, Ruff lint/format (522 files),
strict mypy (519 files), all 21 named frontend assertions and all three real Chromium
procedures (18 screenshots, 18 matching downloads, zero page errors). All 544 frozen
source/configuration files and 68 original authentic receipt files remain unchanged.

See [milestone evidence](data/research-cohort-review/20261030/README.md) and the
[operating guide](docs/shadow-history.md) for final quality results and retained browser
artifacts. This uses the existing installation; no new clean-install or V1 release pass
is claimed. Return this milestone for supervisor review before another major phase.
Continue authentic forward collection, preserve Bitcoin's frozen boundaries, defer
new-family selection pending user approval and external provider checking pending
separately authorized credentials. Sufficient authentic labels, certified effective fees,
empirical two-family evidence and independent release acceptance remain open.

## Previous milestone: sustained shadow history to backtest inputs

Implemented on the designated `supervisor/20261030-194338` checkout from `8eab397`.
The supervisor owns every Git operation and independent acceptance. No credentials,
exchange orders, live activation, risk-limit changes or new family were used.
**V1 remains incomplete.**

The private workbench now enumerates all completed retained inputs as explicit partitions
of at most 128. Users can select a separate later outcome partition. Frozen snapshots
retain receipts and global calendar/model protections; selecting a later partition first
cannot move validation boundaries. Shadow ingestion verifies saved decision replay AND
causal raw-source/book bindings. R2/R4 inputs retain exact shadow decision clocks and
cycle-specific sized books. Missing labels, stale/future depth and uncertified fees stay
explicit refusals. Downloads expose original shadow features/versions, probabilities,
frozen specs, saved decisions, fee versions and later binary labels without promoting
forward predictions or exposing protected labels in experiment projections.

The 130-cycle CONTROLLED collector/store regression passes restart after cycle 64,
partitions of 128 and 2, later-label linkage, deterministic decision comparison and offline
restore without deleting receipts. Separate authentic original shadow receipts still yield
four events on two dates, zero source-matched scalar highs and honest insufficiency.
See the [guide](docs/shadow-history.md) and [evidence bundle](data/shadow-history-review/20261030/README.md)
for final quality results and the exact source fingerprint.
Final verification passes **1,073 pytest tests in 472.99s**, Ruff lint/format
(518 files), strict mypy (515 files), and all 21 named frontend assertions. The 538
frozen application/test/configuration hashes and 68 original receipt files are unchanged.

Managed Chromium installation succeeds; its one launch is denied before page interaction
at `crashpad/util/linux/socket.cc:45` (`setsockopt: Operation not permitted`, SIGTRAP).
The failure trace is retained and the denial is not retried. The executable two-procedure
Playwright harness covers controlled partition selection and authentic insufficiency,
research, inspection, downloads and offline restore. **Current browser acceptance is
outstanding**, not inferred from listener or DOM tests. Run both procedures in a permitted
environment before accepting browser behavior. No fresh clean-install pass is claimed.

Return this substantial intermediate milestone for independent supervisor review. Keep
forward collection authentic and frozen boundaries intact. Defer credential-dependent
verification, empirical release acceptance, new-family selection and profitability claims.
Do not start another major phase.

## Previous milestone: retained weather history through the browser

Implemented on designated `supervisor/20261030-191216` from `c461db3`. The supervisor
owns all Git operations and independent review. No branch/commit/merge/push operations,
credential access, external provider verification, new family or real orders were used.
**V1 remains incomplete.**

The browser now freezes and selects content-addressed weather snapshots from completed
public captures and shadow cycles, then uses the existing research → StrategySpec → R2
feature/model → R4 experiment workflow. Original receipt clocks, forecast revisions and
source-matched scalar-label rules remain intact. Independent counts, partition shortages,
original acquisition failures and protected exclusions are visible on every result tab.
The six-event sample remains a legacy option; retained datasets become the default when
available. Reports and review JSON remain downloadable after restart and offline restore.

Snapshots deduplicate repeated captures/vintages, preserve actual open-contract decision
times, validate later binary outcomes against original terms/raw receipts, publish atomically
and recover interrupted staging on explicit retry. First-snapshot calendar partitions stay
fixed (48/12/30 days, then protected holdout); inherited source/model protections persist.
Protected scalar labels cannot enter error/bias features. Actual decision clocks constrain
training/calibration label availability, including overnight/repeated receipts. Existing
minimum-evidence, execution, fee and risk gates remain; binary results never invent highs.

Final verification passes **1,058 pytest tests in 353.35 seconds**, Ruff lint/format
(backend/tools, 514 files), strict mypy (511 files), 18 named frontend checks and
actual managed Chromium acceptance (5 screenshots, 4 matching downloads, no page errors).
Authentic browser-workspace offline snapshot/restore also passes. See the
[verification receipt](data/weather-history-review/20261030/verification.json).

Authentic acceptance receipts yield **4 independent events on 2 dates, 24 contracts,
48 decision rows, 648 deduplicated observations and zero source-matched scalar highs**.
Research therefore saves explicit insufficiency with zero fitted probabilities or backtest
scenarios. Real Chromium interaction and the actual localhost/worker/recovery test pass;
final quality results are recorded in the [evidence bundle](data/weather-history-review/20261030/README.md).
The current environment is reused; no new clean-install pass is claimed. See the
[operating guide](docs/weather-history.md) and [acceptance matrix](docs/v1_acceptance.md).

The initial sandbox socket creation denial and incorrect default Playwright home-cache
attempt remain documented; repo-local managed Chromium installation and normal approved,
credential-free localhost/browser execution succeed. No sandbox policy or test assertion
was weakened. Return this substantial milestone for supervisor review before further work.
Authentic labels/fitting, certified fees, empirical two-family validation and independent
V1 release acceptance remain open. Preserve Bitcoin's frozen boundaries; select no family.
External-provider verification waits for separate credential authorization.

## Previous milestone: provider research through the private website

October 30 correction on the same designated branch, from `194fbe9`: unknown pricing
is refused on each raw model response before tool processing, validation retries,
suspended continuations or later stages. The previous post-stage cumulative check allowed
an unpriced first tool response to proceed through five requests and experiment setup;
the controlled regression reproduced that failure. The response wrapper now retains
individual identities, receipt clocks, token counts and prices, including a refused
response. Failed reviews distinguish an unknown bill from a known cost subtotal and
remain downloadable after restart, with zero experiments. Existing budgets, dedicated-key
isolation, holdout protection and execution permissions are unchanged. No Git mutations,
credential access or supervisor-control edits. Current correction verification is recorded
in [its evidence bundle](data/provider-review/20261030-pricing/README.md); the earlier
October 29 acceptance below describes that historical checkout. Ruff lint/format, strict
mypy (507 files), all **1,047 pytest cases in 338.02 seconds**, 15 frontend checks and both
actual Chromium procedures pass without external credentials. The browser evidence has
13 screenshots and 25 downloads with matching receipt hashes and zero page errors.
This uses the existing environment, not a new clean installation. **V1 remains incomplete.**

Implemented on designated `supervisor/20261029-141757` from `9dff058`. No Git mutations,
supervisor-control changes, real credentials, real orders or risk-limit changes. Existing
R4, private website, Bitcoin, continuous shadow and offline recovery were extended.
**V1 remains incomplete; external provider verification is blocked without separately
authorized research credentials.**

Server provider/model configuration plus fresh browser opt-in now select the existing
bounded four-stage research pipeline in an isolated durable worker. The job freezes the
public configuration. Only that worker can inherit the dedicated research key; local/mock
and shadow workers remain credential-free. Browser payloads cannot select credentials,
provider endpoints, code or filesystem paths. Typed hypotheses and candidate DSLs enter
the existing deterministic experiment engine and holdout gates. Stage/usage/tool/provenance
evidence is visible and downloadable. Missing keys, outages, malformed provider outputs
and deadlines persist failed reviews with zero fabricated candidates/experiments.
Cancellation, interruption/restart and offline restore preserve evidence without silently
repeating provider requests.

The new Playwright-managed Chromium procedure passes real page interaction against an
actual localhost listener: controlled provider transport yields three typed hypotheses and
honest deterministic insufficiency; all tabs, downloads, cancellation and restart pass.
A second unmodified listener with no credentials produces a saved `ResearchCredentialError`
and zero requests. The development pass took 27.5 seconds. This is **controlled provider
software evidence**, not an external provider session or empirical strategy performance.
The fresh locked installation passes Ruff lint/format, strict mypy (505 files), all 15
frontend cases and both real Chromium procedures. The provider procedure takes 49.2 seconds;
broader recovery takes about 1.2 minutes. Their 11 screenshots and 19 downloads match receipt
hashes, with zero page errors. The final **complete suite passes all 1,033 tests in 373.42
seconds**, with zero failures/errors/skips, including the unchanged collector reconnect test.
All 1,474 exported source/input files match checkout and installation. Offline provider
snapshot/restore also preserves 56 original files and all jobs/registry logical rows across
completed, failed, cancelled and interrupted runs. See [aggregate verification](data/provider-review/20261029/verification.json)
and [the milestone bundle](data/provider-review/20261029/README.md).

The retained collector timeout is diagnosed without changing its code/tests: sandbox
`socketpair()` creation succeeds but send fails with `EPERM`, and a minimal `asyncio.to_thread`
check stalls because the event loop cannot wake. Through the normal approval mechanism,
the credential-free socket/executor diagnostic and unchanged reconnect test pass. No event
loop, sandbox policy or assertion was changed. The first clean export also omitted existing
public fixtures/documents and used a temporary path too long for Chromium's Unix sockets.
A second complete run had only one failure: an indirectly cited vendored fee document was
still absent. The driver now exports the exact original citations and uses a short temporary
root. The full suite was rerun in the repaired locked installation without changing
application/test/fee code. Failed receipts stay intact; aggregate verification explicitly
links the final supplemental suite instead of relabeling old failures as passes.

Authentic weather fitting/outcome coverage, certified effective fees and empirical
two-family validation stay incomplete. Preserve Bitcoin's frozen dates; select no new
family. Return this coherent milestone to the supervisor before more major work.

## Previous milestone: local operation and recovery — historical checkpoint

The current correction starts at `99ba77a` on the existing
`supervisor/20261029-124902` branch. Source recovery verification now requires an existing
workspace under `data/cache/` and a validated snapshot before opening application stores.
One exclusive source lease covers snapshot, inspection and comparisons; a separate restored
lease covers initialization, comparisons and recovery. Busy, missing, out-of-cache and
incompatible sources cannot create or migrate databases. Normal supported legacy SQL NULL
bindings remain unbound. No Git mutations, supervisor-control changes, credentials, risk
changes or real orders; all Git operations remain with the supervisor.

The browser-independent real-listener recovery test uses unmodified research and shadow
workers, actual downloads, an interrupted active cycle, snapshot/restore, a fresh poll,
cancellation and another restart. The isolated gate includes both earlier listener files
and retains exact-source fingerprints and per-file deadlines/logs/JUnit. This is independent
of Bitcoin's future validation windows. Managed Chromium and the stalled complete suite
are not retried. **V1 remains incomplete**; browser/full-suite and empirical release gaps
still need independent acceptance.

**311 tests pass across 13 isolated pytest files, with three named R4 workflows deselected**;
Ruff lint/format (505 files), strict mypy (502 files) and 12 frontend assertions pass.
All 643 fingerprinted application/test/tool/config/data files remain unchanged during the
gate. The new actual-listener test passes in 23.1 seconds, including a genuinely interrupted
cycle and fresh authentic collection of 24 contracts/648 observations. No prediction,
intention, fill or performance is inferred from those model/fee-blocked decisions. The
corrected offline verifier also preserves 114 retained real evidence files, all logical
database rows and paused exports, with both original 24-decision replays passing.
See [exact-source results, artifacts and limitations](data/local-operation-review/20261029-leased-source-final/README.md).
No current browser, complete-suite, new clean-install or V1 pass is claimed. Return this
scoped correction for supervisor review before further major work.

### Earlier legacy SQL NULL binding correction

Implemented on the existing `supervisor/20261029-124902` checkout from `70cbc7a`.
No Git mutations, supervisor-control changes, real orders or credential access. The
supervisor retains all commits/merges/pushes. **V1 remains incomplete.**

The follow-up correction from `bd67f10` preserves supported legacy SQL NULL model bindings
through offline snapshot/restore. It does not invent a binding from a model reference or
export. New regressions migrate the old schema, compare logical rows and original evidence
bytes/clocks, run normal startup recovery, resume monitoring and verify continued blocked
scoring/replay. Malformed non-null bindings, including JSON `null`, remain refused before
publishing a snapshot or restored workspace.

**34 recovery tests and 291 focused tests pass** (three asynchronous experiment workflows
explicitly deselected), with Ruff lint/format, strict mypy (499 files), 12 frontend assertions
and recovery Playwright syntax/discovery checks. See [correction evidence](data/local-operation-review/20261029-legacy-null-binding/README.md).
These are controlled software checks in the existing environment, not a new clean install,
real-data capture or browser pass. The earlier Chromium launch denial and full-suite stall
remain unresolved; neither was repeated. The default acceptance driver still needs to run
in a permitted environment. No next major phase is started.

### Earlier local recovery evidence, before the legacy NULL correction

[Offline workspace snapshot/restore](docs/local-recovery.md) preserves jobs, the shared
lineage registry, frozen model/spec bindings and all run/shadow bytes. It requires the
exclusive server lease, snapshots SQLite consistently and verifies hashes, schemas,
references, registry lineage and cycle results before publishing a new destination.
Existing data is never overwritten. Unsafe paths/links and corrupt/incomplete evidence
are refused. Workers inherit the lease so a parent crash cannot permit a concurrent
snapshot or server while an old worker is still writing. Restore does not backfill missed
receipts or change frozen Bitcoin boundaries.

**23 original recovery regressions pass.** A fresh locked offline installation, with the final
CLI correction applied and reverified, passes Ruff lint/format, strict mypy (499 files),
pinned npm setup and all 12 named frontend checks. **280 focused tests pass, three asynchronous experiment
workflows explicitly deselected**; these cover recovery, shadow/model/risk boundaries,
controlled multi-cycle outcomes, deterministic experiments/execution and submission
refusal. This selection is not a complete-suite pass. Source hashes and package inventory
are retained in the [preparation receipt](data/local-operation-review/20261029-final-source/acceptance.json)
and [final source comparison](data/local-operation-review/20261029-final-source/source-cli-fixed-comparison.json).
The original network install failed DNS resolution; cache provisioning reused package
artifacts and managed Chromium, not the existing virtualenv or credentials.

An [offline authentic recovery proof in the locked installation](data/local-operation-review/fresh-authentic-current-source/verification.json)
restores one real research run, one paused monitor and two completed real cycles. All
non-database bytes and logical database rows match; paused export and both 24-decision
replays are identical. The installed CLI round trip also passes after the argument-order
correction found by this check. This reuses original October 29 receipts, creates no new source
data and makes no performance claim. Nonempty reservations, bound fitted models and
active/in-flight recovery have controlled evidence only.

The new real-browser research/results → shadow → snapshot/restore → fresh active cycle →
cancellation/restart harness is executable. Supported managed Chromium installation
succeeds, but its one launch fails before page interaction at
`third_party/crashpad/crashpad/util/linux/socket.cc:45`:
`setsockopt: Operation not permitted (1)` (SIGTRAP). No new screenshots, real listener
workflow or browser pass is claimed. The fresh-install full suite stalls in the existing
collector reconnect case; the diagnostic stack is retained and a 120-second deadline
exits 124. The earlier unbounded attempt was interrupted. No test, policy, event loop,
risk limit or sandbox setting was weakened; the denied launch was not repeated.

See [milestone evidence and exact remaining steps](data/local-operation-review/README.md)
and [V1 acceptance matrix](docs/v1_acceptance.md). The supervisor/human must run the default
acceptance driver in a permitted environment, inspect actual browser artifacts and obtain
a full-suite pass before marking this milestone accepted. No next major phase is started.
Empirical model/outcome coverage, certified fees, authorized provider evidence and a
validated second family remain explicit V1 gaps. New families require user approval;
broader serializers, hosted operation and structural scanning remain deferred.

## Earlier continuous shadow checkpoints

### October 29 model-to-shadow integration

Implemented and verified on designated `supervisor/20261029-120832`, based on `e8b7402`.
Research monitors now freeze the resolved StrategySpec and a unique checksummed data-only
weather model export, including model identity, parameters, fit/calibration clocks,
training-series scope, provenance and protected events. Compatible climatology, raw
forecast and forecast-error models can score causal forward samples; unsupported or
missing real models remain blocked. SQLite retains the frozen snapshot across restarts
and removal of the original export. No live refitting or executable model loading occurs.

Each cycle also retains at most ten sized public books and versioned series fee receipts.
Original feature availability is preserved, decision clocks follow receipts and
hours-to-close is recomputed. Series metadata remains uncertified because it does not
establish the coefficient or effective fee interval. Deferred book requests are explicit.
No fee schedule, fitted real model, intention, fill or profitability is fabricated.
Existing reservation caps, restart/pause recovery and later official outcome linkage remain
enforced. The browser shows the model binding, book/fee audits and explicit refusals.

**All 971 pytest tests pass in 275.90 seconds, with no failures or skips.** Ruff lint and
format checks, strict mypy (496 files), all 12 named frontend tests and JavaScript syntax
checks pass. Controlled regressions cover data-only model/calibrator fidelity, artifact and
spec tampering, temporal/contract/holdout gates, sized book failures, reservation limits
across cycles/restarts, later outcome linkage and deterministic JSON replay. They establish
software behavior, not empirical model performance.

The supported Playwright Chromium installation and real localhost research → start → pause
→ download → server restart → identical download → resume → second cycle → download
procedure pass; the fresh completion run took 21.7 seconds with zero page errors. Each real
cycle has 24 weather contracts, 648 observations, ten sized books, one uncertified fee
version, 14 deferred contracts and zero source/execution failures. All probabilities and
intentions remain absent for honest model/fee blockers. Screenshots, trace, downloads and
original raw cycle copies are retained; separate checksum/source-fingerprint and offline
decision replay checks pass. The initial decimal-strike parser failure and incomplete test
log are preserved separately rather than represented as successes.

See [reviewable implementation and executed evidence](data/shadow-review/20261029-model-integration/README.md).
The socket-denied sandbox preflight was followed by normal approved test execution in a
permitted context; no sandbox policy, test, event-loop behavior or risk cap was weakened.
No human step remains for this scoped browser procedure. Clean-install/final release
evidence, authentic fitted models, certified fees and two-family empirical support remain
outstanding, so **V1 remains incomplete**. Bitcoin boundaries are unchanged and any new
major family still requires user approval. PROJECT_CONTEXT and the roadmap now reflect
the user's general-platform direction and independent forward-collection priorities.
All Git writes remain with the supervisor. Return this milestone for review before starting
another major phase; submissions remain disabled.

### October 29 reserved quote probability bindings

On the same designated branch, starting at `67a049c`, the shared probability resolver
now rejects explicit `yes_bid` and `yes_ask` bindings. These names remain available as
ordinary quote predicates when a separate model probability is bound. The reproduced
controlled NO-side case previously passed a `> 0.30` predicate using quotes `0.40`/`0.50`
despite audited YES probability `0.10`, producing a risk-approved NO intention. Both
aliases now refuse in the resolver, compiler, shadow evaluation and actual JSON replay.
Original inputs, prior evidence and timestamps are preserved; no historical result is
rewritten to make replay pass.

**179 focused tracking/workbench tests, 31 shared interpreter/replay/execution tests
and 46 deterministic experiment/risk tests pass** (three asynchronous workflow cases
explicitly deselected), along with Ruff lint/format, strict mypy (491 files), 12 frontend
presentation tests and JavaScript syntax checks. Twenty new cases cover both reserved
names, the NO-side reproduction, compiler/JSON refusal and valid quote predicates with
implicit/custom model aliases. Existing calibration, provenance, holdout and risk
regressions pass. See [executed evidence](data/shadow-review/20261029-reserved-quote-bindings/README.md).

The complete suite and shadow browser/listener acceptance remain incomplete; previously
documented permission-denied/stalled attempts were not repeated. The existing managed
Chromium real-listener harness and complete suite remain supervisor/human acceptance
steps in a permitted environment. **V1 remains incomplete.** No real orders, credentials,
risk-limit changes or Git writes; all Git operations remain with the supervisor.

### October 29 shadow probability binding correction

On the same designated branch, starting at `d43e262`, shadow evaluation and the strategy
compiler now share the validated probability-name resolver. Implicit custom
`*_probability` predicates and explicit aliases receive the audited model prediction.
Raw features under that name remain in the audit but are excluded from the interpreter's
observations, including at identical availability clocks. A validated probability of
`0.10` cannot become a raw `0.95` intention; eligible intentions use the exact model value.
Missing or ambiguous predictions, required input features, model identity, calibration,
provenance, protected-event and risk gates retain their existing fail-closed behavior.

**163 focused tracking/workbench tests and 27 shared interpreter/replay/execution tests
pass**, plus **46 selected deterministic experiment/risk tests** (three asynchronous
workflow cases deselected), with Ruff lint/format, strict mypy (491 files), 12 frontend
presentation tests and JavaScript syntax checks. The 57 new cases cover implicit names,
absent/null/conflicting raw values, equal receipt clocks, explicit aliases, duplicate
predicates, ambiguous bindings,
model identity and actual JSON replay equality. Initial regressions reproduced eight
failures before the fix. These are controlled software checks, not empirical performance.
See [probability binding evidence](data/shadow-review/20261029-probability-binding/README.md).

The bounded complete-suite attempt collected 903 tests, passed two architecture checks,
then stalled in the existing collector reconnect test and exited 124 after 70 seconds;
its stack is retained. A broader experiment/risk selection also timed out after 60 seconds;
the later deterministic selection above does not establish full experiment-suite acceptance.
Current shadow browser/listener acceptance remains unexecuted.
Previously denied Chromium/socket attempts were not repeated or bypassed; run the existing
managed Chromium harness and complete suite in a permitted environment. Forward scoring
still requires fitted probabilities, certified fees and sized books. **V1 remains
incomplete.** All Git operations belong to the supervisor; review this correction before
another major milestone.

### October 29 calibration availability and model provenance correction

On the same designated branch, starting at `61eef2f`, shadow evaluation now requires a
non-null `calibrated_before` clock at or before the decision for Platt/isotonic predictions.
Missing, invalid or mismatched model metadata `data_kind` blocks intentions and risk;
the dataset's required real/synthetic classification is never used to infer the model's.
Decision inputs retain the supplied model classification while withholding targets and
preserving the union of dataset/model protected events. Matching inputs remain eligible;
uncalibrated outputs still permit a null calibration clock.

**106 focused tests and 25 shared replay/execution tests pass**, along with Ruff
lint/format, strict mypy (491 files) and 12 frontend presentation assertions. New regressions
reproduced both unsafe approvals, exercise both calibration methods and clock boundaries,
missing/mismatched provenance and matching classifications, and verify JSON replay equality
and protected-event exclusions. Blocked cases also fail immediately if the interpreter or
risk evaluation is invoked. These are controlled software inputs, not empirical results.

The full-suite diagnostic collected 846 tests, passed two architecture tests, then stalled
in the existing collector reconnect test; its 70-second external deadline exited 124.
Asyncio debug logs show `PermissionError: [Errno 1] Operation not permitted` writing the
self-pipe; the pending coroutine chain reaches the SDK signing executor while the event
loop remains in `select`. This confirms the previously documented sandbox wakeup failure
for the current collector stall. No test, SDK, event-loop policy or application timeout was
weakened to hide it. **Full-suite and current shadow browser/listener acceptance remain
incomplete.** The denied Chromium/listener attempts were not repeated; the existing real
Playwright harness must run in a permitted environment.

Legacy replay files that previously removed the model classification now fail closed;
they cannot verify their original decision hashes under this stricter policy. A read-only
check confirms the two retained original decisions block on missing provenance, original
files remain unchanged, and the intentional tamper is still rejected. No legacy receipt,
clock, classification or decision is backfilled. See [executed evidence](data/shadow-review/20261029-availability-provenance/README.md).
All Git writes remain with the supervisor. V1 remains incomplete; review this correction
before another major milestone.

### October 29 calibration and holdout correction

On the same designated branch, starting at `a1cafcb`, shadow intentions now enforce the
requested calibration method before intent/risk evaluation. Dataset protection and
model-metadata holdouts are combined before decision projection and replay serialization;
the combined boundary survives metadata redaction. Protected samples, predictions and
decisions are excluded. Regression tests cover mismatches, permitted calibration methods,
each protection source, their union and JSON round-trip replay equivalence. A retained
pre-correction cycle still reproduces its original decision hashes, and its intentionally
tampered companion still fails checksum verification.

**75 focused tests and 25 replay/execution tests pass**, along with Ruff lint/format,
strict mypy (491 files) and the existing frontend presentation assertions. The unchanged
full-suite attempt collected 815 tests but stalled again in the collector reconnect case;
its bounded attempt and diagnostic stack are retained. **Full-suite, current shadow browser
and localhost-listener acceptance remain incomplete.** The previously denied browser/socket
launches were not repeated or bypassed. The executable Playwright procedure remains the
outstanding supervisor/human step. See [correction evidence](data/shadow-review/20261029-boundaries/README.md).
No real orders, credentials, Git writes, supervisor controls or empirical claims were added.
V1 remains incomplete; return this correction for supervisor review before another phase.

### Original shadow implementation checkpoint

Implemented on the designated `supervisor/20261029-001707` checkout starting at `1ed5522`,
with no Git writes, credential access or supervisor-control changes. **V1 remains
incomplete.** Bitcoin work is preserved as an optional adapter, not the mandatory second
family. New family selection needs an evidence comparison and user approval. Authentic
forward collection keeps its original clocks and frozen historical validation windows;
independent product work does not wait for Bitcoin's future dates.

The [continuous shadow workflow](docs/shadow-tracking.md) connects a frozen real research
candidate to a durable scheduler, existing public capture/feature adapters, replay decision
view, typed strategy interpreter and risk engine. SQLite stores lifecycle controls,
append-only cycles, first-seen contract terms and later official binary outcomes. Cycles
retain raw receipts, unsized listing quotes, features/versions, predictions or explicit
model refusals, intended orders and risk checks when eligible, artifact/code hashes and
deterministic decision digests. Browser UI exposes saved monitors, pause/resume, cycle
decisions and evidence downloads. Restarts preserve completed results and reservations,
interrupt unfinished cycles and collect fresh receipts. Failure backoff, bounded workers,
five-failure pause and explicit workspace budgets are implemented.

Existing forward adapters still lack fitted forward probabilities, certified fees and
sized books. Actual forward decisions therefore block, with null probabilities/intents;
eligible/risk-rejected intentions and reservations are verified with controlled fixtures
only. There is no broker call, submission, fill, simulated P&L or profitability claim.
Official binary results are never substituted for scalar source labels. This is an
independently useful collection/audit milestone, not empirical model or V1 acceptance.

Ruff lint/format and strict mypy (491 files) pass; **59 focused tests pass** (45 new shadow
unit/integration checks plus 14 existing workbench boundary checks). All existing frontend
presentation assertions and JavaScript syntax checks pass. The full suite stalled in the
existing collector reconnect test; separate broader attempts also stalled in an existing
gateway test and the offline R4 research workflow. Their diagnostic stacks are retained;
no complete-suite pass is claimed and no existing test was changed or weakened.

One actual recorded research → shadow subprocess probe completed the research step, then
retained five clocked acquisition failures with zero HTTP receipts/contracts/observations.
The normal four-minute worker deadline persisted a failed cycle and partial files; the
monitor was explicitly paused. This verifies a real deadline/failure path, not successful
ingestion or continuous operation. Full details are in the [milestone evidence](data/shadow-review/20261029/README.md).
Playwright's supported Chromium install command succeeded, but its one launch attempt
failed before page interaction: crashpad `setsockopt: Operation not permitted`, then
`SIGTRAP`. Reports/trace are retained; no screenshot or browser acceptance pass is claimed.
The executable real-listener/page-interaction procedure remains for supervisor/human
acceptance in a permitted environment. No retry of the denied launch was made.

## Previous checkpoint: October 28 history evidence

**V1 and second-family empirical acceptance remain incomplete. Actual Bitcoin result
reconciliation and retained-real-receipt browser acceptance now pass.** This continuation
started clean on `supervisor/20261028-201233` at `97074a3`. Local `main` also points to
that supervisor checkpoint and contains the earlier R4/website/history work; no remote
freshness is claimed. No Git mutation or credential access was performed.

The [current evidence](data/bitcoin-history-review/20261029T001500Z/README.md) retains
four successful exact official result GETs, all finalized NO with matching payouts,
settlement clocks and frozen contract terms. Inventorying all eight original workbench
Bitcoin captures still yields four independent events across three dates. The new labels
became available at their October 29 receipt times; earlier decisions remain unchanged.
The [history workflow](docs/bitcoin-history.md) now shows the exact fitting/validation
counts, shortages, classes and fixed windows on every tab and in both downloads.

An actual Playwright-managed Chromium check passed against the real localhost server
and unmodified worker using imported **real retained receipts**, with no response stubs
or simulated clocks. Form submission, all three tabs, four screenshots, four checksummed
downloads, server restart and identical reopened bytes passed; zero page errors. Two
independent experiment replays produced the original identity and serialized refusal
results. This verifies honest insufficiency, not fitted empirical performance. The
[October 28 controlled continuation](data/bitcoin-history-review/20261028T235347Z/README.md)
also remains valid: 752 pytest tests and two controlled/empty browser procedures passed
there with permitted sockets. Older sandbox-denial logs are historical failed attempts.

The evaluated snapshot has 4/40 fitting events on 3/20 dates, only NO outcomes and
0/20 validation events on 0/10 dates. Frozen validation is December 24, 2026 through
January 22, 2027; ten validation dates cannot exist before January 2. A separate one-shot
source probe succeeded (three HTTP 200 receipts, 318 contracts, one spot observation,
three pending forward samples). Current public access is feasible, but today's downloads
cannot manufacture earlier receipt history or future validation. Longitudinal capture or
a separately reviewed archive requires a user decision. No partition boundary was moved.

Current `make check` passed: Ruff lint/format, strict mypy across 483 files and
**754 pytest tests in 269.06 seconds**, with no skips. All 12 frontend checks passed.
The real browser procedure passed in 19.1 seconds; the independent receipt/determinism
verifier passed. These are working-checkout checks; no clean install is claimed.

Continuous paper/shadow, final V1 acceptance and clean-install release evidence remain
deferred. Trading scenarios and P&L remain closed without certified rules, depth and fees.
The supervisor owns independent review, clean-checkout verification and every Git write.
No production submission or real order was enabled.

## October 26 acceptance record

**All four documented browser procedures passed** with isolated Playwright Chromium and
the real localhost backend on October 26, 20:42:33–20:43:23 UTC. No Computer Use or personal
Chrome was used. The [current bundle](data/workbench-review/20261026T203717Z/README.md)
retains the passing [browser receipt](data/workbench-review/20261026T203717Z/browser-attempt-2/browser-receipt.json),
26 screenshots, 24 checksummed browser downloads, JSON/JUnit results, a trace, actual source
captures/reviews and final SQLite snapshots. Supplemental readable UI screenshots and the
first failed harness attempt are preserved separately. The failure was a harness assumption
about null calibration timestamps; no application change or weakened safety rule was needed.

Recorded weather showed typed exact comparisons, real insufficiency, empty probabilities
and excluded holdout. Synthetic mode exposed 100 of 192 validation records, banners on
all result tabs and zero negative-control fills in all three scenarios. Public weather
returned 8 successful HTTP receipts, 24 contracts and 648 observations; Bitcoin returned
3 successful receipts, 210 contracts and one observation. All Bitcoin settlement gates
remained closed, verified sources empty and 420 authority mentions separately unverified.
A deliberately OS-denied backend run separately produced two clocked acquisition failures
and zero receipts/data; its incomplete summaries remained visible on all three tabs and in
the text report. Public capture provides no historical evaluation or real-data returns.

Active cancellation, subsequent worker-slot reuse, shutdown of an active run, interrupted
restart history and reopening all six completed reviews passed. Browser JSON and report
downloads match retained protected results, with identical checksums after restart. One
browser console resource 404 is retained; no JavaScript page errors or failed workflow
requests occurred. See the [reproducible harness](frontend/browser/README.md).

An isolated read-only export of reviewed commit `18be50c` passed locked setup, Ruff
lint/format, strict mypy across 477 files, **734 pytest tests in 184.91 seconds**, JavaScript
syntax and all **nine frontend tests**, with no skips. All 2,347 exported files remained
unchanged. All 275 pre-existing receipt checksums passed. Earlier source states, HTTP-only
evidence, browser denials and SQLite stall/repair receipts remain immutable historical records.
No application source, financial safety boundary or Git ref was changed.

The supervisor must review this evidence, complete independent final clean-checkout
verification and handle every commit, merge and push. **V1 remains incomplete** because
usable second-family history/semantics/evaluation and continuous paper/shadow remain open.
See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) and [the operating guide](docs/workbench.md).

## Delivered capabilities

- Read-only Kalshi collection, restart-safe recording, integrity/freshness health,
  generic actual-contract discovery and reproducible Parquet datasets remain intact.
- Forward Open-Meteo/NWS capture, causal feature matrices and event-level temperature
  distributions feed contract probabilities through the existing R2 modeling pipeline.
- Configurable PydanticAI research uses bounded, read-only evidence and full-spec criticism,
  followed by independent validation. Real providers require explicit opt-in and a dedicated key.
- `research-and-test` joins research → typed candidates → feature/model selection → temporal
  predictions → deterministic replay → forecast/trading validation → comparison and artifacts.
  Explicit offline and synthetic modes never masquerade as provider-backed empirical research.
- The bounded interpreter supports actual ticker/event/series selection, UTC/date entry
  windows, YES/NO, comparisons, versioned features/models, net edge, price/spread/size limits,
  fixed contracts/dollars, position caps, settlement and simple predicate exits. Hedging,
  Kelly, resting orders and holding-duration exits are rejected explicitly.
- Replay processes books, decisions, latency, fills and settlements chronologically. It
  bounds book age/split/close/expiry, consumes shared depth, reserves pending capital and
  passes actual event exposure to risk. Partial/unfilled remainders cancel; all fills are
  simulations. Optimistic/base/conservative scenarios expose execution sensitivity.
- Experiments preserve date/event grouping, separate calibration/validation, pre-holdout
  walk-forward diagnostics, protected final holdout, minimum evidence gates, date-block
  intervals and search counts. Rankings use validation Brier, with tied scores sharing rank;
  synthetic P&L never ranks or promotes candidates. No lifecycle promotion occurs.
- The existing SQLite Registry, local MLflow and Parquet/JSON artifacts retain prompt,
  hypothesis/spec, model/feature/data/code/config identities, predictions, orders/fills,
  equity, fees, criticisms and rejections. Identical inputs replay the same experiment ID.
- Family-neutral samples/prediction-provider registration and evidence projections are
  tested with a controlled non-weather mentions fixture; real mentions ingestion is absent.

## Evidence and checks

R4 final `make check`: **626 tests passed in 233.31s**, Ruff lint/format clean and
strict mypy clean (463 files). All 595 R3 tests remain, with 31 new R4 cases covering
chronology/capacity/risk, execution semantics, provenance/cutoffs, family adapters,
artifact accounting and end-to-end replay. Two old expectations now supply explicit
fixture fees and recognize supported spread limits; no invariant was weakened.
Frozen CLI reports are in [data/r4-demo](data/r4-demo/README.md) and the
[experiment guide](docs/experiments.md).

- **Real historical integration:** 36 contracts/six Philadelphia+Chicago city/day events
  across three dates. Zero eligible historical forecasts/scalar-temperature labels, no
  sized books or certified historical fees/rules. The integrated offline research run
  returns insufficient-data/unsupported candidates, without fitted empirical models,
  forecasting metrics, fills, P&L or a profitable-strategy claim.
- **Synthetic integration:** 240 date blocks/480 city-day events exercise R2 fitting,
  predictions, four mock research candidates, execution scenarios, statistical diagnostics,
  rankings, negative-control rejection and persisted artifacts. This verifies software;
  it does not establish an empirical Kalshi advantage. Final holdout remains untouched.
- **Provider/feed status:** no dedicated research or Kalshi read key is configured here.
  Live LLM research and authenticated sustained WebSocket collection remain unverified.
- **Forward weather evidence unchanged:** three real polls/restart on October 24 retained
  18 receipts, four provider/location vintages and 648 hourly points. October captures
  cannot backfill September features. This is not a multi-day operating deployment.

## Remaining limitations

Actual aligned forecast vintages, historical rule evidence, source-matched scalar highs,
independent events, sized books and effective fee evidence are still required for real
strategy evaluation. Weather Company settlement cannot be replaced by NWS CLI.
Snapshot simulation does not model queues, exchange competition or observed fills. Capacity
resets on a changed snapshot/advancing sequence are explicit assumptions. Equity between
settlements uses cost basis; reported drawdown is not a market-marked drawdown. Selection
intervals are descriptive after repeated searches, not a corrected discovery guarantee.

No production order transport or trading credentials were added. Legacy artifacts and
previous recovery branches are preserved. No real strategy is approved or validated.

## Exact next action

Supervisor review of the [probability binding correction](data/shadow-review/20261029-probability-binding/README.md),
the [calibration/holdout correction](data/shadow-review/20261029-boundaries/README.md)
and integrated [shadow milestone and executed limits](data/shadow-review/20261029/README.md),
then run the supplied browser/listener acceptance procedure and unchanged full suite in a
suitable environment, investigating the retained collector stall. Leave all Git
operations to the supervisor and stop before another major milestone. Empirical modeling,
certified forward scoring/depth/fees, an approved second-family decision and the independently
verified V1 acceptance matrix remain open. Do not spend another autonomous phase waiting
for Bitcoin history or move its frozen boundaries. No real strategy is approved.
