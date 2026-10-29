# EntropyTrade project context

Updated 2026-10-29. **V1 remains incomplete.** The current milestone connects frozen
models to continuous read-only shadow collection using existing families. Implement and
test on the designated supervisor branch; all branch/commit/merge/push operations belong
to the supervisor. No credential access, real-money orders or submission activation.

## Product direction and current checkout

EntropyTrade is a general Kalshi research, modeling, reproducible backtesting and
paper/shadow platform. Weather was first. Preserve the existing Bitcoin implementation
and original receipt clocks, but do not wait for unavailable Bitcoin validation windows
before completing independent functionality. Forward authentic collection is preferred
to reconstructing historical availability. A new major market family requires user
approval after comparing accessible point-in-time history, resolution semantics, modeling
feasibility, execution costs and realistic validation.

This implementation uses designated `supervisor/20261029-120832`, based on `e8b7402`.
The existing R4 experiment workflow, local website, Bitcoin history and continuous shadow
foundation were already present; they were extended rather than rebuilt. Earlier bundles
retain their original commits, evidence and limitations. No remote freshness is implied.

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

## Executed evidence and honest limitations

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
| Integrated research/backtesting | R4 CLI and local website connect typed proposals and deterministic experiments. Real weather history remains insufficient; synthetic fits/replays verify software only. Provider-backed research remains opt-in and externally unverified without authorized research credentials. |
| Private website | Local research jobs/results, cancellation, history, shadow inspection and durable downloads exist. Current shadow browser lifecycle is executed; clean-install release evidence remains separate. |
| Two real-data families | Existing weather and Bitcoin source/history paths remain. Two fully supported empirical families are not established. No new family is selected. |
| Continuous shadow | Durable collection/control/replay/outcome linkage and frozen compatible weather scoring are implemented. Actual collected candidates lack fitted real models; uncertified fees still block intentions. |
| V1 release | **Incomplete.** No independently verified final acceptance matrix, full empirical gate or current clean-install release proof. |

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

Return this sizeable integration for supervisor review before another major milestone.
The highest-impact next gap is sufficient authentic source-matched fitting evidence plus
reviewed effective fee evidence; continue independent release/operating work while data
accrues. Ridge/boosting data-only scoring, Bitcoin scoring, broader depth scheduling,
final-outcome corrections and hosted operation remain explicit limitations, not approvals.
Before setting V1 complete, the supervisor must commit and independently cross-check
`docs/v1_acceptance.md` against actual code, executed checks and durable real-data/browser
proof. A blocked path or synthetic-only fit cannot satisfy a real-data requirement.
