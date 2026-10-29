# EntropyTrade project context

Updated 2026-10-28 ET / 2026-10-29 UTC. **V1 and second-family empirical acceptance
remain incomplete. Stop for the user's collection/archive decision.** The existing
workflow already reports the missing evidence; further feature abstractions do not
provide elapsed receipt-time history. Continuous paper/shadow and final V1 release
acceptance remain deferred. All Git writes belong to the supervisor. No credential
access, production submission, real-money orders or live execution activation is authorized.

## Verified checkout and scope

This reconciliation started with a clean working tree on `supervisor/20261028-203104`.
HEAD and local `main` both point to supervisor checkpoint
`7f06e11d744500592357a864c3b732b42555dec9`. This is a local comparison, with no remote
freshness claim. R4, the local workbench, executed browser acceptance, retained Bitcoin
history and the latest official-result reconciliation are already present. The older
`30bed8e` R4-only main and October 26 website-review status are historical baselines,
not the current checkout. Original evidence bundles retain their own commits and clocks.

The current instruction supersedes the general Git workflow in `AGENTS.md`: implement
and test only on the designated branch; do not create branches, commit, merge, push or
modify supervisor control files. This reconciliation updates project context and checks
existing evidence. It does not start sustained collection or select an archive for the user.

## Product gates

The user's V1 sequence takes precedence over older numbering in
[the roadmap](docs/roadmap.md), which labels the website R5 and second family R6.

| User-directed gate | Evidence-backed status |
| --- | --- |
| R5: research → typed strategy → model/experiment → honest result | Implemented in R4's `research-and-test` CLI. Real historical weather returns explicit insufficiency. Separate synthetic inputs exercise fitting, calibration and realistic deterministic replay; no empirical advantage is established. |
| R6: minimal private web interface and jobs | Implemented: localhost-only workbench, bounded jobs/progress/history, protected result tabs and downloads. Executed Chromium evidence covers results, public capture success/failure, cancellation, worker reuse and restart persistence. Independent supervisor review and release clean-install evidence remain required. |
| R7: second materially distinct family | The Bitcoin history workflow connects original Kalshi rules/Coinbase predictor receipts, later finalized official binary outcomes, typed local proposals, fixed probability models and shared experiments. Four real labeled events are retained. Actual browser interaction verifies visible insufficiency and durable results. Fitted real-data model/baseline evaluation is still blocked by sparse history and future validation dates. Real mentions ingestion is absent. |
| R8: continuous paper/shadow tracking | Not delivered as an integrated continuous workflow. Existing paper execution/ledger primitives do not satisfy this gate. Deferred. |
| V1 complete | **No.** Second-family empirical evaluation, integrated paper/shadow, clean-install release evidence and the independently verified final acceptance matrix remain open. No real strategy is approved or validated. |

R3's provider-backed research is implemented behind explicit opt-in and separate research
credentials; external provider execution remains unverified here. The website's local
typed proposal templates do not establish provider-backed research acceptance.

## Current second-family evidence

The [latest real-data bundle](data/bitcoin-history-review/20261029T001500Z/README.md)
records four successful exact public official-result GETs. All four are finalized NO
with matching binary payouts, settlement clocks, event/strike identity and recognized
contract terms. Their labels became available at the original October 29 HTTP receipt
times, not at earlier settlement times. All eight original workbench capture directories
still deduplicate to four events across three target dates. A separate one-shot public
source probe succeeded with three HTTP 200 receipts, 318 contracts and one spot observation;
its three pending forward samples are not part of the four-label evaluation snapshot.

The [immutable snapshot](data/bitcoin-history-review/20261029T001500Z/real-all-captures/history/manifest.json)
preserves these calendar boundaries:

| Partition or evidence gate | Fixed requirement and observed evidence |
| --- | --- |
| Fitting | Target dates October 25–December 23, 2026; finalized labels received by December 24, 00:00 UTC. **4/40 events on 3/20 dates**, short 36 events and 17 dates; only NO outcomes, with both YES and NO required. |
| Validation | December 24, 2026 inclusive through January 23, 2027 exclusive. **0/20 events on 0/10 dates**, with no validation labels. Ten validation dates cannot exist before **January 2, 2027**; this is a calendar lower bound, not a completion promise. |
| Protected final holdout | Target dates from January 23, 2027. Excluded from research, fitting, evaluation and browser projections. |
| Deterministic evaluation | Two independent real-input replays retain the same experiment identity and serialized results: two `INSUFFICIENT_DATA` candidates, no probabilities, forecast scores, trading scenarios or P&L. Deterministic refusal does not constitute fitted empirical evaluation. |

No future download can backdate original rule/predictor receipts. Repeated captures and
related strikes do not create independent events. Coinbase is a predictor, never the
settlement price. The narrow supported target is an official finalized binary result for
exact recognized BRTI sixty-second-average strictly-above terms, not a reconstructed
scalar BRTI value. Exceptional settlement paths remain unverified; `rules_known=false`,
missing depth and uncertified fees continue to close trading scenarios and P&L.

The [passing real-receipt browser receipt](data/bitcoin-history-review/20261029T001500Z/browser/retained-history-browser-receipt.json)
records actual Playwright-managed Chromium against a real localhost server and the
unchanged worker: form submission, all three tabs, four screenshots, four checksummed
downloads, server restart and identical reopened bytes, with zero page errors. Imported
setup jobs explicitly represent retained-receipt replay, not new browser acquisition.
There were no controlled responses, simulated clocks or replacement workers in this case.
No human page-interaction step remains for that scoped executed procedure. The
[harness guide](frontend/browser/README.md) preserves reproduction commands and distinguishes
real retained receipts from the separate empty/controlled software cases. Earlier socket
denials remain failed historical attempts and are not counted as browser passes.

## Verification and earlier evidence

This documentation reconciliation passed Ruff lint/format, strict mypy across 483 files,
**11 selected deterministic Bitcoin pytest cases** and all **12 frontend presentation
tests**. The pytest selection was `rule_recognition or binary_models or shared_research
or conflicting_event_dates or readiness` in `backend/tests/unit/test_bitcoin_history.py`;
the other eight cases were not selected. A read-only cross-check verified all 15 recorded
source hashes, checksum-validated snapshot reconstruction, original label clocks,
readiness counts, equality of the two retained replay results, all eight browser
screenshot/download hashes and this document's links. No new browser run, full-suite
run, network acquisition or clean install was performed for this documentation change.

The latest bundle's executed working-checkout checks passed Ruff lint/format, strict mypy
across 483 files, **754 pytest tests in 269.06 seconds** with no skips, all **12 frontend
checks**, 19 targeted Bitcoin tests and the real-receipt Chromium procedure in 19.1 seconds.
These are retained results from that acceptance run, not a new full-suite run or clean
install during this documentation reconciliation. Its [independent verifier result](data/bitcoin-history-review/20261029T001500Z/verification.json)
records source/label integrity, fixed boundaries, deterministic refusals and browser bytes.

The [October 26 workbench bundle](data/workbench-review/20261026T203717Z/README.md)
retains the earlier four-workflow browser pass, 26 screenshots, 24 downloads, cancellation,
worker reuse and restart evidence. Its read-only exported source passed locked setup,
Ruff/format, strict mypy across 477 files, 734 pytest tests and nine frontend tests.
Those historical results preserve their original scope; they do not certify the current
checkout's clean installation or second-family empirical models.

The real historical weather integration still contains 36 contracts across six city/day
events and three dates, with zero eligible historical forecast/scalar-label pairs.
Weather Company settlement cannot be replaced by NWS CLI; October forward receipts cannot
backfill September decisions. Synthetic fitting and replay verify software, not real
forecast accuracy, returns or profitability. Prior evidence is not rewritten.

## Decision and next acceptance

The current milestone explicitly requires the user's collection/archive decision before
further empirical work. No such choice is recorded for this continuation. Either operate
original forward capture and official-result reconciliation through the frozen validation
window using the existing workflow, or review a user-selected independently retained
archive's provenance. Keep empirical acceptance blocked until that decision and sufficient
evidence exist. No sufficient certified archive is established by the retained inputs;
public historical outcomes alone cannot supply original active-rule/Coinbase receipt clocks.

The next coherent milestone must demonstrate at least **40 receipt-valid fitting events
on 20 dates with both classes**, **20 labeled validation events on ten dates**, deterministic
real-data model/baseline evaluation and browser-visible results or precise remaining
blockers. Preserve the existing protected partition; a different archive requires separate
provenance review without moving its boundaries. Class balance, feature-domain overlap and
later source access are not guaranteed even after the minimum elapsed time.

Defer paper/shadow and final V1 acceptance. Before any future V1 completion claim, execute,
commit through the supervisor and independently review `docs/v1_acceptance.md` against
actual code, tests and durable browser/real-data evidence for every required gate.
