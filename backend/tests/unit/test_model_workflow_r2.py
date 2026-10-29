"""Connected Parquet → features → models → predictions → SQLite/MLflow proof."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from entropytrade.features.pipeline import build_features
from entropytrade.ml.experiment import ModelingConfig, run_modeling
from entropytrade.ml.forward import FrozenWeather
from entropytrade.ml.synthetic import synthetic_dataset


@pytest.fixture(scope="module")
def workflow(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any], Path]:
    root = tmp_path_factory.mktemp("r2-workflow")
    dataset = synthetic_dataset(root / "synthetic", days=300)
    manifest = build_features(
        dataset=dataset, archives=[], output=root / "features", data_kind="synthetic"
    )
    features = root / "features" / manifest["feature_version"].removeprefix("sha256:")
    result = run_modeling(
        features=features,
        output=root / "models",
        registry_path=root / "registry.sqlite",
        tracking=root / "mlflow",
        config=ModelingConfig(),
        data_kind="synthetic",
    )
    return root, result, features


def test_complete_models_and_predictions_are_grouped_and_holdout_protected(
    workflow: tuple[Path, dict[str, Any], Path],
) -> None:
    root, result, _ = workflow
    assert result["data_kind"] == "synthetic"
    assert result["status"] == "evaluated"
    assert result["independent_events"] == 600
    assert set(result["models"]) == {
        "climatology",
        "raw_forecast",
        "forecast_error",
        "ridge",
        "boosting",
    }
    assert not result["holdout_evaluated"]
    destination = root / "models" / result["run_id"].removeprefix("sha256:")
    predictions = [
        json.loads(line) for line in (destination / "predictions.jsonl").read_text().splitlines()
    ]
    assert len({p["prediction_id"] for p in predictions}) == len(predictions)
    holdout = set(result["split"]["holdout"])
    assert not any(p["event_id"] in holdout for p in predictions)
    for model in result["models"].values():
        assert model["metrics"]["validation"]["independent_events"] == 120
        assert model["metrics"]["validation"]["contracts"] == 480
    assert len(result["walk_forward"]) == 2
    for fold in result["walk_forward"]:
        assert set(fold["validation_events"]).isdisjoint(holdout)
        assert fold["models"]
    assert all(p["net_edge"] is None and p["executable_price"] is None for p in predictions)
    with closing(sqlite3.connect(root / "registry.sqlite")) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM probability_runs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM probability_predictions").fetchone()[
            0
        ] == len(predictions)
    assert list((root / "mlflow").rglob("meta.yaml"))


def test_modeling_exports_only_data_only_frozen_supported_models(
    workflow: tuple[Path, dict[str, Any], Path],
) -> None:
    root, result, _ = workflow
    destination = root / "models" / result["run_id"].removeprefix("sha256:")
    exports = sorted(destination.glob("*.forward.json"))
    assert {p.name for p in exports} == {
        "climatology.forward.json",
        "raw_forecast.forward.json",
        "forecast_error.forward.json",
    }
    for path in exports:
        model = FrozenWeather.model_validate_json(path.read_text())
        assert model.data_kind == "synthetic"
        assert model.model_hash == result["models"][model.family]["artifact_hash"]
        assert set(model.protected_events) == set(result["split"]["holdout"])
        assert set(model.training_events).isdisjoint(model.protected_events)


def test_repeated_builds_and_separate_runs_reproduce_hashes_and_registry(
    workflow: tuple[Path, dict[str, Any], Path],
) -> None:
    root, result, features = workflow
    rebuilt = build_features(
        dataset=root / "synthetic",
        archives=[],
        output=root / "features-again",
        data_kind="synthetic",
    )
    assert rebuilt["feature_version"] == "sha256:" + features.name
    second = run_modeling(
        features=features,
        output=root / "models-again",
        registry_path=root / "registry.sqlite",
        tracking=root / "mlflow",
        config=ModelingConfig(),
        data_kind="synthetic",
    )
    assert second == result
    cached = run_modeling(
        features=features,
        output=root / "models",
        registry_path=root / "registry.sqlite",
        tracking=root / "mlflow",
        config=ModelingConfig(),
        data_kind="synthetic",
    )
    assert cached == result
    with closing(sqlite3.connect(root / "registry.sqlite")) as connection, connection:
        assert connection.execute("SELECT COUNT(*) FROM probability_runs").fetchone()[0] == 1


def test_real_six_event_dataset_produces_insufficiency_not_synthetic_metrics(
    tmp_path: Path,
) -> None:
    source = Path("data/r1-demo/7be1ac67055e7abdc15bf90cdf093d257bde67f484440297add4428075c15b14")
    manifest = build_features(dataset=source, archives=[], output=tmp_path / "features")
    assert manifest["eligible_events"] == 0
    assert manifest["events_with_scalar_labels"] == 0
    features = tmp_path / "features" / manifest["feature_version"].removeprefix("sha256:")
    result = run_modeling(
        features=features,
        output=tmp_path / "models",
        registry_path=tmp_path / "registry.sqlite",
        tracking=tmp_path / "mlflow",
        config=ModelingConfig(),
    )
    assert result["status"] == "insufficient_data"
    assert result["independent_events"] == 6
    assert result["contracts"] == 36
    assert result["models"] == {}
    assert len(result["refusals"]) == 5
    assert result["coverage"]["missing_forecast_rows"] == 36
    assert pq.read_table(features / "features.parquet").num_rows == 36
    with pytest.raises(ValueError, match="must not be mixed"):
        build_features(dataset=source, archives=[], output=tmp_path / "bad", data_kind="synthetic")
