# Prospective shadow-evaluation milestone — October 31, 2026

Implemented on designated `supervisor/20261031-081845` from `a83b9db`. No branches,
commits, merges, pushes, supervisor-control edits, new families, credential access, real
orders, activation or risk-limit changes. **V1 remains incomplete.** Independent review
and environment-dependent acceptance remain outstanding.

## Implemented behavior

`tracking/prospective.py` verifies committed cycle digests/artifacts, original public
features/contracts, deterministic decisions and frozen-model forecasts. It matches later
official raw binary receipts by frozen terms and receipt-time availability. The website
offers pending/refused/matched rows, unique event/date and poll counts, source/prediction/
outcome lineage and JSON/CSV exports. Protected boundaries apply before projection.

The earliest retained pre-close observation per contract is fixed; repeated polls cannot
replace missing forecasts or increase independent evidence. Model versions, calibrations
and real/synthetic classifications stay separate. Ten matched events on five dates permit
descriptive event-weighted Brier/log loss and reliability bins. Strikes divide event weight;
no significance, historical validation, trading return or profitability claim is supported.
Quote/fee/risk refusal is independently visible and does not invalidate a causal forecast.

The collector now shares its existing ten-contract outcome budget between unresolved
contracts and finalized revision checks, with oldest-attempt rotation. Later official
corrections remain in new cycle receipts. Monitoring uses the latest valid receipt at its
cutoff; first simulated accounting settlements and old decisions remain frozen. The real
collector regression exercises NO → YES correction, no duplicate paper settlement and
unchanged original files. Model protection and original historical partitions do not move.

## Executed scoped checks

- Repository Ruff lint and format check pass: [lint](ruff-lint.log), [format](ruff-format.log).
- Strict mypy passes all **556 files**: [log](mypy.log).
- **24 frontend presentation tests** pass: [log](frontend-final.log). These DOM doubles
  verify labeling, absent metrics and text-safe source rendering; they are not browser tests.
- **28 focused pytest cases** pass: [log](focused-final.log), [JUnit](focused-final.xml). They cover
  deduplication, delayed receipts/as-of cutoffs, revisions/conflicts, missing/invalid forecasts,
  future fit/calibration clocks, holdouts, later protection, original-contract forgery,
  authentic insufficiency, original shadow risk/replay and real collector revisions.
  This final focused run covers the last fail-closed projection guard after the all-file driver
  started; the all-file failures below remain recorded separately.
- Both offline restart/snapshot/restore paths pass: [durable receipt](offline/receipt.json),
  [driver](offline_proof.py), [log](offline-proof.log). JSON reports/CSV bytes reproduce,
  with **23 synthetic cycle files and all 68 authentic cycle files unchanged**. Offline
  exports are files generated locally, not website downloads.
- Chromium's supported installation completes: [log](chromium-install.log). The final
  executable harness discovers both procedures: [log](harness-final-discovery.log).
  Syntax checks pass. Neither discovery nor installation proves browser acceptance.

## Distinct synthetic and authentic evidence

[Synthetic report](offline/synthetic-report.json) and [CSV](offline/synthetic-observations.csv):
39 repeated poll observations project to 13 contracts on 12 distinct events/dates: 11 matched
contracts on ten events/dates, one pending forecast, one missing-prediction refusal and one
excluded boundary event. A second strike shares event weight. One later correction changes
the monitoring label; Brier score **0.0875** is explicitly controlled synthetic software evidence,
never empirical model performance or trading accounting. Original fake source clocks are not
presented as authentic history.

[Authentic report](offline/authentic-report.json) and [CSV](offline/authentic-observations.csv):
unchanged original receipt bytes give **24 refused contract observations, four events, two
dates and 48 polls**. There is no usable forecast and **no invented metric**. No new network
acquisition or external-source verification is claimed. The test import restores the original
frozen strategy/model identity while keeping original cycle files unchanged; destination
monitor/cycle IDs and SQLite bookkeeping are new. Original receipt times are retained.

Archives/workspaces referenced by `offline/receipt.json` are retained under ignored `data/cache`;
they are required for raw workspace restore review and are not promised in a clean checkout.
The tracked report/CSV/source-hash receipts remain independently readable. Reproduce with
fresh paths by adapting the executable `offline_proof.py`; existing workspaces are never replaced.

## Browser/listener boundary and outstanding human step

The actual managed Chromium attempt failed **before page setup**, at
`third_party/crashpad/crashpad/util/linux/socket.cc:45`:
`setsockopt: Operation not permitted (1)`, followed by SIGTRAP. The retained
[launch log](browser-attempt-1.log), [Playwright JSON](browser-attempt-1/playwright-results.json),
[JUnit](browser-attempt-1/playwright-results.xml) and small failure trace contain that result.
One procedure failed at launch; the authentic procedure did not run. **No page interaction,
screenshot or website download was executed.** The same denied browser launch is not repeated;
no flags, security settings or environment permissions were changed.

Separately, the actual localhost-listener acceptance fails at `socket.socket(AF_INET, ...)`
with `PermissionError: [Errno 1] Operation not permitted`: [initial log](focused-attempt-1.log)
and bounded per-file listener log. Offline/DOM checks do not replace either failure.

Outstanding: execute **both** procedures in `frontend/browser/prospective.spec.cjs` in a
socket-permitted environment using the fresh-path command in
[the workflow](../../../docs/prospective-evaluation.md), inspect retained screenshots, compare
JSON/CSV downloads across restart/offline restore and verify zero page errors. Run the actual
listener test and complete pytest suite there. Keep these acceptance gates open until executed;
independent supervisor review is still required.

## Full-suite execution limits and retained attempts

The unfiltered suite collected **1,318 tests**, passed the two architecture tests, then made
no further progress in the existing collector reconnect file under this restricted runtime.
It was interrupted (process exit **130**): [collection](pytest-collection.log),
[partial log](pytest-full.log). This is incomplete, not a full-suite pass.

The bounded [all-file driver](run_bounded_pytest.py) attempts every test file without changing
assertions or markers, using four independent processes, a 90-second per-file deadline and
retained logs/JUnit. Deadlines and nonzero exits are always incomplete/failing evidence.
Exact final counts are recorded in `per-file-summary.json` and `verification.json`.

The final [all-file summary](per-file-summary.json) records **241 files attempted in
477.06 seconds: 217 passed, 12 failed and 12 exceeded deadlines**. The 217 passing files
contain 1,123 cases. Nine failing files contain eleven localhost cases, all denied socket
creation. Two existing weather-label lifecycle cases fail shutdown with
`RuntimeError: weather acquisition did not stop; workspace lease retained`; these remain
unresolved, rather than being relabeled as successful environment checks. The remaining
failure is `test_shadow_history.py`, process exit **-11 (SIGSEGV)** with an incomplete
faulthandler trace during file hashing and no JUnit completion. Its native-crash cause is
unestablished. The isolated serial follow-up passes **all 14 tests in 71.20s**:
[log](shadow-history-isolated.log), [JUnit](shadow-history-isolated.xml). Its 60-second
diagnostic trace shows ongoing hashing before completion; assertions are unchanged. This
non-reproduction does not turn the all-file run into a pass. Deadline files/case counts and every exact exit are in the
summary. No assertions, policy, monetary caps or markers were weakened.

Development evidence retains the initial listener denial and early fixture errors. The first
unit iteration had three failures (invalid calibration fixture, unhandled unknown outcome status,
and a ticker/rules fixture mismatch). Unknown SDK statuses now become explicit outcome refusals;
the fixtures preserve their proper identities. A later strengthened frozen-strategy check exposed
the generic authentic import's setup identity mismatch; the new fixture restores original frozen
identity without changing any receipt. Passing focused evidence follows those corrections.
