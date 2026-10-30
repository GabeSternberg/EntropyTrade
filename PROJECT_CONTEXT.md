# EntropyTrade project context

Updated 2026-10-29. **V1 remains incomplete.** The current milestone delivers
provider-backed research through the existing private website and durable jobs. Work stays
on designated `supervisor/20261029-141757`, based on `9dff058`; no Git mutations or
supervisor-control changes. The supervisor owns independent review and all Git operations.
No real credentials were accessed and no external provider was called.

## Product direction

EntropyTrade is a general Kalshi research, modeling, reproducible backtesting and
paper/shadow platform. Weather was first. Preserve existing Bitcoin work, original
receipt clocks and frozen validation windows. Prefer forward authentic collection;
never fabricate historical availability. Do independent product work while data accrues.
A new major family requires user approval following a comparison of point-in-time history,
resolution semantics, modeling feasibility, costs and realistic validation. None is selected.

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
