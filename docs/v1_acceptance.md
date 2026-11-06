# Market-family screening — November 5, 2026

**complete=false.** This milestone supports the two-family gate; it does not satisfy it. See
[family-selection.md](family-selection.md).

| Requirement | Evidence | Result / remaining gate |
|---|---|---|
| Reproducible comparison of candidate families | `families/screening.py`, `test_family_screening.py`, `data/family-screening-review/20261105/` | Deterministic, hashed per-series report over 29 retained receipts; a rerun is byte-identical. |
| Fail-closed receipt handling | Tests for malformed, contradictory, tampered and existing-output cases | Ambiguous evidence is refused; no outcome or authority is inferred. |
| Read-only bounded catalog acquisition | Fetch tests with a mock transport; one real attempt | Software behaviour is tested. The real attempt was blocked (no egress, issue #3), so no fetched catalog exists. |
| Two empirically validated families | — | **Open.** Candidate catalogs still need fetching, the user still needs to approve a family in writing, and that family still needs point-in-time sources, labels and validation. |

# Browser regression sweep and CI — November 5, 2026

**complete=false (V1).** Branch `claude/vibrant-bohr-b1kuuh` stacked on PR #1.
[Executed evidence](../data/browser-regression-review/20261105/README.md).

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| All website procedures on the current tree | 14 `frontend/browser/*.spec.cjs`, receipts, Playwright JSON, `MANIFEST.sha256` | **Pass:** 19 tests in 12 spec files, plus 3/4 workbench workflows, 0 page errors. **Open:** `weather-labels` and workbench workflow 3 need public egress; they fail honestly with `ConnectError` here. |
| Label-partition UI consistency | `frontend/src/app.js`, new DOM regression | **Defect fixed:** an out-of-order overlapping render could show another partition's requests. |
| Repeatable acceptance runs | 7 specs derive archive/import paths from unique workspaces | **Harness fixed:** run-to-run archive collisions; unignored `data/recovery/`. |
| Continuous integration | `.github/workflows/ci.yml`, GitHub run 42116073148 | **Pass:** Ruff, strict mypy, 25 frontend tests, **1,320 pytest in 693.83s** on a clean runner with no secrets. Browser/public acceptance stays separate. |

# Prospective-evaluation acceptance completion — November 5, 2026

**complete=false (V1).** Branch `claude/vibrant-bohr-l2suow` from main `55b2bea`. Closes the
outstanding browser, listener and complete-suite gates of the October 31 milestone below.
[Executed evidence](../data/prospective-evaluation-review/20261105/README.md).

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| Offline snapshot/restore portability | `api/recovery.py`, `api/recovery_proof.py`, `tests/architecture/test_sqlite_uri.py` | **Defect fixed.** Read-only `file:` URIs lacked `uri=True`; recovery refused on SQLite builds without `SQLITE_USE_URI`. Static guard fails on the pre-fix tree. |
| Real website/browser acceptance | `prospective.spec.cjs`, receipts, screenshots, downloads, traces | **Pass:** both procedures (controlled synthetic; authentic insufficiency), 6 screenshots, 12 downloads identical across restart and offline restore, 0 page errors. First attempt (failed at snapshot) retained. Chromium 153 (preinstalled build 1243) used at the pinned path; exact build 1194 not claimed. |
| Complete quality gate | Ruff/format, strict mypy (557 files), 24 frontend, full JUnit | **Pass:** all **1,320 pytest cases in 619.14s**, zero failures/errors/skips, incl. 11 listener cases and 14 shadow-history cases. 73 original receipt/Bitcoin hashes unchanged. |
| Remaining V1 gates | Existing empirical/provider/fee/family gates | Unchanged: authentic history/validation, certified fees, authorized provider verification, approved second family, multi-day operation and independent review remain open. |

# Prospective shadow-evaluation reports — October 31, 2026

**complete=false.** Implemented on designated `supervisor/20261031-081845` from `a83b9db`;
Git operations and independent review remain with the supervisor. See
[operation](prospective-evaluation.md) and
[executed evidence](../data/prospective-evaluation-review/20261031/README.md).

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| Pending, refused and matched forecasts | `tracking/prospective.py`, website panel, JSON/CSV routes | Implemented using verified saved forecasts and subsequent raw official receipts; original sample/model/receipt clocks stay visible. |
| Repeated polls and independent evidence | `test_prospective.py`, offline synthetic projection | 39 poll observations yield 13 contracts, 12 events/dates and only ten matched events; strikes share event weight. Earliest pre-close observation cannot be replaced by a later forecast. Controlled evidence only. |
| Causal matching, revisions and protection | Late receipt, wrong terms/payout, same-clock conflicts, later protection and rehashed-source forgery tests | No backdated availability; invalid/ambiguous results refuse. Protected rows/predictions are excluded. Finalized contracts receive bounded revision checks. |
| Forecast diagnostics versus accounting | Per-model/data-kind Brier/log loss/reliability bins; real collector revision regression | Ten matched events on five dates are descriptive-monitoring minimums. Trading fees/depth/risk remain separate; original first settlements and monetary caps stay fixed. No validation or return claim. |
| Authentic evidence | Unchanged 68-file original shadow import and offline exports | 24 refused contracts, four events, two dates, 48 polls, no usable predictions or metrics. Authentic empirical evaluation remains insufficient. |
| Restart and offline replay | `test_prospective_offline.py`, durable offline proof | JSON reports and CSV bytes reproduce after restart and verified snapshot/restore, with all 23 synthetic and 68 authentic cycle files unchanged. |
| Real website/browser acceptance | `prospective.spec.cjs`; retained installation, discovery, launch and listener logs | **Outstanding.** Chromium launch denied at `socket.cc:45` (`setsockopt`, SIGTRAP); actual listener denied socket creation (`Errno 1`). Two executable real-page/download/restart/restore procedures remain for a permitted environment. No screenshots/downloads were executed in this runtime. |
| Complete quality/release acceptance | Current evidence logs and bounded all-file summary | Scoped lint/type/frontend/offline tests are recorded separately from incomplete full-suite/browser gates. V1, independent review, sufficient authentic history, authorized provider verification and approved second-family evidence remain open. |

# Bounded immutable label partitions — October 31, 2026

**complete=false.** This intermediate milestone on designated `supervisor/20261031-073225`
removes the finite acquisition cap while retaining bounded evidence partitions. All Git
operations and independent review remain with the supervisor. See [operator workflow](label-partitions.md)
and [executed evidence](../data/label-partition-review/20261031/README.md). Historical matrices
below retain their original scope; their former workspace-wide acquisition limit is superseded.

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| Collection beyond 128 controlled batches | `test_label_partitions.py`; managed-Chromium `label-partitions.spec.cjs` | Actual acquisition service executes 260 controlled batches across 128/128/4 partitions; browser executes 130 unique request IDs across 128/2. Accelerated dates/source responses prove software behavior only. |
| Immutable rollover, idempotency and bounded work | `label_partitions.py`, `label_service.py`, chained seal downloads | Original flat files stay in place; archived IDs do not refetch. Per-partition request/inventory limits, queue/network limits and snapshot/recovery storage budgets remain enforced. |
| Busy rollover, cancellation and failure recovery | Drain/backpressure regression; after-seal interruption regression; Chromium outage/pause controls | Durable plans retain their identity; busy schedules wait for drain. Source errors, interrupted requests and receipts remain inspectable. Sealed corruption and symlinks fail closed. |
| Website inspection and immutable datasets | Partition selector, all bounded request rows, manifest/source downloads, dataset freeze | Both actual Chromium procedures pass. Cross-partition audits replay in deterministic hash order. The first browser attempt exposed an audit-order bug and remains recorded as failed. |
| Original clocks, holdouts and independent event counts | 260-revision snapshot test, existing leakage/risk regression suite, 73 original safety hashes | Receipt clocks and frozen boundaries stay fixed. Many revisions of one event still count as one event; model/history insufficiency remains explicit. |
| Restart and offline recovery | Browser compares original/restored schedules, seal and archived label bytes; verifies all 262 controlled label-store files | Executed listener restart and offline snapshot/restore pass without duplicate controlled requests. Active restored schedules honor earlier opt-in; pause before inspection exports. |
| Separately identified authentic operating evidence | Authentic whole-shadow import, two new public source receipts, browser restart/offline restore | Three station/day scalar highs qualify; one preliminary report is refused. This short real-clock sample does not establish multi-day operation, sufficient independent history, empirical models or profitability. |
| Quality and independent review | Ruff/format, strict mypy, frontend, focused/full pytest and actual Playwright reports in current bundle | Repository Ruff/format, strict mypy (551 files), 22 frontend checks, 64 focused and 12 integrity/lifecycle cases, all 1,292 pytest cases (679.34s; zero failures/errors/skips) and both final Chromium procedures pass. Existing locked environment reused; no new clean-install or independent release approval is claimed. |
| Outstanding V1 gates and safety | Existing empirical/provider/fee/release gates | V1 remains incomplete. More authentic history, sustained operation, certified fees, authorized provider verification, two-family evidence and independent acceptance remain open. No credentials, new family, real orders, activation or risk-limit changes. |

# Atomic request-claim/cancellation correction — October 31, 2026

**complete=false.** Corrected on designated `supervisor/20261031-054650` from `2f93999`.
Git operations and independent acceptance remain with the supervisor. This correction closes
the request lifecycle races; it does not close the outstanding empirical or V1 release gates.
[Current correction evidence](../data/forward-validation-review/20261031-atomic-claim/README.md)
records exact executions and preserves the interrupted browser attempt separately.

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| Cancellation after queue selection, before claiming | Barrier-based `test_queued_selection_cannot_start_after_durable_completion`, parameterized over interrupted/completed/failed | No acquisition starts from a stale queued copy; terminal request and batch bytes stay identical. |
| Cancellation after ownership registration, before acquisition | Barrier-based pause/shutdown regressions, actual-listener controlled browser startup barrier | Ownership and running status are atomic; pending cancellation prevents source calls before the callback runs. Interrupted evidence survives late completion, restart and restore. |
| Receipt retention, repeated claiming and existing workflow | Lifecycle/scheduler/label/listener tests; controlled/authentic managed-Chromium procedures | Existing partial receipts, bounded acquisition, provenance, pause/resume, immutable freeze and offline recovery remain covered. Exact quality/browser results are in the current evidence bundle. |
| Required quality and browser regression gates | Current Ruff/format/mypy, frontend, focused/full JUnit and actual Playwright reports | **Scoped pass:** strict mypy/format cover 547 files; 22 frontend checks, 50 focused tests and all **1,277 pytest cases in 555.99s** pass with no failures/errors/skips. Both actual Chromium procedures pass with 11 screenshots, six downloads and zero page errors. Interrupted first attempt remains explicitly incomplete. Existing environment reused; independent review remains pending. |
| Safety and release boundaries | Current safety hashes and existing empirical/provider/fee gates | Original receipt and Bitcoin boundaries remain unchanged. No real orders, credentials, risk-limit changes or Git mutations. Sufficient independent data, certified fees, provider verification, two-family validation and independent V1 review remain open. |

# Continuous forward-validation acceptance — October 31, 2026

**complete=false.** This intermediate milestone connects opt-in scheduling to existing
label/shadow infrastructure on `supervisor/20261031-054650` from `9d9f921`. Git operations
and independent review remain with the supervisor. [Current evidence](../data/forward-validation-review/20261031/README.md)
separates controlled transitions, authentic original receipts and new public acquisition.
Prior evidence below keeps its original scope; no release acceptance is inferred.

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| Opt-in continuous workflow and browser progress | `weather/label_schedule.py`, website controls, `forward-validation.spec.cjs` | Executed managed Chromium covers enable/refused missing opt-in, date progress, outage details, pause/resume and downloads through actual localhost listeners. Following existing public/shadow partitions is separately opt-in. |
| Bounded histories over eight dates and repeatability | Controlled twelve-date pytest/listener/browser procedures | Requests split into batches of eight and four dates. Preliminary-to-official transitions, outage backoff and daily revisions retain distinct immutable receipts. These controlled dates/results are software evidence only. |
| Authentic point-in-time labels and source semantics | Authentic whole-shadow import and new scheduled Weather Company acquisition | Two October 29 highs qualify; two October 30 preliminary station reports are refused. Availability starts at each new receipt. Sparse authentic history cannot establish fitting or performance. |
| Shutdown/restart, idempotency and offline replay | Active partial-batch cancellation, before-enqueue crash, post-acquisition bookkeeping recovery, browser restart/offline restore | Original planned request IDs survive recovery and pause/block. Reopened/restored paused-state downloads compare byte-for-byte; source/rule/batch references revalidate offline. Continuous multi-day authentic operation has not been observed. |
| Immutable snapshots, revisions and protected boundaries | Shared history pipeline, late-protection tests, offline source/reference validation | New snapshots preserve calendars, original receipt/publication/revision semantics and protected holdouts. Existing insufficient-data gates remain in force; a new receipt cannot repair an earlier cutoff. |
| Paper/risk/credential boundaries | Existing deterministic shadow/accounting engines and regression suite | No new order transport, credentials, submission activation, model promotion or risk-cap changes. Acquisition capacity exhaustion blocks with durable backlog; no evidence deletion. |
| Reproducible realistic empirical backtests, two families and providers | Existing model/experiment/provider gates; no new empirical claim | **Incomplete.** More authentic independent dates and validation, certified fees, separately authorized external-provider verification and two-family release evidence remain open. Bitcoin boundaries are preserved; no additional family is selected. |
| Quality, install and independent review | Exact executed logs and artifact verification in current bundle | **Pass:** Ruff/format and strict mypy (546 files), all 22 frontend checks, all **1,271 pytest cases in 553.51s** with no failures/errors/skips, and both managed-Chromium procedures (10 screenshots, 6 downloads, 0 page errors). All 73 original receipt/boundary hashes verify. Existing locked environment reused; no new clean-install or independent release pass is claimed. Supervisor review remains required. |

# Forward weather-label acquisition acceptance — October 31, 2026

**complete=false.** This is an independently useful intermediate milestone, not V1 release
approval. Implemented in place on `supervisor/20261031-050653`; Git operations and independent
review remain with the supervisor. [Current evidence](../data/weather-label-review/20261031/README.md)
separates new authentic source acquisition, original forecast receipt replay, controlled
refusal/correction tests and browser interactions. Historical results below retain their scope.

| Requirement | Concrete evidence | Result / remaining gate |
|---|---|---|
| User-facing acquisition → status → provenance → immutable dataset → research | `frontend/browser/weather-labels.spec.cjs`, actual managed-Chromium receipts/screenshots/downloads | **Scoped pass.** New public acquisition and honest insufficient-data research; identical label/review/report downloads after listener restart. The first failed selection-persistence attempt stays retained. |
| Authentic source-matched scalar highs | `weather/labels.py`, original public portal JSON and acquisition batch downloads | **Two October 29 station/day labels verified; two October 30 preliminary reports refused.** Existing Philadelphia/Chicago rules name Weather Company; NWS and binary outcomes are not scalar substitutes. More independent dates remain required. |
| Receipt/publication/revision clocks and leakage | `labels.py`, `label_history.py`, `_verify_labels`, corrected/late/protected tests | **Scoped pass.** New receipt-time availability; absent provider clocks stay null. Revisions stay distinct; only versions known at model cutoff qualify. Original forecasts and frozen splits stay unchanged; protected labels stay excluded. |
| Restart, idempotency, failures and offline recovery | `test_weather_labels.py`, `test_weather_labels_listener.py`, verified snapshot/restore evidence | **Scoped pass.** Bounded credential-free GETs, persisted partial receipts, terminal refusal batches, active shutdown, interrupted startup without network retry, exact offline label/rule/audit replay and restored download equality. |
| Reproducible realistic empirical modeling/backtests | Existing model/backtest gates and actual browser research result | **Incomplete.** Sparse labels leave all candidates insufficient; no fitted probabilities, fills, return or profitability claim. More dates, temporal validation and certified effective fees remain open. |
| Website, paper/shadow and safety | New browser procedure plus existing operating acceptance below; full regression results in current bundle | Existing website/accounting/alert workflows preserved. No real submissions, credentials, execution activation or risk-limit relaxation. New source receipt work does not certify live trading. |
| Two meaningfully distinct empirically validated market families | Existing weather and optional Bitcoin code/receipts | **Incomplete.** Bitcoin boundaries preserved; no new family selected. Future evidence or another user-approved family is required. |
| Provider-backed research with authorized credentials | Prior controlled integration below | **External verification deferred.** No credential access or external-provider acceptance claimed. |
| Quality, install and independent release review | Current execution bundle; prior locked operating acceptance below | **Pass:** Ruff/format and strict mypy (542 files), all **1,255 pytest cases in 609.09s**, 22 frontend checks and actual Chromium acceptance (7 screenshots, 6 downloads, 0 page errors). Offline authentic restore/reparse and all 73 original safety/boundary hashes verify. Large generated trace/archive bytes remain local with checksummed retention evidence. No new clean-install pass is claimed. Independent milestone review and all remaining V1 gates remain required. |

# Private-workbench operating acceptance — October 31, 2026

**complete=false. Private-workbench operating acceptance is verified; V1 remains incomplete.**
All six browser procedures and all **1,210 pytest tests in 644.82s** pass in a fresh locked
installation, with zero failures/errors/skips. Final artifact/source/restore verification
passes. These software and operating results are not independent V1 release approval.
The [current bundle](../data/operating-acceptance-review/20261031-permitted-serial/README.md)
retains actual page interactions, reports, screenshots, downloads and traces. Work remains
on designated `supervisor/20261031-033238` from `2f8d9ad`; all Git mutations and independent
sign-off belong to the supervisor. Earlier failed attempts remain failed.

Checkpoint retention correction: [local artifact policy and limitations](../data/operating-acceptance-review/ARTIFACT_RETENTION.md)
and the [hash manifest](../data/operating-acceptance-review/local-artifacts-20261031.json)
retain 1,096 generated trace/archive files (261,903,008 bytes) at their original local paths,
excluded from new staging. Reports and historical verification receipts remain in the
reviewable bundle. A checkout alone cannot inspect the local trace bytes or replay their
workspace archives; independent review requires obtaining and hash-verifying those files.
Byte retention verification does not reexecute acceptance or close any V1 gate.

| Requirement | Current executed evidence | Result / remaining work |
|---|---|---|
| Fresh locked installation | Current `acceptance.json`, lock/sync/inventory/npm/Chromium logs | **Pass:** new virtualenv, 117 installed Python packages, pinned npm and supported Playwright-managed Chromium provisioning from offline artifact caches. No existing virtualenv or personal browser reused. |
| Usable private browser research/results | Actual Playwright JSON/JUnit reports, provider/recovery/weather receipts | **Scoped pass:** all six required identities have successful execution records, not just discovery. Research, typed candidates, results/tabs and explicit authentic insufficiency execute through localhost. Hosted operation is outside this check. |
| Continuous paper decisions, source/model/fee versions, quotes, intentions, execution risk and outcomes | Controlled/authentic paper page procedures, actual account/evidence downloads and accounting replay | **Scoped pass:** controlled synthetic accounting has two fills and one settlement; authentic retained receipts have zero fills/fees and explicit missing-model/fee refusals. Simulation is not empirical performance. |
| Operator acknowledgement, recovery and recurrence | Actual alert page clicks, lifecycle downloads, listener restart and offline restore | **Pass in the serial run:** three incidents are acknowledged while remaining open; recovery resolves them; recurrence creates a new unacknowledged incident; restored downloads match. Controlled health/outcome signals remain labelled. |
| Restart, cancellation, offline restore and repeatability | Recovery/provider/paper/alert browser receipts; [final verification](../data/operating-acceptance-review/20261031-permitted-serial/verification.json), retained workspace archives | **Scoped pass:** all 43 download hashes, 26 screenshots, six intact traces and 19 identical download comparisons verify. Actual listeners restart, cancelled/interrupted jobs remain durable and restored alerts/paused monitors retain their evidence. Both actual paper browser workspaces also restore offline with identical exports and account replay. |
| Provenance, point-in-time clocks, leakage checks and frozen holdouts | [Source verification](../data/operating-acceptance-review/20261031-permitted-serial/source-verification.json), [safety hashes](../data/operating-acceptance-review/20261031-permitted-serial/safety-receipt.json), temporal/risk tests and final archives | **Scoped pass:** all 1,578 checkout/install source/input hashes, 68 original receipt hashes and five Bitcoin boundary hashes match. Final archives retain fresh authentic receipt bytes and original clocks. Existing holdout/source/settlement protections are unchanged; authentic empirical evidence and independent leakage review remain open. |
| Deterministic backtests and realistic accounting | Existing shared deterministic engines and controlled browser/pytest evidence | **Software capability retained; empirical gate incomplete.** Authentic history lacks enough source-matched labels/models and certified effective fees. A synthetic result cannot pass this gate. |
| Two materially distinct empirically supported families | Existing weather and optional Bitcoin forward paths | **Incomplete:** preserve authentic forward receipts and frozen Bitcoin windows. Another major family needs user approval; blocked paths do not count as supported empirical families. |
| Provider research using separately authorized credentials | Controlled provider HTTP browser integration and missing-key refusal | **External verification deferred:** no real credential or external-provider session used. Controlled responses do not satisfy the external-provider gate. |
| Complete quality gates | Fresh Ruff/format, strict mypy, frontend, [full pytest log](../data/operating-acceptance-review/20261031-permitted-serial/pytest.log) and JUnit; additional driver/JS checks | **Pass:** backend/driver Ruff and format, strict mypy (535 files), 22 frontend checks, JS syntax and all **1,210 pytest cases in 644.82s**, zero failures/errors/skips. The full driver completes with `acceptance_complete=true`. |
| Safety and operating limitations | Disabled submission catalog/export checks, existing credential/risk boundaries and retained failure reports | **Scoped pass:** localhost only, credential-free acceptance environment, no real orders or live activation, unchanged risk limits. Earlier native crash/timeout attempts remain failed; the final serial run passes without reproducing the native crash. Its underlying cause is not established; run acceptance sequentially. |
| Independent release acceptance | This matrix, actual code, complete reports and durable evidence | **Pending:** supervisor must independently audit the executed evidence and every remaining V1 gate. No release completion, empirical returns or profitability claim. |
| Generated evidence retention / checkpoint size | [Local byte manifest](../data/operating-acceptance-review/local-artifacts-20261031.json), verifier and scoped ignore policy | **Local retention verified:** all four attempts preserve original statuses and trace/archive bytes. Large generated bytes are local only; independent inspection/restore from a fresh checkout requires separately obtaining them. No evidence deletion, tracked-file migration, safety-gate relaxation or supervisor checkpoint is performed. |

## Previous provider deadline debugging correction — October 31, 2026

**complete=false.** The [current correction evidence](../data/debugging-review/20261031-provider-deadline/README.md)
reproduces the reported `assert calls` failure with a controlled slow agent setup and
repairs the timing-dependent HTTP fixture without changing production deadlines or risk
limits. Separate regressions require actual timeout cancellation during HTTP and zero
requests on real startup expiry, unchanged failed-review recovery bytes and a released
worker guard. Ruff/format, strict mypy, 64 focused pytest cases and 22 named frontend checks
pass. The [complete suite](../data/debugging-review/20261031-provider-deadline/full-suite.log)
passes **1,210 tests in 532.60s**, with no failures or skips, including all deadline
regressions. This closes the reported verification failure for this correction's source.

The existing controlled provider procedure now executes in managed Chromium through a real
localhost listener using the supported approval path: 8 screenshots, 14 hash-verified
downloads, cancellation/restart and zero page errors. The [execution-report check](../data/debugging-review/20261031-provider-deadline/browser-verification.json)
requires its exact identity and successful result records. It explicitly records the other
five required procedures as missing; this scoped pass cannot complete operating acceptance.
There is no fresh-install or external-provider pass and no new authentic model/fee/two-family
evidence. All 68 original receipts and five Bitcoin boundary files remain byte-identical.
Independent release review and all remaining V1 requirements stay open. No Git operations
or real orders are performed. The following matrix retains its earlier execution scope.

# Prior private-workbench operating acceptance — October 31, 2026

**complete=false. Operating acceptance is externally blocked.** Implementation/checks are
on designated `supervisor/20261031-014049` from `b8d2538`; all Git operations and independent
release review belong to the supervisor. The [current bundle](../data/operating-acceptance-review/20261031/README.md)
retains fresh locked-install results, exact failed export checks and their repairs, source
hashes, focused tests and offline recovery evidence. Earlier matrices retain their original
checkout scope. No historical browser pass certifies the current website.

The [report-gate correction](../data/operating-acceptance-review/20261031/report-gate-correction/README.md)
requires discovery of all six fixed browser procedure identities and parses both discovery
and execution JSON reports. Completion requires actual passing result records for every
procedure, matching selection and aggregate counts. Absent, malformed, skipped, failed or
empty execution results fail despite a zero process exit. A successful narrowed
`--browser-grep` run is explicitly partial and keeps `acceptance_complete=false`.
These parser/orchestration regressions and actual `--list` checks do not execute pages or
close any outstanding browser, complete-suite or V1 requirement. Existing evidence is retained.

| Requirement | Current executed evidence | Result / remaining work |
|---|---|---|
| Reproducible fresh installation | [Final driver receipt](../data/operating-acceptance-review/20261031/locked-reviewed/acceptance.json), lock/sync/package/npm/Chromium logs | **Scoped preparation passes.** New environment, offline package artifacts, 117 Python packages, pinned npm install and Playwright-managed Chromium provisioning; no reused virtualenv or personal browser. `acceptance_complete=false`; preparation is not operating acceptance. |
| Private browser research → typed hypotheses → experiments/results | Six selected procedures in [actual discovery](../data/operating-acceptance-review/20261031/locked-reviewed/browser-discovery.log) | **Current page workflows unexecuted.** Research/recovery, controlled provider and authentic weather remain selected alongside both paper procedures and alerts. Discovery is not page interaction. Run all six through actual localhost listeners in a permitted environment. |
| Durable paper decisions, predictions, source versions, quotes, intentions, execution risk and subsequent outcomes | Fresh focused account/collector/risk/replay checks; [offline paper exports and verification](../data/operating-acceptance-review/20261031/offline/receipt.json) | **Scoped offline checks pass.** Both exports reproduce, reopen and restore identically. Controlled account has two synthetic fills and one settlement. Authentic original-receipt account has zero fills/fees and explicit missing-model/fee refusals. No empirical accuracy, returns or profitability is established. Browser accounting inspection/downloads remain unexecuted. |
| Operator acknowledgement, recovery and recurrence | Fresh alert tests; [offline lifecycle receipt](../data/operating-acceptance-review/20261031/offline/receipt.json), executable `alerts.spec.cjs` | **Scoped offline checks pass.** Idempotent acknowledgement survives reopen; recovery resolves three acknowledged incidents; recurrence gets a new incident requiring acknowledgement; restored exports match. Browser acknowledgement and presentation remain unexecuted. Controlled health/outcome signals cannot certify authentic collection. |
| Restart, cancellation, offline restore and identical downloads | Fresh recovery/worker/account tests and offline export/archive comparisons; existing recovery/paper/alerts browser procedures | **Offline/restart software evidence passes; browser gate blocked.** Store reopen and offline restore preserve exact canonical export bytes. This does not verify browser downloads, real-listener restarts or page-driven cancellation. Retain screenshots and compare actual downloaded bytes when the six procedures can execute. |
| Source clocks, provenance, leakage checks and protected holdouts | [Safety receipt](../data/operating-acceptance-review/20261031/safety-receipt.json), frozen 1,578-member source export, focused risk/temporal/recovery tests | **Scoped checks pass.** All 68 original receipt files and five Bitcoin boundary implementation/manifest files match prior hashes. Export repairs copy original bytes, including saved results/decisions and the v1 account fixture; they do not backdate data or invent audit fields. Final independent leakage review and authentic empirical evidence remain required. |
| Deterministic backtests and realistic accounting | Existing deterministic engines plus fresh fee/execution/risk/account replay tests | **Software capability retained; empirical gate incomplete.** Missing authentic models/labels, certified effective fees and validation history remain explicit blockers. Controlled fixtures do not count as empirical backtests. |
| Two meaningfully distinct supported empirically validated families | Existing weather and optional Bitcoin forward paths | **Incomplete.** No new family selected. Keep authentic forward collection and frozen Bitcoin validation windows; another major family requires user approval. Blocked paths do not count as supported empirical families. |
| Provider-backed research using separately authorized credentials | Existing controlled provider browser procedure is selected/discovered | **External verification remains blocked/deferred.** No credentials accessed and no actual external-provider session attempted. Controlled provider responses and test discovery cannot satisfy this gate. |
| Ruff/format, strict mypy, frontend and complete pytest | Final locked-install logs, [fresh focused run](../data/operating-acceptance-review/20261031/focused-reviewed.log) and JUnit | **Independent quality checks pass:** backend/driver Ruff and format, strict mypy (535 files), 22 frontend checks and **394 focused pytest cases in 40.52s**, zero failures/skips. **Complete suite unexecuted here.** Existing localhost/asyncio socket denial persists; the prior collector stall is not repeated. Focused success never substitutes for a complete-suite pass. |
| Safety, credential boundaries and independent V1 release | Current capability blocker and safety receipts; existing submission/risk tests | **V1 incomplete.** No orders, live activation, credentials, raised risk limits, new family, changed original clocks, force-push or other Git mutation. Independent supervisor review must cross-check code, executed evidence and every remaining release requirement. |

The [current OS probe](../data/operating-acceptance-review/20261031/environment-blockers.json)
returns `PermissionError(1, 'Operation not permitted')` for localhost socket creation and
`socketpair()`. No new Chromium launch or complete-suite retry is made after confirming the
same restriction. The driver now checks these capabilities before dependent execution and
records blocked/unexecuted gates; browser execution stops after its first failure.

Outstanding operator/supervisor acceptance: in an environment permitting localhost sockets,
asyncio socketpairs and managed Chromium, run `python3 tools/local_acceptance.py --output
data/operating-acceptance-review/NEW-NAME` without `--prepare-only`. Require the complete
pytest suite plus all six real-browser procedures, page acknowledgement, recovery/recurrence,
actual restart, offline restore, identical downloads and retained screenshots/traces. Stop
retrying this restricted environment. External-provider, authentic empirical/model/fee and
two-family release evidence remain independently open.

# Historical paper-accounting evidence — October 31, 2026

**complete=false.** Durable simulated paper accounting is implemented as an intermediate
milestone, separately from observed evidence. See [the operating guide](paper-accounting.md)
and [executed evidence](../data/paper-accounting-review/20261031/README.md). Controlled cases
prove causal execution, liquidity non-reuse, fee transitions, risk caps, restart/recovery,
duplicate settlement and offline accounting; they remain synthetic. Authentic receipts
still refuse for missing models/fees. Managed Chromium installation succeeded but browser
launch was denied before page interaction; screenshots, browser downloads and the new
localhost UI workflow are **not verified**. Full-suite socket/listener gaps also remain open.
Existing earlier browser acceptance is historical and does not certify this changed website.
No clean-install or final empirical/provider/release gate is promoted to passed.

# Historical research-cohort evidence — October 30, 2026

## Intermediate fee-evidence milestone — October 30, 2026

**V1 is incomplete.** This milestone adds immutable source/fee versions, causal
selection/refusal, fee-inclusive durable reservations, portable experiment replay and browser
provenance/downloads. Separate CONTROLLED intentions and authentic original-receipt refusal
procedures use managed Chromium and actual localhost listeners. Authentic research still
produces no fitted probabilities, backtest scenarios or profit claims. The official fee
PDF's fresh HTTP 429 response is retained; no authentic schedule is certified. Exact executed
checks and limitations are in [the milestone evidence](../data/fee-evidence-review/20261030/README.md)
and [operating guide](fee-evidence.md). Earlier dated verification below remains historical.
No release requirement is silently promoted to passed; independent final review is required.


**complete=false.** This is a substantial intermediate milestone; independent supervisor
review and the remaining empirical release requirements are still required.

| Requirement | Executed evidence | Result / remaining work |
|---|---|---|
| Multi-partition research through the website | `weather/cohorts.py`, cohort API/forms, [three-procedure browser harness](../frontend/browser/shadow-history.spec.cjs), [current bundle](../data/research-cohort-review/20261030/README.md) | Controlled sufficient-data cohort and both previously outstanding shadow-history procedures pass actual managed Chromium/localhost interaction, all result tabs, downloads and offline restore. Independent review remains pending. |
| Point-in-time source lineage, event counts and frozen boundaries | Cohort/batch manifests and controlled 130-capture regression | 200 independent city/day events across 100 dates; duplicate decisions do not inflate counts. Shared 48/12/30-day calendar, inherited source/model protections and 20 excluded holdout events persist. Protected labels cannot enter bias/fitting/evaluation. Original authentic clocks/bytes remain intact. |
| Deterministic fit, calibration, evaluation and honest execution refusal | `test_weather_cohorts.py`, actual listener/ordinary-worker test, controlled cohort browser downloads | Default minimums admit controlled fitting/Platt calibration/validation; independent model outputs reproduce prediction bytes. Missing labels/protected overlap refuse correctly. Missing sized depth/fees still refuse trading backtests. **Controlled software evidence only.** |
| Bounded work, restart and durable recovery | Immutable 128-input batch snapshots, eight-partition limit, unchanged 256 MB raw-input budget; interruption/restore regressions | Completed batches survive interrupted assembly. Cohort identities and review/report/shadow-input downloads remain identical after offline restore. Existing shadow risk/submission and forward-prediction boundaries remain. |
| Authentic modeling and empirical two-family release | Original retained receipts; existing optional Bitcoin path | **Incomplete:** four authentic weather events on two dates, zero matched scalar highs, zero authentic fitted probabilities/returns. Bitcoin boundaries remain frozen; no family selected. No fabricated historical receipts or profitability claim. |
| Quality, credentials and release review | [Final verification](../data/research-cohort-review/20261030/verification.json); existing credential/risk tests | 1,083 pytest passes in 563.76s, Ruff/format, strict mypy, 21 frontend assertions and three real Chromium procedures pass. 18 screenshots/18 downloads, zero page errors; source/original receipt hashes unchanged. Existing installation reused; no fresh clean-install or authorized external-provider pass claimed. Certified fees, sufficient authentic fitting/evaluation, empirical two-family evidence and independent V1 review remain open. |

The following matrices retain their historical checkout scope, including the earlier
sandbox-denied browser attempt. That attempt is superseded by the executed procedures
above, without changing sandbox policy or browser launch flags.

# Historical sustained-history evidence — October 30, 2026

**complete=false.** This is an intermediate implementation record, not independent release
approval. All Git operations and acceptance sign-off belong to the supervisor.

| Requirement | Evidence | Current result / remaining work |
|---|---|---|
| Sustained history without truncation or boundary movement | `tracking/history.py`, `weather/history.py`, `test_shadow_history.py` | CONTROLLED 130 collector/store cycles, partitions 128+2, later partition first, restart and offline restore are exercised. Original receipts remain. Global anchor and calendar/model protections persist. |
| Causal books, source versions, labels and deterministic replay | Source-binding/tampering regressions; saved shadow replay and projected `ExperimentData` | Replay and raw source/book verification are separate. Exact clocks/books/source and prediction versions persist. Forward predictions stay forward. Later binary receipts do not invent scalar highs; protected labels stay excluded. |
| Research/inspection/downloads through the website | [Browser harness](../frontend/browser/shadow-history.spec.cjs), [evidence bundle](../data/shadow-history-review/20261030/README.md), real-listener integration | **Browser acceptance outstanding.** Installation succeeded; one Chromium launch was denied (`setsockopt: Operation not permitted`, SIGTRAP). No page interaction or screenshots passed. Both procedures must run in a permitted environment. Listener tests are separately classified software evidence. |
| Missing labels, stale depth, certified fees and risk boundaries | Controlled experiment refusal tests and unchanged risk/execution suite | No forward-to-validation promotion, fabricated label, fee substitution, live execution or risk-limit change. Authentic retained weather remains insufficient; no empirical return is claimed. |
| Full quality and durable artifacts | [Current verification](../data/shadow-history-review/20261030/verification.json) | **1,073 pytest passes**, Ruff/format, strict mypy and 21 named frontend assertions pass; final source and original receipts are unchanged. Browser acceptance remains outstanding. Existing environment reused; no new clean installation or independent approval claimed. |
| Final real-data release | Earlier empirical/source/provider requirements below | **Incomplete.** Source-matched fitting and realistic empirical validation, certified effective fees, authorized external provider verification and two-family release evidence remain open. New-family selection is deferred pending user approval. |

The following October 30/29 matrices are historical. Their browser and quality passes apply
to those original checkouts, not the current sustained-history implementation.

# V1 acceptance evidence — October 30, 2026

**complete=false.** This milestone implements retained weather history through the
browser on the designated branch. All Git operations and independent sign-off remain
with the supervisor. No real-money orders, new family or credential access occurred.
External-provider verification is deferred until separately authorized credentials.

| Requirement | Current milestone evidence | Result / remaining work |
|---|---|---|
| Browser receipt ingestion → dataset selection → research/backtest → downloadable results | [Managed Chromium harness](../frontend/browser/weather-history.spec.cjs), [current browser receipt](../data/weather-history-review/20261030/browser-committed/weather-browser-receipt.json), [guide](weather-history.md) | **Scoped authentic-receipt workflow passes.** Ordinary localhost/worker, explicit dataset selection, all tabs, downloads and restart execute. This replays original authentic captures; no new acquisition or empirical performance is implied. |
| Immutable datasets, provenance and deterministic replay | `weather/history.py`, `data/dataset.py`, archive exports and feature pipeline; `test_weather_history.py` | **Scoped checks pass.** Reversed/duplicate input replay is identical; checksums, publication/staging recovery, revision conflicts, first receipt clocks and original acquisition failures are preserved. 4 events, 2 dates, 24 contracts, 48 decisions and 648 observations replace dependence on the legacy six-event sample. |
| Source-matched labels, known-at-time fitting and holdout protection | Existing `verified_targets`/`_examples`; retained fixed partitions; controlled scalar/binary receipt and overnight regressions | **Software checks pass; empirical gate incomplete.** Wrong-source highs cannot substitute; binary outcomes cannot invent scalar labels. Corrections require their original availability; fitting uses timely labels. Fixed 48/12/30-day calendar membership and inherited protections persist across snapshots; protected labels cannot enter bias features. Authentic scalar highs remain absent. |
| Deterministic experiments and realistic accounting | Existing research/StrategySpec/model/R4 engine; authentic browser insufficiency; separately labelled synthetic fitting regression | **Integrated refusal path passes.** Authentic samples yield no fitted probabilities, scenarios, fills or performance claims. Existing minimums, fee/depth/risk gates stay enforced. Sufficient empirical fitting/backtests and certified effective fees remain open. |
| Durable restart, cancellation and offline restore | `test_weather_history_listener.py`, browser downloads/restart; recovery snapshot validation | **Scoped checks pass.** Frozen dataset references, interrupted/cancelled requests and completed result bytes persist; offline restore includes verified snapshots. Broader pre-existing shadow/provider recovery remains covered by the suite. |
| Two meaningfully distinct empirically validated families | Existing weather and optional Bitcoin adapters | **Incomplete.** No family selected; Bitcoin dates remain frozen. Authentic forward ingestion and synthetic fitting do not satisfy empirical two-family validation. |
| Provider-backed research with authorized research credentials | Prior controlled provider integration and pricing evidence below | **Deferred external verification.** No credentials accessed. Existing server configuration, explicit per-run consent and credential isolation remain enforced. |
| Required quality gates and browser artifacts | [Current evidence bundle](../data/weather-history-review/20261030/README.md) | **Pass:** Ruff/format (514 files), strict mypy (511 files), all **1,058 pytest tests in 353.35s**, 18 frontend cases and the actual Chromium procedure (5 screenshots, 4 downloads, zero page errors). Actual managed-Chromium screenshots/downloads are distinct from controlled/unit checks. The existing environment is reused; no new clean-install pass is claimed. |
| Safety and release review | Existing submission boundary and risk tests; unchanged Bitcoin/family/credential boundaries | **V1 incomplete.** No live execution or risk cap changes. Independent supervisor review and a final verified release matrix remain required. |

The prior evidence below remains historical and keeps its original scope and limitations.

# Historical V1 evidence — October 29, 2026

**complete=false.** The current milestone connects provider-backed research to the existing
private website. This matrix records scoped software and operating evidence; it is not
independent release approval. All Git operations and final review belong to the supervisor.
No real credentials, external provider session, real orders or new family were used.

The [current evidence bundle](../data/provider-review/20261029/README.md) contains a fresh
locked installation, source fingerprints, test reports, Playwright-managed Chromium
screenshots/traces/downloads and offline provider/recovery snapshots. Controlled OpenAI
HTTP responses verify software integration; they never count as an external provider pass.
The unmodified server also demonstrates a missing research key with zero provider requests.
Earlier evidence retains its original code, timestamps and limitations.

| Requirement | Evidence | Result and remaining work |
|---|---|---|
| Private usable website: prompt → multiple typed hypotheses → deterministic experiments → results/downloads | `api/server.py`, `jobs.py`, `worker.py`; [provider browser harness](../frontend/browser/provider.spec.cjs), [current receipts](../data/provider-review/20261029/locked-final/browser/provider-browser-receipt.json) | **Scoped browser workflow passes.** Real localhost/page interaction exercises explicit consent, three typed hypotheses using controlled provider HTTP, deterministic real-data insufficiency, all tabs and identical downloads after restart. Synthetic probabilities remain labeled software evidence. Real external-provider reasoning remains separately blocked. |
| Two meaningfully distinct supported families with concrete real-data paths and realistic validation | Existing weather capture and [optional Bitcoin history](bitcoin-history.md) | **Incomplete.** Authentic forward paths exist; neither missing historical source-matched weather fitting/outcomes nor insufficient Bitcoin validation counts as a supported empirical family. Bitcoin's four retained fitting events on three dates, one class and future validation dates remain unchanged. No replacement family selected. |
| Source clocks, as-of joins, leakage checks and protected holdouts | `agents/evidence.py`, `experiments/workflow.py`, existing feature/model/tracking protections; temporal tests and retained source artifacts | **Scoped software checks pass.** Research tools expose permitted projections without outcomes; deterministic gates keep protected events excluded. Provider reviews preserve source/model identities, prompt hashes, run clocks and tool receipts. Actual forward collections never backfill historical availability. Final independent leakage audit and sufficient empirical history remain open. |
| Deterministic reproducible backtests and realistic accounting | Existing R4 experiment/backtest, execution/fee and risk engines; complete-suite regression evidence; browser synthetic workflow | **Software capability present; empirical gate incomplete.** Typed candidates use the same model/fee/depth/chronology/risk gates. Real recorded weather remains insufficient; no real fitted probability, empirical return or profitable strategy is claimed. Effective fees remain uncertified. |
| Provider-backed bounded research with separately authorized credentials | `agents/provider.py`, `pipeline.py`, `api/runner.py`; controlled serialization/job/browser tests; [external check receipt](../data/provider-review/20261029/external-provider-check.json) | **Website integration passes controlled checks; external check BLOCKED.** Operator provider/model configuration plus fresh per-job consent are required. Public configuration is frozen; only opted-in workers receive the dedicated research key. Existing request/tool/token/cost/deadline limits remain. Missing credentials, outages, malformed output and deadlines yield saved failures without experiments or mock fallback. A separately authorized actual provider session remains required. |
| Durable continuous shadow decisions, versions, quotes, intended orders, risk checks and outcomes | Existing tracking store/worker/replay; [current recovery browser receipt](../data/provider-review/20261029/locked-final/browser/recovery-browser-receipt.json), retained workspace archive | **Scoped operating workflow passes.** Browser inspection, pause/resume, interruption, restore, fresh authentic collection and subsequent cancellation/restart execute. Actual model/fee blockers leave intentions absent; eligible reservations/outcome release remain controlled evidence. Zero real submissions/fills; no performance claim. |
| Restart, cancellation and offline recovery | [Provider offline verification](../data/provider-review/20261029/provider-offline-verification.json); browser receipts; existing workspace leases and restore checks | **Scoped checks pass.** Provider snapshot/restore preserves 56 files and logical jobs/registry rows across completed, failed, cancelled and interrupted jobs. Pending opted-in jobs recover as interrupted without automatic billable retries. Existing source/worker lease, frozen binding, reservation and original-receipt protections remain. Broader browser recovery also passes. |
| Safety and credential boundaries | Same-origin/CSRF, request allowlists, worker environment tests, existing submission/risk boundaries | **Scoped checks pass.** Browser requests cannot carry keys, provider URLs, code or model paths. Ambient SDK/exchange keys and HOME do not enter workers; ordinary and shadow workers remain credential-free. Synthetic/provider combinations are refused. No risk limits, execution activation, holdout dates or settlement semantics changed. Final independent review remains necessary. |
| Locked install and complete tests | [Locked setup/browser receipt](../data/provider-review/20261029/locked-final/acceptance.json), [completed suite](../data/provider-review/20261029/complete-suite/receipt.json), [aggregate verification](../data/provider-review/20261029/verification.json) | **Scoped pass after documented export repair.** Fresh offline locked Python/npm setup uses package artifacts and managed Chromium, never an existing virtualenv. Ruff/format, strict mypy (505 files), 15 frontend cases, both real-browser procedures and all 1,033 pytest cases pass. Two original vendored citation documents were added before the final complete-suite rerun; application/test/fee code stayed unchanged. Earlier failed driver reports remain failed, not rewritten. |
| Repeatable operation and limitations | [Workbench](workbench.md), [agent research](agent-research.md), [recovery](local-recovery.md), [roadmap](roadmap.md) and executable locked acceptance driver | **Documented.** Loopback single-user operation; keys require separate authorized setup. Provider cost can be unknown for the first request; unknown cost stops further requests. Cancellation cannot undo an already issued provider charge. Hosted operation, broader serializers/depth scheduling and structural scanning remain deferred. |
| Independent final release acceptance | This matrix plus final code and durable evidence | **Pending.** Supervisor must independently cross-check the actual browser/test/source artifacts and all empirical requirements. Controlled/synthetic or blocked paths cannot satisfy real-data release requirements. |

Full suite: **1,033 passed in 373.42 seconds; zero failures, errors or skips**. The final source/input fingerprint comparison and
exact browser/test counts are retained in the current bundle: 11 screenshots, 19 browser downloads, zero page errors; all 1,474 source/input hashes match checkout and installation. No final release completion
is implied by a complete software suite or a successful recovery workflow.

The retained collector timeout is diagnosed without changing the collector or its test:
sandbox socketpair sends fail with `EPERM`, preventing asyncio executor wakeups; the
credential-free diagnostic and unchanged reconnect test pass through normal approved
execution. The first clean-export attempt additionally omitted existing `data/public`
fixtures and research documents, and used a TMPDIR too long for Chromium's Unix sockets.
The driver now copies the original required inputs, including the exact two vendored fee references used by the old tests, and allocates a short temporary root.
Original denial, timeout, missing-file and browser-crash receipts remain preserved.

Return this substantial intermediate milestone for supervisor review. The next provider
acceptance task, only after separate credential authorization, is one bounded actual
provider-backed website run with typed outputs or an honest saved provider failure,
downloads, source/holdout evidence and recorded cost/usage. Authentic fitting/outcomes,
certified fees, empirical two-family validation and independent V1 review remain open;
no frozen Bitcoin boundary may be moved to satisfy them.
