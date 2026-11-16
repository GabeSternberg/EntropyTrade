"""Research strategy bridge uses real engine gates; all executable inputs are synthetic."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest

from entropytrade.research.backtesting import backtest_hypothesis, strategy_for_hypothesis
from entropytrade.research.model import (
    DecisionPoint,
    FeatureNeed,
    HypothesisSpec,
    Provenance,
    RuleSketch,
)
from entropytrade.research.registry import FeatureDefinition, FeatureRegistry
from tests.r4_support import START, nonweather


def fixture() -> tuple[HypothesisSpec, FeatureRegistry, dict[str, Any]]:
    """Explicit nonweather adapter fixture, not a newly selected production family."""
    data, provider, _, config = nonweather()
    feature = FeatureDefinition(
        feature_id="mention_count",
        version="1",
        family="bitcoin",
        unit="count",
        entity="station_day",
        inputs=(),
        transform="covariate_latest",
        materializer="not_implemented",
        description="Synthetic count available before a decision",
    )
    label = feature.revalidated(
        feature_id="synthetic_result", role="label", dtype="bool", unit="outcome"
    )
    spec = HypothesisSpec(
        hypothesis_id="h-123456abcdef",
        signature="sha256:" + "1" * 64,
        title="Synthetic count hypothesis",
        objective="Verify the deterministic research backtest bridge",
        family="bitcoin",
        universe=("MENTIONS",),
        rationale="Synthetic available counts test executable replay software only.",
        features=(FeatureNeed(name="mention_count"),),
        label=FeatureNeed(name="synthetic_result", role="label"),
        decision_schedule=(DecisionPoint(day_offset=0, local_time=START.time()),),
        timestamp_semantics="Synthetic observations are timestamped before decisions.",
        candidate_models=("provided-frequency",),
        rules=(),
        validation_plan="Separate validation and protected heldout observations.",
        leakage_risks=("Labels cannot enter decision-time features.",),
        invalidation=("The source or model fails validation.",),
        provenance=Provenance(generator="local_templates", created_at=START),
    )
    return (
        spec,
        FeatureRegistry((feature, label)),
        {
            "data": data,
            "bundle": provider.bundle,
            "config": config,
            "model_family": "provided-frequency",
        },
    )


def test_missing_execution_evidence_is_a_precise_predictive_only_refusal() -> None:
    spec, registry, _ = fixture()
    result = backtest_hypothesis(spec=spec, registry=registry)
    assert result["status"] == "awaiting_execution_evidence"
    assert result["execution_fidelity"] == "predictive_only"
    assert result["performance"] is None
    assert len(result["reasons"]) == 4
    assert not result["submission_enabled"]
    assert not result["paper_eligible"]


def test_registered_synthetic_predictions_reach_existing_risk_and_replay_engine() -> None:
    spec, registry, inputs = fixture()
    result = backtest_hypothesis(spec=spec, registry=registry, **inputs)
    assert result["status"] == "backtested"
    assert result["execution_fidelity"] == "order_book_simulation"
    assert result["performance"]["forecast_metrics"]["independent_events"] == 20
    assert result["performance"]["scenarios"][0]["fill_count"] == 20
    assert len(result["performance"]["scenarios"]) == 1
    assert result["strategy"]["features"][0]["name"] == "mention_count"
    assert not result["submission_enabled"]
    assert not result["paper_eligible"]


@pytest.mark.parametrize(
    "fault", ["books", "fees", "model", "future", "version", "dataset", "unit", "dates"]
)
def test_missing_or_mismatched_evidence_never_produces_fills(fault: str) -> None:
    spec, registry, inputs = fixture()
    if fault == "books":
        inputs["data"] = inputs["data"].revalidated(
            samples=tuple(
                s.revalidated(book=None, fidelity="candle") for s in inputs["data"].samples
            )
        )
    elif fault == "fees":
        inputs["config"] = inputs["config"].revalidated(fee_policy=None)
    elif fault == "model":
        inputs["model_hash"] = "sha256:" + "f" * 64
    elif fault == "future":
        inputs["bundle"] = inputs["bundle"].revalidated(
            records=tuple(
                p.revalidated(fitted_before=START + timedelta(days=500))
                for p in inputs["bundle"].records
            )
        )
    elif fault == "version":
        inputs["data"] = inputs["data"].revalidated(feature_version="sha256:" + "e" * 64)
    elif fault == "dataset":
        inputs["bundle"] = inputs["bundle"].revalidated(
            model_metadata={**inputs["bundle"].model_metadata, "dataset_version": "wrong"}
        )
    elif fault == "unit":
        inputs["data"] = inputs["data"].revalidated(
            feature_definitions={
                "features": [{"name": "mention_count", "version": "1", "unit": "USD"}]
            }
        )
    elif fault == "dates":
        inputs["data"] = inputs["data"].revalidated(
            samples=tuple(s.revalidated(target_date=START.date()) for s in inputs["data"].samples)
        )
    result = backtest_hypothesis(spec=spec, registry=registry, **inputs)
    assert not result["eligible"]
    assert result["reasons"]
    assert result["performance"] is None or not result["performance"]["scenarios"]


def test_unfitted_hypothesis_threshold_is_never_guessed() -> None:
    spec, registry, inputs = fixture()
    spec = spec.revalidated(rules=(RuleSketch(feature="mention_count", op=">"),))
    result = backtest_hypothesis(spec=spec, registry=registry, **inputs)
    assert result["status"] == "unsupported"
    assert "unfitted" in result["reasons"][0]
    result = backtest_hypothesis(
        spec=spec, registry=registry, fitted_thresholds={"mention_count": Decimal(-1)}, **inputs
    )
    assert result["status"] == "backtested"


def test_heldout_records_never_enter_replay_even_when_relabeled_validation() -> None:
    spec, registry, inputs = fixture()
    inputs["bundle"] = inputs["bundle"].revalidated(
        records=tuple(p.revalidated(partition="validation") for p in inputs["bundle"].records)
    )
    result = backtest_hypothesis(spec=spec, registry=registry, **inputs)
    assert result["performance"]["forecast_metrics"]["independent_events"] == 20
    assert not any(p.startswith("prediction-7") for p in result["performance"]["prediction_ids"])
    assert result["prospective_validation"] == "pending_genuine_forward_observations"


def test_label_as_feature_and_unregistered_features_are_refused() -> None:
    spec, registry, inputs = fixture()
    unknown = spec.revalidated(features=(FeatureNeed(name="imaginary_edge"),))
    result = backtest_hypothesis(spec=unknown, registry=registry, **inputs)
    assert result["status"] == "unsupported"
    leaked = spec.revalidated(
        features=(FeatureNeed(name="synthetic_result"),),
        label=FeatureNeed(name="mention_count", role="label"),
    )
    with pytest.raises(ValueError, match="labels cannot"):
        strategy_for_hypothesis(
            leaked,
            registry,
            model_hash="sha256:" + "a" * 64,
            model_family="provided-frequency",
            required_sources=("fixture-transcript",),
        )


def test_no_strategy_uses_low_yes_probability_and_replays_no_fills() -> None:
    spec, registry, inputs = fixture()
    spec = spec.revalidated(
        rules=(RuleSketch(feature="mention_count", op=">=", threshold=Decimal(0), side="no"),)
    )
    inputs["bundle"] = inputs["bundle"].revalidated(
        records=tuple(
            p.revalidated(probability_yes=Decimal(".25")) for p in inputs["bundle"].records
        )
    )
    result = backtest_hypothesis(spec=spec, registry=registry, **inputs)
    assert result["status"] == "backtested"
    assert result["strategy"]["side"] == "no"
    assert result["strategy"]["entry_rules"]["all_of"][0]["op"] == "lt"
    scenario = result["performance"]["scenarios"][0]
    assert scenario["fill_count"] == 20
    assert all(fill["contract"]["side"] == "no" for fill in scenario["ledger"]["fills"])
