# EntropyTrade — current status

Updated 2026-10-31. R0 `c7ad278`, R1 `e2c1448`, R2 `b9cbaa8` and R3 `624d442`
remain recoverable on their original branches. R3 was integrated into main before R4.

## Current milestone: durable simulated paper accounting in continuous shadow

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
