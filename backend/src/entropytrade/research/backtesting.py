"""Bridge typed persistent hypotheses to the existing deterministic replay engine.

This module accepts already verified contract samples and frozen probability records. Scalar
weather forecasts are not contract probabilities, and settled market metadata is not proof
of historical liquidity or decision-time rules. When those inputs are absent the result is
predictive analysis only, without fills, returns or deployment eligibility.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from entropytrade.domain.enums import ActorKind, OutcomeSide, StrategyFamily, TimeInForce
from entropytrade.domain.lifecycle import Actor
from entropytrade.domain.strategy import (
    CalibrationMethod,
    ComparisonOp,
    ExecutionPreferences,
    FeatureRequirement,
    MarketUniverse,
    ModelKind,
    PositionSizing,
    Predicate,
    ProbabilityModelRef,
    RuleSet,
    SizingMethod,
    StrategySpec,
)
from entropytrade.experiments.data import ExperimentData, PredictionBundle, RecordedPredictions
from entropytrade.experiments.engine import ExperimentConfig, evaluate_candidate
from entropytrade.research.model import HypothesisSpec
from entropytrade.research.registry import FeatureRegistry
from entropytrade.strategies.interpret import compile_strategy

_OPS = {
    ">": ComparisonOp.GT,
    ">=": ComparisonOp.GE,
    "<": ComparisonOp.LT,
    "<=": ComparisonOp.LE,
    "==": ComparisonOp.EQ,
}


def strategy_for_hypothesis(
    spec: HypothesisSpec,
    registry: FeatureRegistry,
    *,
    model_hash: str,
    model_family: str,
    required_sources: tuple[str, ...],
    calibration: str = "none",
    fitted_thresholds: Mapping[str, Decimal] | None = None,
) -> StrategySpec:
    """Compile only supported, resolved rules; an unfitted threshold is never guessed.

    Entry uses a predeclared probability hurdle of 0.5 and net edge of 0.03, fixed one-contract
    sizing, immediate taker execution and settlement exit. These are research configuration,
    not optimized thresholds or trading authorization. Hypothesis rule thresholds must be
    explicit in the typed proposal or supplied from its frozen training result.
    """
    features = []
    names = {}
    for feature in spec.features:
        resolution = registry.resolve(feature.name)
        if resolution.feature_id is None:
            raise ValueError("unregistered strategy feature: " + feature.name)
        definition = registry.get(resolution.feature_id)
        if definition.role != "feature":
            raise ValueError("outcome labels cannot be strategy features")
        names[feature.name] = definition.feature_id
        features.append(
            FeatureRequirement(
                name=definition.feature_id,
                version=definition.version,
                description=definition.description,
            )
        )
    label = registry.resolve(spec.label.name)
    if label.feature_id is None or registry.get(label.feature_id).role != "label":
        raise ValueError("unregistered or invalid strategy outcome label")
    sides = {rule.side for rule in spec.rules} - {"either"}
    if len(sides) > 1:
        raise ValueError("contradictory strategy sides are unsupported")
    predicates = [
        Predicate(
            feature="model_yes_probability",
            op=ComparisonOp.LT if sides == {"no"} else ComparisonOp.GT,
            threshold=Decimal(".5"),
        )
    ]
    thresholds = fitted_thresholds or {}
    for rule in spec.rules:
        threshold = rule.threshold if rule.threshold is not None else thresholds.get(rule.feature)
        if threshold is None:
            raise ValueError("unfitted strategy threshold: " + rule.feature)
        predicates.append(
            Predicate(feature=names[rule.feature], op=_OPS[rule.op], threshold=threshold)
        )
    strategy = StrategySpec(
        strategy_id="research-" + spec.hypothesis_id,
        name=spec.title,
        version=spec.version,
        description=spec.rationale,
        hypothesis=spec.rationale,
        strategy_family=StrategyFamily.INFORMATIONAL,
        market_universe=MarketUniverse(
            description="Frozen hypothesis universe", series_tickers=spec.universe
        ),
        side=OutcomeSide.NO if sides == {"no"} else OutcomeSide.YES,
        probability_feature="model_yes_probability",
        model_ref=ProbabilityModelRef(family=model_family, version=model_hash),
        required_sources=required_sources,
        features=tuple(features),
        model_kind=ModelKind.DOMAIN_STATISTICAL,
        calibration=CalibrationMethod(calibration),
        entry_rules=RuleSet(
            description="Frozen probability and hypothesis rules", all_of=tuple(predicates)
        ),
        exit_rules=RuleSet(
            description="Hold to settlement",
            all_of=(Predicate(feature="settlement", op=ComparisonOp.EQ, threshold=Decimal(1)),),
        ),
        minimum_edge=Decimal(".03"),
        position_sizing=PositionSizing(
            method=SizingMethod.FIXED_CONTRACTS,
            contracts=Decimal(1),
            max_contracts=Decimal(1),
        ),
        execution=ExecutionPreferences(time_in_force=TimeInForce.IMMEDIATE_OR_CANCEL),
        invalidation_conditions=spec.invalidation,
        assumptions=(
            "Fixed predeclared one-contract YES/NO candidate, not a tuned execution policy.",
            "Only verified decision-time sized books and certified fee versions support replay.",
            "Replay fills are simulated; no real-money execution is authorized.",
        ),
        evidence=(spec.signature,),
        generated_by=Actor(kind=ActorKind.SYSTEM, actor_id="research-strategy-compiler-v1"),
        created_at=spec.provenance.created_at,
    )
    compile_strategy(strategy)
    return strategy


def backtest_hypothesis(
    *,
    spec: HypothesisSpec,
    registry: FeatureRegistry,
    data: ExperimentData | None = None,
    bundle: PredictionBundle | None = None,
    config: ExperimentConfig | None = None,
    model_hash: str | None = None,
    model_family: str = "ridge",
    fitted_thresholds: Mapping[str, Decimal] | None = None,
    required_sources: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run shared deterministic replay or return durable, precise missing-evidence reasons.

    The caller is responsible for verified acquisition/feature lineage before constructing
    ``ExperimentData``. This function additionally enforces registry versions and existing
    engine gates, including clocks, protected partitions, fees, model binding and risk.
    No network client or exchange submission adapter is used.
    """
    result: dict[str, Any] = {
        "status": "awaiting_execution_evidence",
        "eligible": False,
        "executed": False,
        "execution_fidelity": "predictive_only",
        "reasons": [],
        "strategy": None,
        "performance": None,
        "submission_enabled": False,
        "paper_eligible": False,
        "prospective_validation": "pending_genuine_forward_observations",
    }
    unknown = [
        need.name
        for need in (*spec.features, spec.label)
        if registry.resolve(need.name).feature_id is None
    ]
    if unknown:
        result.update(
            status="unsupported", reasons=["Unregistered features: " + ", ".join(unknown)]
        )
        return result
    if data is None:
        result["reasons"].extend(
            [
                "Historical decision-time contract prices and sized order books are unavailable.",
                "Contract rules known at historical decision times are unverified.",
            ]
        )
    if bundle is None:
        result["reasons"].append(
            "Frozen point-in-time contract probabilities are unavailable; "
            "scalar predictive metrics are not trading probabilities."
        )
    selected_config = config or ExperimentConfig(fee_versions=())
    if selected_config.fee_versions == () or (
        selected_config.fee_versions is None
        and (data is None or data.data_kind == "real" or selected_config.fee_policy is None)
    ):
        result["reasons"].append("Certified applicable historical fee evidence is unavailable.")
    if data is not None and data.data_kind == "real" and selected_config.fee_versions is None:
        result["reasons"].append("Real replay requires immutable certified fee versions.")
    if data is None or bundle is None:
        return result
    if result["reasons"]:
        return result
    dataset_version = bundle.model_metadata.get("dataset_version")
    if dataset_version is not None and dataset_version != data.dataset_version:
        result.update(status="invalid", reasons=["Model/dataset version mismatch."])
        return result
    models = {
        p.model_hash
        for p in bundle.records
        if p.family == model_family and p.partition == "validation"
    }
    if model_hash is None and len(models) == 1:
        model_hash = next(iter(models))
    if model_hash is None:
        result.update(status="invalid", reasons=["A single frozen model version is required."])
        return result
    calibrations = {
        p.calibration
        for p in bundle.records
        if p.family == model_family and p.partition == "validation"
    }
    if len(calibrations) != 1:
        result.update(status="invalid", reasons=["A single frozen calibration method is required."])
        return result
    protected = set(data.protected_events) | set(
        (bundle.model_metadata.get("split") or {}).get("holdout", [])
    )
    scoped = [s for s in data.samples if s.family in spec.universe and s.event_id not in protected]
    validation_keys = {
        (p.event_id, p.ticker, p.decision_time)
        for p in bundle.records
        if p.family == model_family and p.partition == "validation"
    }
    evaluation = [s for s in scoped if (s.event_id, s.ticker, s.decision_time) in validation_keys]
    if len({s.target_date for s in evaluation}) < selected_config.min_events:
        result["reasons"] = [
            "Insufficient independent evaluation dates; "
            "correlated contracts are not extra evidence."
        ]
        return result
    source_sets = [set(s.sources) for s in scoped]
    sources = required_sources or tuple(
        sorted(set.intersection(*source_sets) if source_sets else set())
    )
    if not sources:
        result["reasons"] = ["Verified source provenance is unavailable."]
        return result
    definitions = {f["name"]: f for f in data.feature_definitions.get("features", [])}
    for feature in spec.features:
        resolved = registry.resolve(feature.name)
        if resolved.feature_id is None:
            raise ValueError("feature resolution changed during strategy compilation")
        expected = registry.get(resolved.feature_id)
        actual = definitions.get(expected.feature_id)
        if (
            actual is None
            or actual.get("version") != expected.version
            or actual.get("unit") != expected.unit
            or actual.get("dtype", expected.dtype) != expected.dtype
            or actual.get("definition_hash", expected.definition_hash) != expected.definition_hash
        ):
            result.update(
                status="invalid",
                reasons=["Dataset/registered feature type, unit or version mismatch."],
            )
            return result
        if any(s.versions.get(expected.feature_id) != expected.version for s in scoped):
            result.update(
                status="invalid", reasons=["Contract sample/registered feature version mismatch."]
            )
            return result
    try:
        strategy = strategy_for_hypothesis(
            spec,
            registry,
            model_hash=model_hash,
            model_family=model_family,
            required_sources=sources,
            calibration=next(iter(calibrations)),
            fitted_thresholds=fitted_thresholds,
        )
    except ValueError as exc:
        result.update(status="unsupported", reasons=[str(exc)])
        return result
    result["strategy"] = strategy.model_dump(mode="json")
    candidate = {
        "candidate_id": spec.hypothesis_id,
        "hypothesis_id": spec.hypothesis_id,
        "spec": strategy.model_dump(mode="json"),
        "missing_capability": "",
        "required_features": [f.name for f in strategy.features],
        "required_sources": list(strategy.required_sources),
        "model_family": model_family,
        "evidence_ids": [spec.signature],
    }
    # This deterministic schema/registry check authorizes a research experiment only. It is
    # explicitly not an independent empirical critic, a promotion decision or human approval.
    research = {
        "decisions": [
            {"candidate_id": spec.hypothesis_id, "critic": {"accept_for_experiment": True}}
        ]
    }
    evaluated = evaluate_candidate(
        candidate, research, data, RecordedPredictions(bundle), selected_config
    )
    result.update(
        status=evaluated["status"].lower(),
        executed=evaluated["tested"],
        eligible=evaluated["tested"]
        and evaluated["status"] not in {"INSUFFICIENT_DATA", "INVALID", "UNSUPPORTED"},
        execution_fidelity="order_book_simulation" if evaluated["tested"] else "predictive_only",
        reasons=evaluated["reasons"],
        performance=evaluated,
    )
    return result
