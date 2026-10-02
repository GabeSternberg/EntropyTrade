---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 10 checkpoint

Date: 2026-10-02. Phase 10 is complete as a fixture-tested gate. No order was
sent. `attempt_submit` is not connected to `KalshiGateway`.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 11.

A copy of this file is in the repository at `docs/phase-reports/phase-10.md`.

## What was built

`is_decayed` scores a sequence of `ShadowComparison` rows. A row counts only
when `difference` is set. That value is the next print minus the fill or
shadow price. A gap has no print, so it is skipped. Decay is true when at
least `window` scored rows exist and the mean of the last `window` of them
is strictly below the caller's threshold. A mean equal to the threshold is
not decay. A shorter series is not decay.

`propose_downward` builds one `LifecycleTransition` when decay is true and a
legal downward edge exists. The actor is an agent and there is no
`HumanApproval`, which the lifecycle type already allows for a decrease.
`live` goes to `degraded`. `live_small` goes to `degraded`. `degraded` and
`paper` and `shadow_live` go to `paused`. `backtested` and `validated` have
no `paused` or `degraded` edge, so they go to `research`. `paused`, `draft`,
and `research` go to `retired`. `retired` proposes nothing. The proposal is
never `live` or `live_small`. An agent still cannot apply `shadow_live` to
`live_small`.

`reduced_quantity` halves a contract count on the 0.01 grid, rounding down,
and never returns a larger number. `0.01` stays `0.01` because half of it
rounds to zero. When decay is false the quantity is unchanged.

## Acceptance

| Criterion | Result |
| --- | --- |
| Recent mean of print minus price, gaps excluded | Met. |
| Threshold is an argument; equality is not decay | Met. |
| Downward move only, and only on an allow-listed edge | Met. `backtested` → `research`. |
| Never proposes `live` or `live_small` | Met. |
| An agent can apply the downward move | Met. The transition constructs. |
| An agent cannot apply an upward capital move | Met. The existing validator still rejects it. |
| Size does not increase | Met. |
| No socket, no submit wiring | Met. The module names neither host nor `attempt_submit`. |
| Spec diagnostics that need other series | Not implemented. See weaknesses. |

## Files

- `backend/src/entropytrade/monitoring/decay.py`
- `backend/tests/unit/test_decay.py`
- `docs/risk.md` (decay paragraph)

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 140 passed
(134 from Phase 9, plus 6 decay tests).

## Reused code

`ShadowComparison`, `LifecycleTransition`, `capital_rank`, and the allow-list.
No audited bot. No new dependency.

## Weaknesses

- Model drift, calibration, live-versus-backtest divergence, feature drift,
  and a separate realized-versus-expected edge are not scored. A comparison
  row does not carry a model, a feature vector, or a backtest path. Inventing
  those series would be a fake diagnostic.
- The health number is the recent mean difference. There is no second score.
- Halving does not change a risk-limit configuration. It returns a smaller
  quantity for the caller to use. Nothing raises a limit.
- `paused` to `retired` is the only further downward edge. Resuming from
  `paused` is not proposed.
- This does not watch a live session. The inputs are fixture comparisons.

## Decisions

- `attempt_submit` stays unwired from `KalshiGateway`. Decay does not import
  the gate, the gateway, or an HTTP client.
- The first downward step from `live` is `degraded`, matching the spec's
  `LIVE → DEGRADED` step. Reduced size is a separate function, then a later
  decay from `degraded` proposes `paused`.
- A missing edge stops at the nearest legal state that does not increase
  capital rank, rather than inventing a `backtested` → `paused` edge.

## Exact plan for Phase 11

Phase 11 stays deferred. Do not add pmxt, FIX, deep learning, cross-exchange
execution, or automatic retraining. Write the deferral into
`docs/phase-reports/phase-11.md` and the store copy, mark Phase 11 deferred
in `STATUS.md`, and commit that documentation only.
