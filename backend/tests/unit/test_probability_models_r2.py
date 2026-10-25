"""Coherent probabilities, grouped temporal boundaries and reusable fitted artifacts."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.ml.evaluation import metrics, temporal_plan, walk_forward_plans
from entropytrade.ml.models import EventExample, WeatherModel
from entropytrade.ml.probability import contract_probability, normal_cdf
from entropytrade.weather.probability import InsufficientHistoryError
from tests.r2_support import row


@given(st.integers(-50, 150), st.integers(1, 50), st.floats(-30, 130, allow_nan=False))
def test_nested_thresholds_monotone_and_exhaustive_buckets_sum_to_one(
    threshold: int, gap: int, mean: float
) -> None:
    def cdf(x: float) -> float:
        return normal_cdf((x - mean) / 4)

    low = Strike(strike_type=StrikeType.GREATER, floor=Decimal(threshold))
    high = Strike(strike_type=StrikeType.GREATER, floor=Decimal(threshold + gap))
    assert 0 <= contract_probability(high, cdf) <= contract_probability(low, cdf) <= 1
    below = Strike(strike_type=StrikeType.LESS, cap=Decimal(threshold))
    between = Strike(
        strike_type=StrikeType.BETWEEN, floor=Decimal(threshold), cap=Decimal(threshold + gap)
    )
    assert (
        contract_probability(below, cdf)
        + contract_probability(between, cdf)
        + contract_probability(high, cdf)
    ) == pytest.approx(1)


def test_strict_fractional_thresholds_and_bucket_inclusivity() -> None:
    def cdf(x: float) -> float:
        return float(x >= 81)

    for strike_type, floor, cap, expected in (
        (StrikeType.GREATER, "81", None, 0),
        (StrikeType.GREATER, "80.5", None, 1),
        (StrikeType.LESS, None, "81", 0),
        (StrikeType.LESS, None, "81.5", 1),
        (StrikeType.BETWEEN, "81", "82", 1),
        (StrikeType.BETWEEN, "80.1", "80.9", 0),
    ):
        strike = Strike(
            strike_type=strike_type,
            floor=Decimal(floor) if floor else None,
            cap=Decimal(cap) if cap else None,
        )
        assert contract_probability(strike, cdf) == expected
    with pytest.raises(ValueError, match="Fahrenheit"):
        contract_probability(strike, cdf, unit="degC")


def examples(count: int = 90) -> list[EventExample]:
    start = datetime(2024, 1, 1, 15, tzinfo=UTC)
    return [
        EventExample(
            event_id=f"event-{n}",
            decision=start + timedelta(days=n),
            target_date=(start.date() + timedelta(days=n)).isoformat(),
            station="fixture",
            features={"forecast_high_f": float(60 + n % 10), "season_sin": n / 100},
            target_f=float(62 + n % 10 + n % 3 - 1),
            label_available=start + timedelta(days=n, hours=19),
        )
        for n in range(count)
    ]


def test_small_samples_refused_and_training_future_labels_rejected() -> None:
    data = examples()
    cutoff = data[-1].label_available + timedelta(days=1)
    model = WeatherModel("ridge")
    with pytest.raises(InsufficientHistoryError):
        model.fit(data[:10], asof=cutoff)
    with pytest.raises(ValueError, match="label/decision"):
        model.fit(data, asof=data[-1].decision)
    with pytest.raises(ValueError, match="one frozen decision"):
        model.fit([*data, data[0]], asof=cutoff)
    with pytest.raises(ValueError, match="integer"):
        model.fit([replace(data[0], target_f=60.2), *data[1:]], asof=cutoff)


@pytest.mark.parametrize("method", ["platt", "isotonic"])
def test_calibration_disjoint_temporal_and_monotone(method: str) -> None:
    data = examples(120)
    model = WeatherModel("forecast_error")
    model.fit(data[:80], asof=data[80].decision)
    with pytest.raises(ValueError, match="overlap"):
        model.calibrate(data[60:100], asof=data[100].decision)
    with pytest.raises(ValueError, match="temporal"):
        model.calibrate(data[80:110], asof=data[100].decision)
    model.calibrate(data[80:110], asof=data[110].decision, method=method)
    assert set(model.training_events).isdisjoint(model.calibration.event_ids)
    probabilities = [model.cdf(data[111].features, t) for t in range(40, 90)]
    assert probabilities == sorted(probabilities)
    assert all(0 <= p <= 1 for p in probabilities)
    assert model.cdf(data[111].features, float("-inf")) == 0
    assert model.cdf(data[111].features, float("inf")) == 1


def test_repeatable_train_only_imputation_and_model_serialization(tmp_path: Path) -> None:
    data = examples(100)
    cutoff = data[80].decision
    models = [WeatherModel("ridge"), WeatherModel("ridge")]
    hashes = []
    with threadpool_limits(limits=1):
        for index, model in enumerate(models):
            model.fit(data[:80], asof=cutoff)
            model.calibrate(data[80:], asof=data[-1].label_available + timedelta(days=1))
            hashes.append(model.save(tmp_path / f"model-{index}.joblib"))
    assert hashes[0] == hashes[1]
    with pytest.raises(ValueError, match="trusted"):
        WeatherModel.load(tmp_path / "model-0.joblib", expected_hash=hashes[0])
    with pytest.raises(ValueError, match="hash mismatch"):
        WeatherModel.load(tmp_path / "model-0.joblib", expected_hash="wrong", trusted=True)
    loaded = WeatherModel.load(tmp_path / "model-0.joblib", expected_hash=hashes[0], trusted=True)
    strike = Strike(strike_type=StrikeType.GREATER, floor=Decimal(65))
    assert loaded.predict_proba(data[-1].features, strike, unit="degF") == models[0].predict_proba(
        data[-1].features, strike, unit="degF"
    )
    # The median is learned from training only; distant evaluation values do not refit it.
    assert loaded.estimator.named_steps["imputer"].statistics_[0] == 64.5
    assert len(loaded.training_events) == 80


def test_split_keeps_events_and_same_date_cities_together_and_holdout_protected() -> None:
    rows: list[dict[str, Any]] = []
    for n in range(150):
        source = row(date(2025, 1, 1) + timedelta(days=n))
        for city in ("PHL", "CHI"):
            rows.extend(
                {**source, "event_id": f"{city}-{n}", "market_ticker": f"{city}-{n}-{strike}"}
                for strike in range(5)
            )
    plan = temporal_plan(rows)
    groups = (plan.fit, plan.calibration, plan.validation, plan.holdout)
    for n in range(150):
        assert sum(f"PHL-{n}" in g and f"CHI-{n}" in g for g in groups) == 1
    for fold in walk_forward_plans(rows):
        assert set(fold.fit + fold.calibration + fold.validation).isdisjoint(plan.holdout)
    with pytest.raises(ValueError, match="at least ten"):
        temporal_plan(rows[:10])


def test_metrics_count_independent_events_not_contracts_or_unbalanced_event_sizes() -> None:
    predictions = [{"event_id": "one", "probability_yes": 0.8, "outcome": "yes"}] * 20
    predictions += [{"event_id": "two", "probability_yes": 0.1, "outcome": "yes"}]
    result = metrics(predictions)
    assert result["independent_events"] == 2
    assert result["contracts"] == 21
    assert result["brier"] == pytest.approx((0.04 + 0.81) / 2)
    assert result["status"] == "descriptive_small_sample"
    assert result["calibration_slope"] is None
    assert sum(b["predictions"] for b in result["reliability_bins"]) == 21
    json.dumps(result, allow_nan=False)
