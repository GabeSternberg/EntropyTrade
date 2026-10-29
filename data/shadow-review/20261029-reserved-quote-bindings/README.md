# Reserved quote probability bindings

Implemented/tested on `supervisor/20261029-001707`, starting HEAD `67a049c`.
No Git writes, credentials, real orders, execution activation, risk-limit changes or
historical timestamp changes. **V1 remains incomplete.** All Git operations and the
next milestone remain with the supervisor.

The shared resolver now refuses `yes_bid` and `yes_ask` as explicit probability
bindings, including when the name is absent from entry predicates. Compilation, shadow
evaluation and JSON replay consume that resolver. Ordinary quote predicates still use
the actual book with a separate implicit or explicit custom probability binding.

Before correction, both retained **CONTROLLED software fixtures** produced
`shadow_eligible` NO intentions: the entry predicate was `alias > 0.30`, audited YES
probability was `0.10`, and quotes were bid `0.40` / ask `0.50`. The book passed the
predicate while the model failed it; the intention nevertheless used NO probability
`0.90` and passed risk. These inputs/decisions are retained in
[controlled-before.json](controlled-before.json), with their original fixture clocks.
Replaying those exact serialized inputs now refuses both aliases in the resolver,
compiler and JSON replay; see [controlled-after.json](controlled-after.json). There
were no source captures, fills, real orders or empirical performance in these probes.

| Executed check | Result |
| --- | --- |
| New regressions before correction | **12 failed, 8 passed, 149 deselected**. Both reserved names were accepted; all eight shadow/replay cases reached the risk tripwire. [Log](regressions-before.log), [JUnit](regressions-before.xml). |
| New regressions after correction | **20 passed, 149 deselected**. [Log](regressions-after.log), [JUnit](regressions-after.xml). |
| Tracking/integration/workbench | **179 passed**, no skips, including all 16 new tracking cases. Final run after lint cleanup: [log](focused-tests-final.log), [JUnit](focused-tests-final.xml). |
| Shared interpreter/execution/replay/original shadow | **31 passed**, no skips, including four new resolver/compiler cases. [Log](shared-tests.log), [JUnit](shared-tests.xml). |
| Deterministic experiment/risk selection | **46 passed, 3 deselected**, no skips. The same three previously stalled asynchronous workflow cases are explicitly excluded; this is not complete-suite acceptance. [Log](deterministic-tests.log), [JUnit](deterministic-tests.xml). |
| Ruff lint/format | Pass, **491 files** already formatted. [Lint](ruff-final.log), [format](format-final.log). Initial lint found a complex `pytest.raises` block; the final test uses a single call in each block without changing the refusal assertion. |
| Strict mypy | Pass, **491 source files**. [Log](mypy-final.log). |
| Frontend presentation / JS syntax | **12 passed** with the existing DOM double. [TAP](frontend.log). `node --check` passed for the application and existing shadow browser harness. These are not browser checks. |
| Original legacy refusal/tamper probe | Pass; two legacy decisions still block on missing provenance, original verification refuses changed decisions, deliberate tamper refuses checksum mismatch. [Log](legacy-replay.log). |
| Prior evidence integrity | **160 files** across all four earlier shadow bundles preserve content and modification times. [Before snapshot](prior-evidence-before.json), [verification](prior-evidence-verification.json). |
| Complete suite / current shadow browser acceptance | **Outstanding**, not attempted again during this correction. Prior stalls and Chromium/socket denials remain recorded in the [previous evidence](../20261029-probability-binding/README.md). No mocked HTTP test is claimed as browser acceptance. |

The twenty new cases cover both quote aliases; alias presence/absence in entry rules;
YES and reproduced NO paths; direct evaluation and actual JSON serialization/replay;
implicit `custom_probability` and explicit `forecast_score` bindings; and passing/failing
quote predicates with conflicting raw quote values. The quote tests check actual book
semantics and the exact audited model edge value. Existing calibration, model identity,
provenance, protected events, source availability, fees, books, risk and recovery tests
remain unchanged and pass in the focused selections.

Reproduce from the repository root using the existing environment:

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

Outstanding supervisor/human steps: run the unchanged complete Python suite and the
existing [managed Chromium page-interaction harness](../../../frontend/browser/shadow.spec.cjs)
against a real localhost listener in a permitted environment, using fresh evidence paths
and the [documented procedure](../../../docs/shadow-tracking.md). Prior Chromium launch
failed before page interaction (`setsockopt: Operation not permitted`, `SIGTRAP`), and a
separate listener socket constructor raised `PermissionError: [Errno 1] Operation not
permitted`. Those denied attempts were not retried or bypassed. There are no new browser
screenshots or acceptance claims here.

Forward scoring still requires fitted authentic probabilities, certified fees and sized
books. Empirical validation, approved second-family support and independently checked
release acceptance remain open. Old reserved-alias decisions may fail replay under this
correction; preserve their original receipts, inputs and results rather than backfilling.

[Check results](check-results.json), [source hashes](source-checksums.json) and
[evidence hashes](evidence-checksums.json) identify this working-checkout evidence.
