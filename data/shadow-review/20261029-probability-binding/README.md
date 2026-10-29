# Shadow probability binding correction

Implemented on designated branch `supervisor/20261029-001707`, starting HEAD `d43e262`.
No Git mutations, credential access, real orders, production activation, changed risk
limits or empirical performance claims. **V1, full-suite and current shadow
browser/listener acceptance remain incomplete.** Review this correction before new work.

The compiler and shadow evaluator now share `resolve_probability_feature`: explicit
aliases must occur in the entry predicates; otherwise exactly one distinct
`*_probability` predicate name is required. The shadow evaluator supplies its validated
prediction under that exact name. Competing raw features under the bound name are
excluded from interpreter observations but retained unchanged in the decision audit,
source versions and feature hash. This also prevents as-of tie breaking from selecting
a raw value when feature and prediction availability clocks match. Other feature,
model identity, calibration, provenance, source, holdout, fee, book and risk checks remain.

The retained [controlled inputs and decisions](controlled-probability-cases.json) show
implicit `custom_probability`, raw `0.95`, matching feature hashes and all precondition
gates passing. Audited model `0.10` produces `no_signal`, null intention and null risk;
audited `0.75` produces a controlled shadow intention whose edge uses exactly `0.75`.
Both reproduce through JSON serialization. These are explicitly **CONTROLLED software
fixtures**, never authentic forward models, source certification, fills or returns.

| Executed check | Result |
| --- | --- |
| Initial regressions before fix | **8 failed, 40 passed**, 90 deselected. Reproduces unsafe raw `0.95` approval over model `0.10`, incorrect edge probability, missing/null/low raw-feature false refusals, and repeated implicit predicates. [Before log](regressions-before.log). Nine model-identity/tied-clock cases were added afterward. |
| Initial regressions after fix | **48 passed**, 90 deselected. [Log](regressions-after.log). The final 57 new cases all run in the focused selection below. |
| Focused tracking/integration/workbench | **163 passed**, no skips. [Log](focused-tests.log), [JUnit](focused-tests.xml). Includes all existing calibration/provenance/holdout/risk/lifecycle checks and 57 new binding cases. |
| Shared interpreter/replay/execution/original shadow | **27 passed**, no skips. [Log](replay-risk-tests.log), [JUnit](replay-risk-tests.xml). |
| Selected deterministic experiment/risk regressions | **46 passed, 3 deselected**, no skips. [Log](deterministic-experiment-risk-tests.log), [JUnit](deterministic-experiment-risk-tests.xml). Three asynchronous experiment workflow cases excluded explicitly; this is a focused selection, not a full-suite pass. |
| Ruff lint/format | Passes, 491 files formatted. [Lint](ruff.log), [format](format.log). |
| Strict mypy | Passes, 491 files. [Log](mypy.log). |
| Frontend presentation and syntax | **12 passed**, using the existing DOM double. [TAP](frontend.log). Application and existing shadow Playwright harness syntax checks exit 0; this is not browser acceptance. |
| Bounded complete-suite attempt | **Incomplete**, 903 tests collected, two architecture tests passed, then existing collector reconnect test stalled. External 70-second deadline exited **124**, no final JUnit report. [Log/stack](pytest-full.log). |
| Broader experiment/risk attempt | **Incomplete**, 60-second deadline exited **124** after 15 completion dots; no final report. [Log](experiment-risk-tests.log). The later deterministic selection above passed; it does not complete this attempted selection. |
| Legacy replay/tamper check | Original two decisions still refuse missing model provenance; original decision verification and deliberate tamper both reject as expected. Original files remain unchanged. [Log](legacy-replay.log), [existing executable check](../20261029-availability-provenance/check_legacy_replay.py). |
| Prior evidence integrity | **133 checksummed files verified unchanged** across the three prior shadow evidence bundles. [Results](prior-evidence-verification.json). |
| Current shadow browser/listener acceptance | **Unexecuted**. Previously denied supported installation/launch and listener attempts were not repeated or bypassed. Existing executable harness remains the outstanding supervisor/human step. |

The 57 new cases exercise implicit conventional/custom names, explicit custom names and
aliases without a probability suffix; missing/null/low/high/coincident raw features;
model `0.10`/`0.75`; missing/ambiguous predictions and missing required input features;
model family/hash matches and mismatches; identical clocks with model names sorting before
the raw source; repeated predicates on one inferred name; explicit disambiguation of other
probability predicates; and missing/ambiguous/invalid bindings. Successful, no-signal and
blocked outcomes are checked through actual JSON replay. Information-gate refusals guard
against strategy invocation or risk evaluation. Matching feature hashes alone never let
a raw value substitute for an audited prediction.

The current complete-suite stack shows the event loop in `select` and an idle executor
worker in the existing collector reconnect case. The [prior diagnostic](../20261029-availability-provenance/README.md)
recorded denied asyncio self-pipe writes while awaiting SDK signing; this run retains
the stack but does not claim a new independent proof of that permission failure. No SDK,
event-loop policy, timeout, test or assertion was changed to bypass the stall.

Legacy decisions affected by the binding bug may no longer reproduce their old hashes.
Preserve their original inputs/results; do not backfill observations, receipt clocks,
predictions or classifications to recover a pass. Unaffected default decisions retain
their projection. The unchanged legacy controlled cycles already lack model provenance
and continue to block for that separately recorded reason.

Commands from the repository root:

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
.venv/bin/pytest backend/tests/unit/test_tracking.py \
  backend/tests/integration/test_shadow_tracking.py \
  backend/tests/unit/test_workbench_http.py -q --tb=short
.venv/bin/pytest backend/tests/unit/test_interpret.py \
  backend/tests/unit/test_execution_r4.py backend/tests/unit/test_replay.py \
  backend/tests/unit/test_shadow.py -q --tb=short
.venv/bin/pytest backend/tests/unit/test_experiments_r4.py \
  backend/tests/unit/test_orders_risk_lifecycle.py backend/tests/unit/test_paper_risk.py \
  -k 'not real_workflow and not synthetic_end_to_end and not same_research_replays' \
  -q --tb=short
node frontend/tests/acquisition.test.cjs
node --check frontend/src/app.js
node --check frontend/browser/shadow.spec.cjs
.venv/bin/python data/shadow-review/20261029-availability-provenance/check_legacy_replay.py
```

[Check outcomes](check-results.json), [source fingerprints](source-checksums.json) and
[bundle fingerprints](evidence-checksums.json) bind the reviewed source and evidence.
The full-suite command used `PYTHONASYNCIODEBUG=1 timeout --signal=TERM --kill-after=5s 70s
.venv/bin/pytest -vv -s --tb=short -o faulthandler_timeout=20`; the additional attempted
experiment/risk selection used the same three files above without `-k`, under a 60-second
external deadline. Both attempted JUnit output but neither finished a report.

Outstanding supervisor/human acceptance: run the existing [managed Chromium procedure](../../../frontend/browser/shadow.spec.cjs)
against the real localhost application using the [documented commands](../../../docs/shadow-tracking.md)
with fresh evidence/workspace paths, and run the unchanged complete Python suite in a
permitted environment. Retain page interactions, screenshots, downloads and listener
lifecycle evidence. Prior Chromium launch failed before page interaction with crashpad
`socket.cc:45`, `setsockopt: Operation not permitted (1)` and `SIGTRAP`; the separate
listener socket constructor raised `PermissionError: [Errno 1] Operation not permitted`.
[Original evidence](../20261029/README.md) remains intact. There are no new screenshots
or browser acceptance claims, and HTTP/unit tests do not replace this outstanding step.

Authentic forward scoring still lacks fitted probabilities, certified fees and sized
books; actual captures remain fail closed. Empirical validation, approved second-family
support and final independently checked release acceptance remain separate open gates.
All commits, merges and pushes are left to the supervisor.
