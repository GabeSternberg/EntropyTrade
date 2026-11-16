"""Causal, reproducible acquired-feature modeling; synthetic evidence is explicit."""

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from entropytrade.data.sources import file_hash
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.models import WeatherModel
from entropytrade.research.model import FeatureNeed
from entropytrade.research.modeling import plan_hypothesis, run_hypothesis
from entropytrade.research.registry import FeatureRegistry
from tests.research_modeling_support import MODEL_NOW, modeling_fixture


def rewrite(
    root: Path, artifact: dict[str, Any], change: Callable[[list[dict[str, Any]]], None]
) -> dict[str, Any]:
    """Republish changed input rows under a new valid immutable content identity."""
    path = root / "features" / ("sha256-" + artifact["artifact_id"].removeprefix("sha256:"))
    manifest: dict[str, Any] = json.loads((path / "manifest.json").read_text())
    rows = [json.loads(line) for line in (path / "values.jsonl").read_text().splitlines()]
    change(rows)
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    from hashlib import sha256

    manifest["values"] = "sha256:" + sha256(body.encode()).hexdigest()
    identity = {
        k: manifest[k]
        for k in (
            "feature_id",
            "version",
            "definition_hash",
            "entity",
            "schedule",
            "window",
            "input_datasets",
            "values",
        )
    }
    manifest["artifact_id"] = scientific_hash(identity)
    target = root / "features" / ("sha256-" + manifest["artifact_id"].removeprefix("sha256:"))
    target.mkdir()
    (target / "values.jsonl").write_text(body)
    (target / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_acquired_features_fit_existing_models_and_validate_independently(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    planned = plan_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        data_kind="synthetic",
    )
    assert planned["freeze_ready"]
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "evaluated"
    assert result["data_kind"] == "synthetic"
    assert set(result["models"]) == {"ridge", "forecast_error", "climatology", "raw_forecast"}
    assert result["models"]["ridge"]["calibration"] == "platt"
    assert 0 <= result["models"]["ridge"]["metrics"]["brier"] <= 1
    assert result["models"]["ridge"]["metrics"]["log_loss"] >= 0
    comparison = result["validation"]["baseline_comparisons"]["ridge"]
    assert comparison["paired_events"] == 44
    assert (
        comparison["improvement_interval"]["lower"] <= comparison["improvement_interval"]["upper"]
    )
    assert comparison["selection_adjusted"] is False
    assert set(result["validation"]["sensitivity"]["ridge"]) == {
        "uncalibrated",
        "threshold_minus_5f",
        "threshold_plus_5f",
        "forecast_minus_1f",
        "forecast_plus_1f",
    }
    assert result["validation"]["holdout_evaluated"] is False
    assert result["validation"]["prospective"] is False
    partitions = result["validation"]["partitions"]
    assert set(partitions["fit"]).isdisjoint(partitions["validation"])
    assert set(partitions["calibration"]).isdisjoint(partitions["holdout"])
    assert result["backtest"]["eligible"] is False
    assert result["backtest"]["execution_fidelity"] == "predictive_only"
    assert result["backtest"]["submission_enabled"] is False
    destination = (
        tmp_path / "experiments" / ("sha256-" + result["experiment_id"].removeprefix("sha256:"))
    )
    fitted = WeatherModel.load(
        destination / "ridge.joblib",
        expected_hash=result["models"]["ridge"]["artifact_hash"],
        trusted=True,
    )
    assert set(fitted.training_events).isdisjoint(partitions["holdout"])
    assert fitted.feature_names == ("nws_pfm_max_f", "nws_cli_bias_f")
    assert file_hash(tmp_path / result["report"]["path"]) == result["report"]["hash"]


def test_identical_experiment_reuses_verified_artifacts(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    kwargs = {
        "root": tmp_path,
        "registry": FeatureRegistry(),
        "spec": spec,
        "artifacts": artifacts,
        "now": MODEL_NOW,
        "data_kind": "synthetic",
    }
    first = run_hypothesis(**kwargs)  # type: ignore[arg-type]
    second = run_hypothesis(**kwargs)  # type: ignore[arg-type]
    assert first == second
    assert len(list((tmp_path / "experiments").glob("sha256-*"))) == 1


def test_late_authentic_style_label_receipts_never_enter_historical_training(
    tmp_path: Path,
) -> None:
    spec, artifacts = modeling_fixture(tmp_path, late_labels=True)
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "awaiting_data"
    assert result["eligibility"]["train_eligible_events"] == 0
    assert result["eligibility"]["training_late_labels"] > 0
    assert "cannot be backdated" in result["eligibility"]["reasons"][0]
    assert not result["models"]


@pytest.mark.parametrize("days", [7, 30])
def test_insufficient_events_keep_unfrozen_durable_refusal(tmp_path: Path, days: int) -> None:
    spec, artifacts = modeling_fixture(tmp_path, days=days)
    planned = plan_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        data_kind="synthetic",
    )
    assert planned["freeze_ready"] is False
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "awaiting_data"
    assert result["eligibility"]["reasons"]


def test_single_class_target_refuses_training(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path, constant_targets=True)
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "awaiting_data"
    assert "Single-class" in result["eligibility"]["reasons"][0]
    assert result["models"] == {}


def test_calibration_shortfall_does_not_freeze_before_later_evidence_can_resume(
    tmp_path: Path,
) -> None:
    spec, artifacts = modeling_fixture(tmp_path, days=150)
    early = plan_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        data_kind="synthetic",
    )
    assert not early["freeze_ready"]
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "awaiting_data"
    assert "calibration events" in result["eligibility"]["reasons"][0]
    assert result["models"] == {}
    _, grown = modeling_fixture(tmp_path, days=220)
    later = plan_hypothesis(
        root=tmp_path, registry=FeatureRegistry(), spec=spec, artifacts=grown, data_kind="synthetic"
    )
    assert later["freeze_ready"]
    assert early["experiment_id"] != later["experiment_id"]


def test_unknown_feature_is_never_mapped_to_a_supported_predictor(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    spec = spec.revalidated(features=(FeatureNeed(name="fictional_signal"),), rules=())
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "unsupported"
    assert "Unregistered feature" in result["eligibility"]["reasons"][0]


def test_future_information_in_feature_is_refused_even_with_valid_content_hash(
    tmp_path: Path,
) -> None:
    spec, artifacts = modeling_fixture(tmp_path)

    def future(rows: list[dict[str, Any]]) -> None:
        rows[0]["inputs_available_at"] = "2027-01-01T00:00:00+00:00"

    artifacts[0] = rewrite(tmp_path, artifacts[0], future)
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "invalid"
    assert "future-information leakage" in result["eligibility"]["reasons"][0]


def test_synthetic_input_cannot_be_presented_as_authentic(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    result = run_hypothesis(
        root=tmp_path, registry=FeatureRegistry(), spec=spec, artifacts=artifacts, now=MODEL_NOW
    )
    assert result["status"] == "invalid"
    assert "synthetic/authentic" in result["eligibility"]["reasons"][0]


def test_rehashed_row_cannot_change_the_declared_decision_schedule(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)

    def change(rows: list[dict[str, Any]]) -> None:
        rows[0]["decision_time"] = "2026-01-01T23:59:00+00:00"

    artifacts[0] = rewrite(tmp_path, artifacts[0], change)
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "invalid"
    assert "frozen hypothesis schedule" in result["eligibility"]["reasons"][0]


def test_cached_model_does_not_hide_corrupted_original_raw_evidence(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    next((tmp_path / "raw").glob("*/*")).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="raw response checksum"):
        run_hypothesis(
            root=tmp_path,
            registry=FeatureRegistry(),
            spec=spec,
            artifacts=artifacts,
            now=MODEL_NOW,
            data_kind="synthetic",
        )


def test_manifest_cannot_remove_original_response_verification(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    path = next((tmp_path / "datasets").glob("*/manifest.json"))
    manifest = json.loads(path.read_text())
    manifest["raw_hashes"] = []
    path.write_text(json.dumps(manifest))
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    assert result["status"] == "invalid"
    assert "raw response inventory" in result["eligibility"]["reasons"][0]


def test_corrupted_model_artifact_is_not_reused(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    result = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    path = tmp_path / "experiments" / ("sha256-" + result["experiment_id"].removeprefix("sha256:"))
    (path / "ridge.joblib").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="experiment artifact checksum"):
        run_hypothesis(
            root=tmp_path,
            registry=FeatureRegistry(),
            spec=spec,
            artifacts=artifacts,
            now=MODEL_NOW,
            data_kind="synthetic",
        )


def test_protected_targets_never_change_metrics_and_growing_windows_keep_boundaries(
    tmp_path: Path,
) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    first = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=artifacts,
        now=MODEL_NOW,
        data_kind="synthetic",
    )
    boundaries = (
        date.fromisoformat(first["boundaries"][0]),
        date.fromisoformat(first["boundaries"][1]),
        date.fromisoformat(first["boundaries"][2]),
    )
    _, grown = modeling_fixture(tmp_path, days=300)

    def hostile(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            if row["target_date"] >= first["boundaries"][2]:
                row.update(value="not-a-number", inputs_available_at="2099-01-01T00:00:00+00:00")

    grown[-1] = rewrite(tmp_path, grown[-1], hostile)
    second = run_hypothesis(
        root=tmp_path,
        registry=FeatureRegistry(),
        spec=spec,
        artifacts=grown,
        now=MODEL_NOW,
        data_kind="synthetic",
        boundaries=boundaries,
    )
    assert second["status"] == "evaluated"
    assert first["models"] == second["models"]
    assert first["validation"]["uncertainty"] == second["validation"]["uncertainty"]
    assert first["validation"]["walk_forward"] == second["validation"]["walk_forward"]
    for fold in second["validation"]["walk_forward"]:
        for group in ("fit", "calibration", "validation"):
            assert all(
                event.split(":")[-1] < first["boundaries"][2] for event in fold["partitions"][group]
            )


def test_cancellation_leaves_no_completed_experiment(tmp_path: Path) -> None:
    spec, artifacts = modeling_fixture(tmp_path)
    with pytest.raises(InterruptedError):
        run_hypothesis(
            root=tmp_path,
            registry=FeatureRegistry(),
            spec=spec,
            artifacts=artifacts,
            now=MODEL_NOW,
            data_kind="synthetic",
            cancelled=lambda: True,
        )
    assert not list((tmp_path / "experiments").glob("sha256-*"))


def test_model_failure_is_not_replaced_by_fabricated_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, artifacts = modeling_fixture(tmp_path)

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("training worker failed")

    monkeypatch.setattr(WeatherModel, "fit", fail)
    with pytest.raises(RuntimeError, match="training worker failed"):
        run_hypothesis(
            root=tmp_path,
            registry=FeatureRegistry(),
            spec=spec,
            artifacts=artifacts,
            now=MODEL_NOW,
            data_kind="synthetic",
        )
    assert not list((tmp_path / "experiments").glob("sha256-*"))
