# StrategySpec

The current scripted research agents return a `StrategySpec`. They do not return
Python and they do not return orders. The spec is a frozen pydantic model; `spec_hash()`
is its identity, and `StrategyVersion` chains hashes so an old version is never overwritten.

## Fields

| Field | Constraint |
| --- | --- |
| `strategy_id`, `name`, `version` | Version starts at 1. |
| `description`, `hypothesis` | Required text. A hypothesis has to be a statement someone could falsify; the research record's `Hypothesis.statement` has a minimum length for the same reason. |
| `strategy_family` | `informational` (forecast the outcome) or `structural` (trade a price inconsistency). They are validated differently later. |
| `market_universe` | At least one series, event, or market ticker. "All markets" cannot be expressed. |
| `required_sources` | At least one source id. |
| `features` | Name, optional pinned version, description. |
| `model_kind` | One of the baselines in spec section 11, or `none` for a rule with no fitted model. |
| `calibration` | `none`, `isotonic`, or `platt`. Calibration without a model is rejected. |
| `entry_rules`, `exit_rules` | A description plus at least one `Predicate` (`feature`, comparison, threshold). This is data, not code. |
| `minimum_edge` | Strictly positive, per contract, after the costs the spec is willing to name. |
| `position_sizing` | Fixed contracts, fixed dollars, or fractional Kelly at or below one half, plus `max_contracts`. |
| `maximum_holding_period_seconds` | Optional, strictly positive. |
| `execution` | Time in force, post-only (which must rest), optional max spread. |
| `risk_overrides_allowed` | Only `"none"`. |
| `invalidation_conditions`, `assumptions` | At least one of each, non-blank. |
| `evidence`, `citations` | Optional. A citation has a source and a claim. |
| `generated_by` | An `Actor`. An agent actor must set `generation_run_id`. |
| `created_at` | UTC. |

`StrategyVersion.from_spec` checks the hash and the parent link.

## What this is not

R0 audit: some stored spec fields/exit predicates are not enforced, and the interpreter
checks gross probability-minus-ask rather than costed net edge. The accepted subset is
therefore not yet a complete semantic guarantee. See [capabilities](capabilities.md).

It is not a trading strategy by itself. `entropytrade.strategies.interpret` can run a
subset: informational specs, fixed contract size, an immediate order, a
`*_probability` entry feature, and an exit description that holds to settlement.
Anything else is rejected instead of half-run. Generated Python is still not
accepted.
Generated Python, if it is ever allowed, runs in a separate container with no credentials,
no network and a read-only dataset (spec section 10). The sandbox in
`karshincheo/kalshi-trading` is not that container: its AST filter allows file reads,
ctypes, network and forged results. It is rejected, not vendored.

## Promotion

A spec does not move itself. Lifecycle transitions are separate records. Agents may propose
one; they cannot approve an increase in real capital. See [`risk.md`](risk.md).
