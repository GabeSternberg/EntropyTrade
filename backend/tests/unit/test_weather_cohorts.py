"""CONTROLLED multi-partition fitting and fail-closed data/restart invariants."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from entropytrade.agents.fixture import demo_specs
from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.experiments.data import WeatherPredictions
from entropytrade.ml.experiment import ModelingConfig, run_modeling
from entropytrade.weather.cohorts import build_cohort, partition_ids
from entropytrade.weather.history import build_snapshot, load_snapshot
from tests.integration.cohort_fixture import START, seed_cohort
from tests.integration.shadow_history_fixture import seed_authentic
from tests.integration.weather_history_retained import REPO


def ids(jobs: Jobs) -> list[str]:
    return [p["partition_id"] for p in jobs.weather_partitions()["partitions"]]


@pytest.mark.parametrize("value", [None, [], "a", ["a"], ["a"] * 9, [["a"]]])
def test_invalid_cohort_selections_are_refused(value: object) -> None:
    with pytest.raises(ValueError, match="select"):
        partition_ids(value)


def test_controlled_130_capture_cohort_fits_calibrates_evaluates_and_recovers() -> None:
    with TemporaryDirectory(prefix="cohort-positive-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        workspace = parent / "workspace"
        seed_cohort(workspace)
        jobs = Jobs(workspace)
        selected = ids(jobs)
        assert len(selected) == 2
        # Simulate interruption after the first bounded batch was published.
        original = build_snapshot
        calls = 0

        def interrupted(*args: Any, **kwargs: Any) -> object:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise InterruptedError("CONTROLLED interruption between batches")
            return original(*args, **kwargs)

        with (
            patch("entropytrade.weather.cohorts.build_snapshot", side_effect=interrupted),
            pytest.raises(InterruptedError, match="CONTROLLED interruption"),
        ):
            build_cohort(jobs, selected)
        output = workspace / "runs/weather-datasets"
        batches = list((output / ".batches").glob("[0-9a-f]" * 64))
        assert len(batches) == 1
        before = (batches[0] / "snapshot.json").read_bytes()
        result = build_cohort(Jobs(workspace), list(reversed(selected)))
        assert (batches[0] / "snapshot.json").read_bytes() == before
        assert len(list((output / ".batches").glob("[0-9a-f]" * 64))) == 2
        assert result["capture_count"] == 130
        ready = result["readiness"]
        assert ready["independent_events"] == 200
        assert ready["date_blocks"] == 100
        assert ready["protected_events"] == 20
        assert ready["status"] == "ready_for_model_gates", ready
        assert all(p["shortage"] == 0 for p in ready["partitions"].values())
        root = output / result["dataset_id"].removeprefix("sha256:")
        rows = pq.read_table(root / result["features"] / "features.parquet").to_pylist()
        assert len(rows) > ready["independent_events"]  # Repeated decisions aren't new events.
        protected = set(result["identity"]["protected_events"])
        assert all(
            r["outcome"] is None and r["temperature_target_f"] is None
            for r in rows
            if r["event_id"] in protected
        )
        assert all(
            not protected & set(json.loads(r["feature_evidence_json"])["bias_event_ids"])
            for r in rows
        )
        boundaries = tuple(
            START.fromisoformat(d) for d in result["identity"]["temporal_boundaries"]
        )
        config = ModelingConfig(boundaries=(boundaries[0], boundaries[1], boundaries[2]))
        kwargs: dict[str, Any] = {
            "features": root / result["features"],
            "registry_path": workspace / "registry.sqlite",
            "tracking": parent / "mlflow",
            "config": config,
        }
        modeled = run_modeling(output=parent / "models", **kwargs)
        assert modeled["status"] == "evaluated"
        assert modeled["models"]["forecast_error"]["calibration"] == "platt"
        assert modeled["models"]["ridge"]["metrics"]["validation"]["status"] == "evaluated"
        assert not modeled["holdout_evaluated"]
        assert not protected & {
            e for k in ("fit", "calibration", "validation") for e in modeled["split"][k]
        }
        reproduced = run_modeling(output=parent / "repeated-models", **kwargs)
        assert reproduced == modeled
        predictions = (
            parent / "models" / modeled["run_id"].removeprefix("sha256:") / "predictions.jsonl"
        )
        again = (
            parent
            / "repeated-models"
            / modeled["run_id"].removeprefix("sha256:")
            / "predictions.jsonl"
        )
        assert predictions.read_bytes() == again.read_bytes()
        assert build_cohort(jobs, selected) == result
        # Existing offline workspace machinery validates and preserves batches and final identity.
        archive = parent / "offline.zip"
        snapshot(REPO, workspace, archive)
        restored = parent / "restored"
        restore(REPO, archive, restored)
        reopened = build_cohort(Jobs(restored), selected)
        assert reopened == result
        assert load_snapshot(restored / root.relative_to(workspace)) == result


def test_missing_labels_and_inherited_protection_refuse_modeling(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    seed_cohort(workspace, labels=False)
    jobs = Jobs(workspace)
    result = build_cohort(jobs, ids(jobs))
    assert result["readiness"]["scalar_label_events"] == 0
    assert result["readiness"]["status"] == "insufficient_data"
    root = workspace / "runs/weather-datasets" / result["dataset_id"].removeprefix("sha256:")
    adapter = WeatherPredictions(
        root / result["features"],
        tmp_path / "models",
        tmp_path / "registry.sqlite",
        tmp_path / "mlflow",
        data_kind="real",
    )
    missing = adapter.prepare(demo_specs()[0], "forecast_error")
    assert not missing.records
    assert missing.refusals
    # Prior source protection propagates across batches and refuses before model fitting.
    event = f"KXHIGHPHIL-{START.strftime('%y%b%d').upper()}"
    captures, _, _ = jobs.weather_inputs(ids(jobs)[0])
    build_snapshot(
        workspace / "runs/weather-datasets", captures, protected_events=frozenset({event})
    )
    protected_cohort = build_cohort(jobs, ids(jobs))
    assert event in protected_cohort["identity"]["protected_events"]
    assert any("Source-protected" in r for r in protected_cohort["readiness"]["blockers"])
    adapter.features = (
        workspace
        / "runs/weather-datasets"
        / protected_cohort["dataset_id"].removeprefix("sha256:")
        / protected_cohort["features"]
    )
    adapter.protected_events = frozenset(protected_cohort["identity"]["protected_events"])
    adapter.cache.clear()
    with pytest.raises(ValueError, match="protected boundary overlaps"):
        adapter.prepare(demo_specs()[0], "forecast_error")
    with pytest.raises(ValueError, match="changed or is unknown"):
        build_cohort(jobs, ["a" * 64])
    with (
        patch("entropytrade.weather.cohorts.MAX_BYTES", 1),
        pytest.raises(ValueError, match="256 MB"),
    ):
        build_cohort(jobs, ids(jobs))


def test_authentic_cohort_remains_insufficient_without_changing_receipts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    seed_authentic(workspace)
    original = {
        p.relative_to(workspace): p.read_bytes()
        for p in (workspace / "shadow").rglob("*")
        if p.is_file()
    }
    result = build_cohort(Jobs(workspace), ids(Jobs(workspace)))
    assert result["readiness"]["independent_events"] == 4
    assert result["readiness"]["scalar_label_events"] == 0
    assert result["readiness"]["status"] == "insufficient_data"
    assert all((workspace / p).read_bytes() == body for p, body in original.items())
    root = workspace / "runs/weather-datasets" / result["dataset_id"].removeprefix("sha256:")
    projection = json.loads((root / "shadow-replay.json").read_text())
    assert len(projection["cycles"]) == 2
    assert all(not c["prediction_bundle"]["records"] for c in projection["cycles"])
