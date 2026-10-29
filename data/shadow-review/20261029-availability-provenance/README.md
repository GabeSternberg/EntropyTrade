# Shadow calibration availability and provenance correction

Implementation on designated branch `supervisor/20261029-001707`, starting HEAD
`61eef2f`. All Git mutations belong to the supervisor. No credential access, exchange
orders, production activation, changed risk caps or empirical performance claims.
**V1, full-suite and current shadow browser/listener acceptance remain incomplete.**

The deterministic shadow evaluator now refuses Platt/isotonic predictions without a known
calibration clock by the decision. A missing clock records `calibration_availability`;
future clocks already fail `point_in_time_prediction`. Uncalibrated outputs may still have
null calibration clocks. Model metadata must supply `data_kind` matching the dataset's
required `real`/`synthetic` classification. Missing, null, unknown, malformed or mismatched
values record `model_dataset_provenance`. Refusals precede strategy invocation and risk
evaluation, leaving intentions and risk null.

Replay inputs preserve the supplied model classification, including absent/invalid cases,
without inferring it from dataset provenance. Full metadata remains redacted behind its
hash; dataset/model protected-event boundaries remain combined and targets withheld.
Matching inputs keep their prior decision projection. All fixture-derived inputs in these
checks are **CONTROLLED software evidence**, including the classification path labeled real.

| Executed check | Result |
| --- | --- |
| New regressions against starting evaluator/replay | **16 failed, 15 passed**, reproducing the null-clock and provenance approvals and loss of classification during replay. [Before log](regressions-before.log). The final tests additionally guard against any blocked strategy/risk invocation. |
| Focused tracking, integration and workbench checks | **106 passed**, no skips. [Log](focused-tests.log), [JUnit](focused-tests.xml). Covers Platt/isotonic missing/before/equal/future clocks, uncalibrated null clocks, both real/synthetic classification paths, missing/null/invalid/mismatched metadata, eligible matches, deterministic JSON replay, protected-event union and target exclusion, existing risk/recovery/failure behavior. |
| Shared execution, replay and original shadow checks | **25 passed**, no skips. [Log](replay-risk-tests.log), [JUnit](replay-risk-tests.xml). |
| Ruff lint/format | Backend passes. [Lint](ruff.log), [format](format.log). |
| Strict mypy | Passes, 491 files. [Log](mypy.log). |
| Existing frontend assertions | **12 passed** in direct Node execution, using a DOM double. [TAP](frontend.log). Existing shadow Playwright harness syntax also passes; neither is browser acceptance. |
| Bounded full-suite diagnostic | Collected **846 tests**. Two architecture checks passed, then existing collector reconnect stalled; 70-second deadline exited **124**, no completed JUnit report. [Log](pytest-full-diagnostic.log), [executable diagnostic](diagnose_suite.py). |
| Legacy retained replay and tamper | Original two decisions now block on absent model classification; verification rejects changed decision hashes. Intentional tamper still fails checksum validation. All original files remain byte-identical. [Log](legacy-replay.log), [read-only check](check_legacy_replay.py). |

The full-suite diagnostic enables asyncio logging and records one pending coroutine-chain
dump from a daemon thread. It does not change event-loop scheduling, transport, tests,
assertions or application configuration. The log captures denied `_write_to_self` writes:
`PermissionError: [Errno 1] Operation not permitted`. The suspended chain is collector
discovery → gateway market listing → SDK `AsyncTransport.request` →
`KalshiAuth.sign_request_async` → executor future. Faulthandler shows the idle executor
worker and event loop asleep in `select`. This confirms the lost wakeup failure for this
current collector stall, consistent with the [earlier independent diagnosis](../../bitcoin-history-review/20261028T235347Z/README.md).
Other previously stalled gateway/research cases were not rerun here; no full-suite pass
or comprehensive application diagnosis is claimed. Do not add polling, replace signing,
skip tests or weaken assertions to make this restricted environment appear to pass.

[Check outcomes](check-results.json), [source fingerprints](source-checksums.json) and
[bundle fingerprints](evidence-checksums.json) bind the reviewed source and retained checks.

Commands from the repository root (output filenames match this bundle):

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
.venv/bin/pytest backend/tests/unit/test_tracking.py \
  backend/tests/integration/test_shadow_tracking.py \
  backend/tests/unit/test_workbench_http.py -q --tb=short
.venv/bin/pytest backend/tests/unit/test_execution_r4.py \
  backend/tests/unit/test_replay.py backend/tests/unit/test_shadow.py -q --tb=short
node frontend/tests/acquisition.test.cjs
node --check frontend/browser/shadow.spec.cjs
.venv/bin/python data/shadow-review/20261029-availability-provenance/check_legacy_replay.py
PYTHONASYNCIODEBUG=1 timeout --signal=TERM --kill-after=5s 70s \
  .venv/bin/python data/shadow-review/20261029-availability-provenance/diagnose_suite.py
```

Browser/listener acceptance remains the outstanding supervisor/human step: run the
[managed Chromium procedure](../../../frontend/browser/shadow.spec.cjs) against an actual
localhost listener with new evidence/workspace paths, using the [documented commands](../../../docs/shadow-tracking.md).
The supported browser installation and launch were already attempted in this environment;
the [retained failure](../20261029/README.md) is crashpad
`setsockopt: Operation not permitted`, followed by `SIGTRAP`, before page interaction.
The separate localhost socket probe was also denied. Neither denied attempt was repeated
or bypassed here. There are no new screenshots or browser pass claims. Rerun the unchanged
full suite in an environment permitting asyncio socketpair wakeups as well.

Legacy artifacts are not retroactively reclassified, recalibrated or rewritten. Verifying
their old hashes requires the original evaluator, which does not satisfy the corrected
safety requirements; it is not a route to approval. Fresh inputs from the corrected
serializer preserve equality through actual JSON round trips and multi-cycle verification.
Authentic forward scoring, certified fees/depth, empirical second-family validation and
independent final release acceptance remain open. Review this correction before new work.
