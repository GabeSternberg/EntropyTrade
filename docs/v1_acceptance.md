# Provider deadline debugging correction — October 31, 2026

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
