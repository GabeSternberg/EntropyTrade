# EntropyTrade project context

Updated 2026-10-31. **V1 remains incomplete.** Current implementation: bounded immutable label
partitions on designated `supervisor/20261031-073225` from `b62f9c6`. Git operations and
independent review belong to the supervisor. No Git mutations, supervisor-control changes,
new family, credentials or real execution.

Opted-in continuous read-only schedules now continue beyond 128 total requests. Each bounded
partition holds at most 128 requests; a chained immutable seal retains exact original request/
batch hashes. Existing flat files are the first partition and remain in place. Requests wait
for unfinished work before rollover, retain the same durable plan through backpressure and
crash recovery, and never refetch an archived request ID. Website selection/downloads,
snapshot construction, retained-input following, cohorts and offline restore include archived
partitions. Original source clocks, calendar boundaries and protected labels stay fixed.

[Operation](docs/label-partitions.md),
[executed evidence](data/label-partition-review/20261031/README.md) and the
[release matrix](docs/v1_acceptance.md) distinguish accelerated controlled rollover checks from
separately identified authentic public receipts. Exact verification results are recorded in
the milestone evidence: repository Ruff/format, strict mypy (551 files), 22 frontend checks,
64 focused tests, 12 integrity/lifecycle checks and all **1,292 pytest cases in 679.34s** pass,
with zero failures/errors/skips. Both final Chromium procedures pass (14 screenshots,
12 downloads, zero page errors), and all 262 controlled label-store files match after restart/
restore. All 73 original receipt/Bitcoin boundary hashes stay unchanged. Authentic acquisition
verifies three station/day highs and refuses one preliminary report at new real receipt clocks.
V1 release acceptance is not implied. Controlled revision requests
do not create independent empirical dates, sufficient history, returns or profitability.
Multi-day authentic reliability remains an observation gate. Snapshot/recovery storage and
schedule target budgets remain bounded and explicit; operators must monitor disk use.

Independent empirical models, certified fees, authorized external-provider verification and
two-family release evidence remain open. Approve safe independent functionality while authentic
data accrues; do not wait for unavailable Bitcoin validation or autonomously select a family.
Previous operating/forward-validation evidence keeps its original scope and bytes.

## Product direction

EntropyTrade is a general Kalshi research, modeling, reproducible backtesting and
paper/shadow platform. Weather was first. Preserve existing Bitcoin work, original
receipt clocks and frozen validation windows. Prefer forward authentic collection;
never fabricate historical availability. Do independent product work while data accrues.
A new major family requires user approval following a comparison of point-in-time history,
resolution semantics, modeling feasibility, costs and realistic validation. None is selected.

## Previous private-workbench operating acceptance

The permitted runtime passes localhost/socketpair checks through the standard approval
path. A new offline locked Python/npm installation and supported managed-Chromium
provisioning pass, followed by Ruff/format, strict mypy (535 files), 22 frontend checks
and all six required browser procedures. Actual page interactions cover research/results,
controlled provider integration, authentic retained weather, both paper accounts, alerts,
cancellation, restart and offline restore. Receipts retain 26 screenshots, 43 downloads
and zero page errors. The complete suite passes **1,210 tests in 644.82s**, with no failures,
errors or skips. Final verification checks all artifact hashes, six intact traces,
19 identical download comparisons, 1,578 checkout/install source hashes, 68 original receipt
hashes and five Bitcoin boundary hashes. **Operating acceptance is verified; V1 remains
incomplete**, with independent supervisor review still required.

Two concrete browser harness failures were repaired without relaxing assertions: reopening
a failed provider run now waits for its exact title and submitted job download URLs;
weather import metadata is staged under the installed repository's data directory before
being copied to the surrounding evidence bundle. Failed reports/traces remain unchanged.
Superseded overlapping verification runs include an acknowledgement timeout, an interrupted
HTTP-timeout suite and a native suite crash; the current execution runs alone and retains
individual pytest case names. It completes without reproducing the native crash, whose
underlying cause is not established. Both actual paper browser workspaces restore offline
with identical exports and account replay. Final recovery/provider/weather archives retain
all stopped workspace evidence, including fresh authentic receipt bytes. See
[current evidence](data/operating-acceptance-review/20261031-permitted-serial/README.md).

Controlled accounting is synthetic; authentic receipts still refuse missing models/fees
and produce zero fills. This work adds no empirical validation, external-provider access,
new family or production submission. Return the verified operating milestone for independent
supervisor review and preserve forward collection/frozen boundaries. The historical sections
below retain their original execution scope; their earlier environment denials do not
describe the current permitted runtime.

## Previous operator-readiness milestone

The website exposes stale-collection, repeated-failure/incompleteness and overdue official
reconciliation incidents across active and paused monitors. Durable acknowledgements record
review without resolving a condition. Healthy collection or subsequent official outcomes
record recovery; recurrence receives a new incident ID. Pause/resume and restart cannot erase
incident history or turn missing models/fees into eligible decisions. Operator clocks remain
separate from receipt, decision and settlement availability clocks. Existing accounts, risk
limits, five-failure pause and disabled submissions remain unchanged.

The background runner and startup evaluate conditions even without page interaction. Exports
and offline workspace recovery retain and validate the incident lifecycle, including legacy
workspace migration. Controlled failure/restart/risk/security checks and authentic blocked-data
inspection execute. Controlled and authentic accounting exports reproduce and restore offline;
all 68 original receipts stay unchanged. See [operation](docs/operator-alerts.md) and
[precise verification evidence](data/operator-readiness-review/20261031/README.md).

Both existing paper Playwright procedures and a new alert lifecycle procedure are executable.
The supported repo-local managed Chromium installation succeeds, but its one launch is denied
at `crashpad/util/linux/socket.cc:45` (`setsockopt: Operation not permitted`, SIGTRAP).
Socket creation is also denied. No retry/bypass or browser/download/restart pass is claimed;
these human acceptance steps require a permitted environment. The complete pytest attempt
stalls in the existing collector reconnect case; bounded diagnostic/all-file results and
separate lint/format/mypy/frontend checks remain explicit in the evidence bundle. Final
focused verification passes 246 pytest cases (including all 11 alert cases), 22 frontend
checks, Ruff/format and strict mypy (534 files). All 228 pytest files are attempted under
deadlines: 211 pass, six fail on socket permission denials and eleven time out. The 130-cycle
history/restart/restore case passes with the other 13 history cases. This is not a
complete-suite pass.

Return this independently useful implementation for supervisor review with those gates open.
Continue authentic forward collection; defer another market-family commitment, empirical
claims and V1 release acceptance. Do not wait for unavailable Bitcoin validation before
reviewing independent paper/shadow capability, and do not start another major phase here.

## Previous research cohorts across retained history partitions

The website can combine up to eight explicitly selected history partitions, with optional
separate later-outcome partitions, into one immutable weather research dataset. Batches
remain limited to 128 inputs; the cohort keeps the 256 MB raw-input budget. Completed
batch snapshots are retained under `runs/weather-datasets/.batches` for restart/retry and
offline recovery. Final assembly reuses frozen receipt copies and rebuilds features jointly
instead of concatenating engineered features or averaging partition metrics.

Global calendar anchoring, inherited source/model protections and the 48/12/30-day
fit/calibration/validation windows remain fixed. Event counts deduplicate city/day events
across repeated captures. Original receipt, decision, forecast-revision and label clocks
remain intact. Protected labels cannot enter fitting/evaluation or bias features. All
existing model minimums, risk, certified-fee and sized-depth gates remain enforced.

CONTROLLED evidence spans 130 captures and 200 events on 100 dates, exercises deterministic
fit/calibration/evaluation, interrupted-batch retry, missing-label/protected-data refusal
and offline restore. This is simulated software evidence, never empirical performance.
Authentic original receipts still have four events on two dates and zero source-matched
scalar highs. Both outstanding shadow-history browser procedures and the new cohort
procedure execute with managed Chromium, actual localhost workers, screenshots and
byte-identical downloads after restore. The previous sandbox launch denial remains
historical evidence; normal supported approval permits this execution without policy
changes. See [current evidence](data/research-cohort-review/20261030/README.md) and
[guide](docs/shadow-history.md). Final gates pass 1,083 pytest tests in 563.76s, Ruff/format
(522 files), strict mypy (519 files), 21 frontend assertions and all three Chromium
procedures (18 screenshots, 18 matching downloads, zero page errors). All 544 frozen
source/configuration hashes and 68 original receipt files remain unchanged.
Current-environment checks do not establish a fresh clean
install, authorized external-provider verification, empirical two-family validation or
an independent V1 release pass. Return for supervisor review; no next phase is started.

## Retained weather history through the browser

The website can freeze immutable, deduplicated snapshots from this workspace's completed
weather public captures and shadow cycles, inspect readiness, select an exact dataset,
submit an idea and download the existing deterministic experiment/insufficiency review.
Retained datasets become the default when present; the static six-event dataset remains
available for legacy reproduction. Original forecast, rule and label availability clocks
are retained. Finalized shadow binary outcomes are source/terms checked and never supply
scalar temperature labels. Original acquisition incompleteness/failures remain visible.

First-snapshot target-date partitions are frozen at 48 days fitting, 12 calibration,
30 validation, then protected holdout. Inherited protections persist; protected scalar
labels cannot leak into prior bias features. Actual next-partition decisions bound labels
available for model fitting/calibration. Existing event/date/model/fee/depth/risk minimums
remain enforced; no real-money execution is introduced. Snapshot publication is atomic,
repeated receipts reuse a content identity, and staging retry/restart/offline restore
preserve completed artifacts and request references. Single partitions are bounded to
128 captures; the cohort extension above retains bounded batches and the 256 MB budget.

Final verification passes **1,058 pytest tests in 353.35 seconds**, Ruff lint/format
(backend/tools, 514 files), strict mypy (511 files), 18 named frontend checks and
actual managed Chromium acceptance (5 screenshots, 4 matching downloads, no page errors).
Authentic browser-workspace offline snapshot/restore also passes. See the
[verification receipt](data/weather-history-review/20261030/verification.json).

Authentic receipt replay proves the browser path with 4 events on 2 dates, 24 contracts,
48 decision rows, 648 observations and zero matched scalar highs. Real fitting/performance
remain insufficient; controlled label/revision/outcome tests and synthetic fitting are
separate software evidence. Actual managed Chromium, localhost workers, downloads and
restart execute. See [current evidence](data/weather-history-review/20261030/README.md),
[guide](docs/weather-history.md) and [V1 matrix](docs/v1_acceptance.md). Current-environment
checks do not constitute a new clean install or independent release review.
Return this milestone for supervisor review. Keep collecting authentic receipts; external
provider verification waits for separately authorized credentials. Bitcoin boundaries,
family selection and the final empirical release gaps remain unchanged.

## Provider research through the private website

The existing four-stage bounded PydanticAI orchestration now runs in isolated durable
website workers: evidence research → 2–6 typed hypotheses → candidate StrategySpecs or
unsupported proposals → independent criticism → deterministic validation and experiments.
Server-side `--research-provider`/`--research-model` configuration and a fresh per-run
checkbox are both required. The exact public provider/model configuration is frozen in
the queued request. The browser cannot submit credentials, URLs, arbitrary code or model
paths. Synthetic mode remains explicitly mock and cannot opt into provider requests.

Only opted-in workers inherit `ENTROPYTRADE_RESEARCH_API_KEY` plus approved proxy/CA
routing settings. Ordinary research and every shadow worker remain credential-free.
Ambient OpenAI/Anthropic/exchange keys and HOME never enter workers. Existing 16-request,
24-tool, token, $2-known-cost and 180-second research limits remain; unknown provider cost
stops further calls. No risk cap, trading gate or protected holdout was changed.

Results expose provider identity, typed hypotheses/specs, deterministic rejections,
permitted probabilities, stage receipts, evidence tools, clocks, budgets, usage and hashes.
Missing research credentials, provider outages, malformed outputs and deadlines save
failed downloadable reviews; they never substitute mock candidates or enter experiments.
Cancellation and shutdown reap the worker; restart marks unfinished jobs interrupted and
requires a new explicit run instead of automatically repeating billable requests. Offline
snapshot/restore now preserves provider configuration and failed-research lineage without
requiring an experiment that never ran.

See [current milestone evidence](data/provider-review/20261029/README.md) and the
[V1 matrix](docs/v1_acceptance.md). Playwright-managed Chromium already passed the new
real-listener provider procedure in development (27.5 seconds): controlled provider HTTP,
three typed hypotheses, deterministic insufficiency, all tabs, downloads, cancellation,
interruption/restart and an unmodified missing-credential worker. Controlled provider
responses are software evidence only, not an external service verification. The locked installation passes Ruff/format, strict mypy (505 files), 15 frontend cases,
both actual Chromium procedures and **1,033 pytest tests in 373.42 seconds**, with zero
failures/errors/skips. Eleven screenshots and nineteen downloads match their receipts.
All 1,474 exported source/input hashes match checkout and installation. The final suite
follows a recorded export-only repair adding two original vendored fee references;
application/tests/fee code stayed unchanged. Earlier omitted-fixture and long-TMPDIR
attempts remain failed receipts. The [aggregate verification](data/provider-review/20261029/verification.json)
links every scope and result. Provider offline restore preserves 56 files and all logical
jobs/registry rows across completed, failed, cancelled and interrupted runs.

## Current model-to-shadow integration

Research candidate → resolved StrategySpec/model identity → immutable data-only weather
model snapshot → fresh public features and sized books → point-in-time probabilities or
explicit refusal → deterministic DSL/risk decisions → persisted cycles → later official
outcome → browser inspection/download and offline replay.

New modeling runs export safe JSON for climatology, raw forecast and forecast-error models,
including supported Platt/isotonic parameters, original artifact hash, fit/calibration clocks,
training series, provenance and protected event boundaries. Monitors bind only a unique,
checksummed server-produced export matching the resolved model reference. Snapshots persist
in SQLite and survive removal of the original run files. No live refitting, pickle loading,
arbitrary model path, promotion or trading activation is exposed. Existing runs without an
export, unsupported models and legacy monitors remain explicitly blocked.

Each cycle makes at most ten exact public book GETs and ten series GETs through fixed
allowlists and existing request/byte/time budgets. YES/NO bids become sized YES books via
the established exchange mapping. Original source availability is retained; the decision
clock follows all book receipts and hours-to-close is recomputed causally. Series fee
fields retain original bytes, receipt clocks, versions and metadata update time, but remain
**uncertified**: they do not establish the fee coefficient or effective interval. No fee
coefficient or fill is invented. The book budget lists deferred contracts explicitly.

The existing conservative fee-inclusive reservation caps, pause/cancellation, failed-cycle
backoff, restart recovery, protected-event union and exact official-outcome reconciliation
remain enforced. Submissions are disabled, fills are empty and performance is null.

## Earlier shadow evidence and honest limitations

See [the integration evidence](data/shadow-review/20261029-model-integration/README.md)
for exact commands, complete-suite and static check results, controlled software fixtures,
source fingerprints and real-browser receipts. The strengthened Playwright-managed
Chromium procedure runs the real localhost listener and workers: research, start, pause,
restart, byte-identical download, resume, second cycle and another download. The retained
real cycles have 24 listed weather contracts, 648 observations, ten sized books, one
uncertified series fee version and 14 deferred contracts per cycle. No source or execution
capture failures occurred. All decisions honestly lack fitted real probabilities and
intentions. Controlled model scoring/risk tests do not establish empirical performance.

Completion verification passes all 971 pytest tests in 275.90 seconds with zero failures
or skips, Ruff lint/format, strict mypy across 496 files and all 12 named frontend cases.
The fresh real-browser lifecycle passes in 21.7 seconds; copied original cycle bytes,
screenshots, trace, downloads and deterministic replay verification are retained under
the evidence bundle's `completion/` directory. No human acceptance step remains for this
scoped browser procedure. A clean-install/final release pass is not claimed.

The first browser attempt exercised the lifecycle but exposed a valid decimal-strike
identifier rejection in both cycles. Its receipts remain intact; the parser was corrected,
a regression added, and the strengthened procedure rerun in a fresh workspace. Historical
socket/Chromium denials remain failures. The current runs use the normal approval mechanism
for a permitted environment, without changing event-loop policies or weakening tests.

## Product gates and remaining work

| Gate | Current evidence-backed capability and gap |
| --- | --- |
| Integrated research/backtesting | R4 CLI and local website connect typed proposals and deterministic experiments. Real weather history remains insufficient; synthetic fits/replays verify software only. Website provider-backed research is opt-in with durable failure/recovery and controlled serialization evidence; external verification remains blocked without separately authorized credentials. |
| Private website | Local research jobs/results, cancellation, history, shadow inspection and durable downloads exist. Current provider and snapshot/restore/shadow workflows have executed locked-install browser evidence, with byte-identical reopened downloads; independent final release review remains separate. |
| Two real-data families | Existing weather and Bitcoin source/history paths remain. Two fully supported empirical families are not established. No new family is selected. |
| Continuous shadow | Durable collection/control/replay/outcome linkage and frozen compatible weather scoring are implemented. Actual collected candidates lack fitted real models; uncertified fees still block intentions. |
| V1 release | **Incomplete.** Scoped locked-install/browser/full-suite proof exists; empirical requirements and independent final matrix/release review remain open. |

The retained Bitcoin snapshot still has four labeled events on three dates, below 40 fit
events on 20 dates with both outcomes. Its fixed validation window is December 24, 2026
through January 23, 2027 exclusive; protected final holdout begins January 23. Validation
needs 20 events on ten dates; ten dates cannot exist before January 2, 2027. These remain
blocked evidence requirements, never backdated or silently waived. Coinbase is a predictor,
not a settlement source. See [original evidence](data/bitcoin-history-review/20261029T001500Z/README.md).

Real historical weather retains six city/day events on three dates with zero eligible
historical forecast/scalar-label pairs. Weather Company settlement cannot be replaced by
NWS CLI; new forward receipts cannot backfill historical decisions. The new book receipts
do not change those historical model-readiness counts.

Return the provider website milestone for supervisor review before another major phase.
External provider verification needs separately authorized research credentials. Continue
independent release work only after review; authentic fitting/source-matched outcomes,
reviewed effective fees and empirical second-family validation remain incomplete. Do not
wait solely for Bitcoin dates or move its frozen boundaries. Hosted operation, broader
model serializers, depth scheduling and structural scanning remain deferred. Before V1
completion the supervisor must independently cross-check `docs/v1_acceptance.md` against
final code, executed tests and durable real-data/browser proof. Blocked and synthetic-only
paths do not satisfy real-data release requirements.
