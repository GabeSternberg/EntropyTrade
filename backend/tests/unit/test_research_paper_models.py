"""Portable acquired-feature models are data, source-specific and horizon-bound."""

import copy
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropytrade.domain.enums import MarketStatus, MarketType, StrikeType
from entropytrade.domain.market import (
    Market,
    MarketRules,
    PriceRange,
    SettlementSource,
    Strike,
    TickSchedule,
)
from entropytrade.domain.strategy import StrategySpec
from entropytrade.experiments.data import ContractSample, ExperimentData
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.models import CDFCalibration, WeatherModel
from entropytrade.research.modeling import run_hypothesis
from entropytrade.research.paper_models import (
    PortableResearchModel,
    freeze_research_model,
    load_research_binding,
    next_research_decision,
    paper_window,
    score_research_model,
    verify_research_binding,
)
from entropytrade.research.registry import FeatureRegistry
from tests.research_execution_support import execution_fixture
from tests.research_modeling_support import MODEL_NOW, modeling_fixture


@pytest.fixture(scope="module")
def portable(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]]:
    root = tmp_path_factory.mktemp("portable-paper")
    hypothesis, artifacts = modeling_fixture(root)
    hypothesis = hypothesis.revalidated(rules=())
    identifier, fees = execution_fixture(root, hypothesis, artifacts)
    result = run_hypothesis(
        root=root,
        registry=FeatureRegistry(),
        spec=hypothesis,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
        execution_datasets=(identifier,),
        fee_versions=fees,
    )
    strategy = StrategySpec.model_validate(result["models"]["ridge"]["backtest"]["strategy"])
    binding = load_research_binding(root, result["experiment_id"], "ridge", data_kind="synthetic")
    return root, result, strategy, binding


def forward(binding: dict[str, Any]) -> tuple[ExperimentData, dict[str, Market]]:
    model = PortableResearchModel.model_validate(binding["snapshot"])
    when = datetime(2026, 11, 14, 23, 0, 30, tzinfo=UTC)
    target = date(2026, 11, 15)
    event = "KXHIGHPHIL-26NOV15"
    ticker = event + "-T65"
    rules = MarketRules(
        market_ticker=ticker,
        rules_primary="SYNTHETIC CLIPHL high in Fahrenheit according to The Weather Company",
        settlement_sources=(SettlementSource(name="The Weather Company"),),
        settlement_basis="contract_text",
        settlement_target_date=target,
        captured_at=when - timedelta(seconds=20),
    )
    market = Market(
        ticker=ticker,
        event_ticker=event,
        series_ticker="KXHIGHPHIL",
        title="Synthetic Philadelphia high",
        market_type=MarketType.BINARY,
        status=MarketStatus.ACTIVE,
        open_time=when - timedelta(days=1),
        close_time=when + timedelta(days=2),
        strike=Strike(strike_type=StrikeType.GREATER, floor=Decimal(65)),
        rules=rules,
        tick_schedule=TickSchedule(
            ranges=(PriceRange(start=Decimal(0), end=Decimal(1), step=Decimal(".01")),)
        ),
    )
    sample = ContractSample(
        event_id=event,
        ticker=ticker,
        family="KXHIGHPHIL",
        target_date=target,
        decision_time=when,
        close_time=market.close_time,
        features_available_at=when - timedelta(seconds=10),
        features={"nws_pfm_max_f": Decimal(65), "nws_cli_bias_f": Decimal(0)},
        versions={f.feature_id: f.version for f in model.features},
        feature_hash="sha256:" + "a" * 64,
        sources=("kalshi", "verified-research-features"),
        rules_known=True,
        eligible=True,
    )
    data = ExperimentData(
        dataset_version="sha256:" + "b" * 64,
        feature_version="sha256:" + "c" * 64,
        data_kind="synthetic",
        samples=(sample,),
        feature_definitions={"features": [f.model_dump(mode="json") for f in model.features]},
        provenance={
            "adapter": "research-forward-v1:weather",
            "feature_schema_hash": model.feature_schema_hash,
            "deployment_created_at": (MODEL_NOW + timedelta(minutes=1)).isoformat(),
        },
    )
    return data, {ticker: market}


@pytest.mark.parametrize("kind", ["climatology", "raw_forecast", "forecast_error", "ridge"])
def test_portable_scoring_matches_fitted_model_and_calibration_tails(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
    kind: str,
) -> None:
    root, result, _, _ = portable
    path = root / "experiments" / ("sha256-" + result["experiment_id"].removeprefix("sha256:"))
    frozen = PortableResearchModel.model_validate_json((path / (kind + ".paper.json")).read_text())
    model = WeatherModel.load(
        path / (kind + ".joblib"),
        expected_hash=result["models"][kind]["artifact_hash"],
        trusted=True,
    )
    for forecast in (40.0, 65.0, 90.0):
        values: dict[str, float | None] = {
            "nws_pfm_max_f": forecast,
            "nws_cli_bias_f": -2.0,
            "forecast_high_f": forecast,
        }
        for threshold in (-100, 40, 64, 65, 66, 90, 200):
            strike = Strike(strike_type=StrikeType.GREATER, floor=Decimal(threshold))
            assert frozen.probability(values, strike) == pytest.approx(
                model.predict_proba(values, strike, unit="degF"), abs=1e-12
            )


def test_binding_loader_does_not_deserialize_joblib(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, result, strategy, _ = portable

    def reject(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("paper cannot load executable model artifacts")

    monkeypatch.setattr(WeatherModel, "load", reject)
    binding = load_research_binding(root, result["experiment_id"], "ridge", data_kind="synthetic")
    model = verify_research_binding(strategy, binding, data_kind="synthetic")
    assert model.family == "ridge"
    with pytest.raises(ValueError, match="provenance"):
        load_research_binding(root, result["experiment_id"], "ridge")


def test_only_trained_horizon_is_scheduled_and_scored(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
) -> None:
    _, _, strategy, binding = portable
    data, markets = forward(binding)
    sample = data.samples[0]
    assert paper_window(binding, sample.decision_time) == sample.target_date
    assert next_research_decision(binding, sample.decision_time) == datetime(
        2026, 11, 15, 23, tzinfo=UTC
    )
    assert next_research_decision(binding, datetime(2026, 7, 1, 21, tzinfo=UTC)) == datetime(
        2026, 7, 1, 22, tzinfo=UTC
    )
    scored = score_research_model(strategy, data, binding, markets)
    assert len(scored.records) == 1
    assert scored.records[0].partition == "forward"
    assert scored.records[0].fitted_before == MODEL_NOW
    late = sample.revalidated(decision_time=sample.decision_time + timedelta(minutes=1))
    refused = score_research_model(strategy, data.revalidated(samples=(late,)), binding, markets)
    assert not refused.records
    assert "trained horizon" in refused.refusals[sample.ticker]


@pytest.mark.parametrize(
    "failure", ["schema", "source", "version", "binding", "deployment_clock", "protected"]
)
def test_changed_semantics_and_protected_station_day_cannot_score(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
    failure: str,
) -> None:
    _, _, strategy, original = portable
    binding = copy.deepcopy(original)
    data, markets = forward(binding)
    sample = data.samples[0]
    if failure == "schema":
        definitions = copy.deepcopy(data.feature_definitions)
        definitions["features"][0]["inputs"][0]["variable"] = "hourly_temperature_f"
        data = data.revalidated(feature_definitions=definitions)
    elif failure == "source":
        data = data.revalidated(
            provenance={**data.provenance, "adapter": "public-forward-v1:weather"}
        )
    elif failure == "version":
        data = data.revalidated(samples=(sample.revalidated(versions={"nws_pfm_max_f": "2"}),))
    elif failure == "binding":
        binding["snapshot"]["ridge_intercept"] += 10
    elif failure == "deployment_clock":
        data = data.revalidated(
            provenance={
                **data.provenance,
                "deployment_created_at": (sample.decision_time + timedelta(seconds=1)).isoformat(),
            }
        )
    else:
        binding["snapshot"]["protected_events"].append("CLIPHL:" + sample.target_date.isoformat())
        binding["binding_hash"] = scientific_hash(
            {k: v for k, v in binding.items() if k != "binding_hash"}
        )
    result = score_research_model(strategy, data, binding, markets)
    assert not result.records
    assert result.refusals


@pytest.mark.parametrize("failure", ["scalar", "inactive", "wrong_authority"])
def test_contract_type_activity_and_authority_are_not_inferred_from_features(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
    failure: str,
) -> None:
    _, _, strategy, binding = portable
    data, markets = forward(binding)
    market = next(iter(markets.values()))
    if failure == "scalar":
        market = market.revalidated(market_type=MarketType.SCALAR)
    elif failure == "inactive":
        market = market.revalidated(status=MarketStatus.CLOSED)
    else:
        market = market.revalidated(
            rules=market.rules.revalidated(
                settlement_sources=(SettlementSource(name="National Weather Service"),)
            )
        )
    result = score_research_model(strategy, data, binding, {market.ticker: market})
    assert not result.records
    assert "strike/rules" in result.refusals[market.ticker]


def test_nonfinite_or_wrong_dimension_portable_coefficients_are_rejected(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
) -> None:
    model = portable[3]["snapshot"]
    for coefficients in ([float("nan"), 1.0], [1.0], [1.0, 2.0, 3.0]):
        with pytest.raises(ValueError, match="ridge"):
            PortableResearchModel.model_validate({**model, "ridge_coefficients": coefficients})
    frozen = PortableResearchModel.model_validate(model)
    strike = Strike(strike_type=StrikeType.GREATER, floor=Decimal(65))
    with pytest.raises(ValueError, match="complete"):
        frozen.probability({"nws_pfm_max_f": 65.0}, strike)


def test_corrupt_portable_json_fails_loader_without_fallback(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
    tmp_path: Path,
) -> None:
    import shutil

    root, result, _, _ = portable
    copied = tmp_path / "research"
    shutil.copytree(root, copied)
    path = (
        copied
        / "experiments"
        / ("sha256-" + result["experiment_id"].removeprefix("sha256:"))
        / "ridge.paper.json"
    )
    payload = json.loads(path.read_text())
    payload["ridge_intercept"] += 1
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="checksum"):
        load_research_binding(copied, result["experiment_id"], "ridge", data_kind="synthetic")


def test_isotonic_export_preserves_interpolation_and_probability_tails(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
    tmp_path: Path,
) -> None:
    from sklearn.isotonic import IsotonicRegression  # type: ignore[import-untyped]

    root, result, _, binding = portable
    source = PortableResearchModel.model_validate(binding["snapshot"])
    path = root / "experiments" / ("sha256-" + result["experiment_id"].removeprefix("sha256:"))
    model = WeatherModel.load(path / "ridge.joblib", expected_hash=source.model_hash, trusted=True)
    estimator = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
    estimator.fit([0.0, 0.2, 0.4, 0.7, 1.0], [0.0, 0.1, 0.5, 0.8, 1.0])
    model.calibration = CDFCalibration(
        "isotonic", estimator, model.calibration.event_ids, model.calibration.fit_asof
    )
    digest = model.save(tmp_path / "isotonic.joblib")
    frozen = freeze_research_model(
        model,
        model_hash=digest,
        data_kind="synthetic",
        series=source.series,
        protected=source.protected_events,
        features=source.features,
        feature_artifacts=source.feature_artifacts,
        dataset_versions=source.dataset_versions,
        created_at=source.available_at,
        selected_schedule=source.selected_schedule,
    )
    features: dict[str, float | None] = {
        "nws_pfm_max_f": 65.0,
        "nws_cli_bias_f": 0.0,
        "forecast_high_f": 65.0,
    }
    for threshold in (-100, 60, 64, 65, 66, 70, 200):
        strike = Strike(strike_type=StrikeType.GREATER, floor=Decimal(threshold))
        assert frozen.probability(features, strike) == pytest.approx(
            model.predict_proba(features, strike, unit="degF"), abs=1e-12
        )


def test_tree_model_has_explicit_portable_refusal(
    portable: tuple[Path, dict[str, Any], StrategySpec, dict[str, Any]],
) -> None:
    source = PortableResearchModel.model_validate(portable[3]["snapshot"])
    with pytest.raises(ValueError, match="no reviewed portable"):
        freeze_research_model(
            WeatherModel("boosting"),
            model_hash=source.model_hash,
            data_kind="synthetic",
            series=source.series,
            protected=source.protected_events,
            features=source.features,
            feature_artifacts=source.feature_artifacts,
            dataset_versions=source.dataset_versions,
            created_at=source.available_at,
            selected_schedule=source.selected_schedule,
        )
