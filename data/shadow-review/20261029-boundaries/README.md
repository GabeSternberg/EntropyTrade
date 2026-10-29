# Shadow calibration and holdout correction — executed evidence

Designated branch: `supervisor/20261029-001707`, starting HEAD `a1cafcb`.
Implementation and checks only; the supervisor owns every Git mutation. No credential
access, production activation, orders, fabricated receipts or performance claims.
**V1, current shadow browser/listener and complete-suite acceptance remain incomplete.**

Shadow evaluation now refuses a prediction whose calibration differs from the frozen
StrategySpec before computing intentions or risk. `none` accepts the existing `none`
and `uncalibrated baseline` labels; Platt and isotonic require exact matches. The refusal
is visible as `requested_calibration`. Other decision projections retain their previous
shape/hashes. Dataset protected events and model metadata `split.holdout` form one union
used by both evaluation and replay serialization. Replay inputs carry that union after
metadata is replaced by its hash; excluded events have no serialized samples, predictions
or decisions. Remaining targets and target availability clocks are withheld as before.

| Executed check | Result |
| --- | --- |
| New regressions against the original evaluator/replay | **10 failed, 4 passed**, demonstrating unsafe eligible calibration mismatches and metadata-protected decision exposure. [Before log](regressions-before.log). |
| Focused tracking/integration/workbench regressions | **75 passed in 6.04s**, no skips. [Log](focused-tests.log), [JUnit](focused-tests.xml). Includes accepted and mismatched calibration methods, dataset-only/model-only/combined protection, serialized exclusion and JSON round-trip replay equivalence. Existing risk, restart, failure and multi-cycle tests remain unchanged. |
| Shared replay/execution/shadow checks | **25 passed in 0.56s**, no skips. [Log](replay-risk-tests.log), [JUnit](replay-risk-tests.xml). |
| Existing retained offline replay | The intact prior controlled cycle reproduces its two original decisions and hashes; its separately retained intentional tamper still fails checksum verification. [Log](retained-replay.log). Neither original artifact was modified. |
| Ruff lint and format | Passed across the backend. [Lint](ruff.log), [format](format.log). |
| Strict mypy | Passed, 491 source/test files. [Log](mypy.log). |
| Existing frontend presentation assertions | Passed under `node --test`; this uses a DOM double. [TAP](frontend.log). `node --check frontend/browser/shadow.spec.cjs` also exited 0. Neither is browser acceptance. |
| Unchanged full-suite attempt | Collected **815 tests**; the two architecture tests passed, then the existing `test_collector_reconnects_with_new_session_and_can_restart` stalled. A 30-second faulthandler stack was retained; the 90-second outer deadline ended the attempt with **exit 124**. [Log](pytest-full-attempt.log). No full-suite pass or test failure diagnosis is claimed. |

Commands used from the repository root (output paths are this bundle):

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/mypy
.venv/bin/pytest backend/tests/unit/test_tracking.py \
  backend/tests/integration/test_shadow_tracking.py \
  backend/tests/unit/test_workbench_http.py -q --tb=short
.venv/bin/pytest backend/tests/unit/test_execution_r4.py \
  backend/tests/unit/test_replay.py backend/tests/unit/test_shadow.py -q --tb=short
node --test frontend/tests/acquisition.test.cjs
node --check frontend/browser/shadow.spec.cjs
timeout --signal=TERM --kill-after=5s 90s .venv/bin/pytest -vv --tb=short \
  -o faulthandler_timeout=30
```

To independently repeat the successful pre-correction offline check without a network:

```bash
.venv/bin/python -m entropytrade.tracking.replay \
  data/shadow-review/20261029/controlled-workspaces/test_multi_cycle_receipts_offi0/shadow/64d1e3b2-445d-4d8c-a6d5-fea49a9d159a/6c646be0-5683-4fdd-9852-d8e55ec81e11
```

The [original milestone bundle](../20261029/README.md) retains the exact browser launch
failure (`setsockopt: Operation not permitted`, `SIGTRAP`), localhost socket denial and
earlier incomplete suite attempts. Those denied launches were not repeated or bypassed.
The executable [managed Chromium/real-listener harness](../../../frontend/browser/shadow.spec.cjs)
and [operating commands](../../../docs/shadow-tracking.md) remain available. Outstanding
supervisor/human steps: execute actual page interactions and listener/restart workflows
with new evidence/workspace paths in a permitted environment; investigate the collector
stall and complete the unchanged suite. There is no new browser screenshot or pass here.

These are controlled software checks and retained replay, not new real-data acquisition
or empirical model validation. Forward model scoring, certified fees and sized books
remain absent; authentic forward intentions remain blocked. Second-family empirical
evidence, sustained operating evidence, clean install and independent V1 release acceptance
are still open. Review this correction before another major phase.
