"""Causal bridge and sustained restore evidence. Controlled cases are not empirical performance."""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.experiments.data import ExperimentData, weather_data
from entropytrade.features.registry import scientific_hash
from entropytrade.tracking.history import anchor, verified_inputs
from entropytrade.tracking.replay import reproduce, verify
from entropytrade.weather.history import build_snapshot, load_snapshot
from tests.integration.shadow_history_fixture import seed_sustained
from tests.integration.weather_history_retained import REPO, SOURCE


def freeze(jobs: Jobs, capture: str, outcomes: str | None = None) -> dict[str, Any]:
    captures, labels, protected = jobs.weather_inputs(capture, outcomes)
    return build_snapshot(
        jobs.root / "runs/weather-datasets",
        captures,
        outcome_roots=labels,
        protected_events=protected,
        frozen_anchor=anchor(jobs),
        selection={"partition_id": capture, "outcome_partition_id": outcomes or capture},
    )


def test_130_collector_cycles_partition_restart_and_offline_restore() -> None:
    # Actual collector/engine/store with CONTROLLED wire sources and simulated clocks.
    with TemporaryDirectory(prefix="sustained-", dir=REPO / "data/cache") as directory:
        parent = Path(directory)
        workspace = parent / "workspace"
        receipt = seed_sustained(workspace)
        jobs = Jobs(workspace)
        catalog = jobs.weather_partitions()
        assert catalog == receipt["catalog"]
        assert catalog["total_inputs"] == 130
        assert [p["inputs"] for p in catalog["partitions"]] == [128, 2]
        assert len({m["id"] for p in catalog["partitions"] for m in p["members"]}) == 130
        with pytest.raises(ValueError, match="select a browser"):
            jobs.weather_inputs()
        with pytest.raises(ValueError, match="changed or is unknown"):
            jobs.weather_inputs("a" * 64)
        first, later = [p["partition_id"] for p in catalog["partitions"]]
        # Select the later page first: calendar protection still starts at the global anchor.
        later_inputs, _, _ = jobs.weather_inputs(later)
        from entropytrade.families.public import forward_data

        assert all(
            s.target_date.isoformat() == "2026-10-27"
            for p in later_inputs
            for s in forward_data(p).samples
        )
        last = freeze(jobs, later)
        original = freeze(jobs, first, later)
        assert (
            original["identity"]["temporal_boundaries"] == last["identity"]["temporal_boundaries"]
        )
        assert original["identity"]["anchor"] == "2026-10-25"
        root = workspace / "runs/weather-datasets" / original["dataset_id"].removeprefix("sha256:")
        data = weather_data(root / original["features"])
        assert len(data.samples) == 128
        assert all(s.book is not None and s.outcome is not None for s in data.samples)
        replay = json.loads((root / "shadow-replay.json").read_text())
        assert len(replay["cycles"]) == 128
        for cycle in replay["cycles"]:
            evidence = root / cycle["evidence"]
            assert verify(evidence)["verified"]
            inputs = verified_inputs(evidence)
            saved = json.loads((evidence / "result.json").read_text())
            assert json.loads(json.dumps(reproduce(inputs))) == saved["decisions"]
            projected = ExperimentData.model_validate(cycle["experiment_data"])
            assert all(
                s.outcome_available_at and s.outcome_available_at > s.decision_time
                for s in projected.samples
            )
            assert all(s.book and s.book.received_at <= s.decision_time for s in projected.samples)
            assert {s.feature_hash for s in projected.samples} == {
                s["feature_hash"] for s in inputs["data"]["samples"]
            }
            assert all(
                row["intent"] is None and "certified_fees" in row["reasons"]
                for row in saved["decisions"]
            )
        before = {
            p.relative_to(workspace).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file()
        }
        archive = parent / "offline.zip"
        snapshot(REPO, workspace, archive)
        destination = parent / "restored"
        restore(REPO, archive, destination)
        reopened = Jobs(destination)
        assert reopened.weather_partitions() == catalog
        assert freeze(reopened, first, later) == original
        assert len(list((destination / "shadow" / receipt["monitor_id"]).iterdir())) == 130
        assert all((destination / name).read_bytes() == body for name, body in before.items())
        # Positive labels existed above; protection must remove them from BOTH bridges.
        captures, labels, inherited = reopened.weather_inputs(first, later)
        protected_event = data.samples[0].event_id
        excluded = build_snapshot(
            destination / "runs/weather-datasets",
            captures,
            outcome_roots=labels,
            protected_events=inherited | frozenset({protected_event}),
            frozen_anchor=anchor(reopened),
        )
        excluded_root = (
            destination / "runs/weather-datasets" / excluded["dataset_id"].removeprefix("sha256:")
        )
        excluded_data = weather_data(excluded_root / excluded["features"])
        assert all(
            s.outcome is None and s.outcome_available_at is None for s in excluded_data.samples
        )
        assert excluded["readiness"]["binary_label_events"] == 0
        projected = json.loads((excluded_root / "shadow-replay.json").read_text())
        assert all(not c["experiment_data"]["samples"] for c in projected["cycles"])
        assert all(not c["saved_decisions"] for c in projected["cycles"])
        assert all(not c["prediction_bundle"]["records"] for c in projected["cycles"])
        assert load_snapshot(root) == original


def test_authentic_shadow_books_and_decision_clocks_survive_bridge(tmp_path: Path) -> None:
    captures = sorted(SOURCE.glob("*/*/public"))
    manifest = build_snapshot(tmp_path / "datasets", captures)
    root = tmp_path / "datasets" / manifest["dataset_id"].removeprefix("sha256:")
    data = weather_data(root / manifest["features"])
    originals = [ExperimentData.model_validate(verified_inputs(p.parent)["data"]) for p in captures]
    expected = {(s.ticker, s.decision_time): s for d in originals for s in d.samples}
    assert {(s.ticker, s.decision_time) for s in data.samples} == set(expected)
    assert all(s.book == expected[s.ticker, s.decision_time].book for s in data.samples)
    assert all(s.outcome is None for s in data.samples)
    assert manifest["readiness"]["status"] == "insufficient_data"
    assert manifest["readiness"]["scalar_label_events"] == 0
    assert manifest["shadow_audit"]["verified_cycles"] == 2
    # Entire snapshot is independently loadable without the original workspace.
    assert load_snapshot(root) == manifest


def test_protected_binary_labels_and_shadow_projection_are_excluded(tmp_path: Path) -> None:
    captures = sorted(SOURCE.glob("*/*/public"))
    event = json.loads((captures[0].parent / "decision-inputs.json").read_text())["data"][
        "samples"
    ][0]["event_id"]
    result = build_snapshot(tmp_path / "datasets", captures, protected_events=frozenset({event}))
    root = tmp_path / "datasets" / result["dataset_id"].removeprefix("sha256:")
    replay = json.loads((root / "shadow-replay.json").read_text())
    assert all(
        s["event_id"] != event for c in replay["cycles"] for s in c["experiment_data"]["samples"]
    )
    assert all(
        s.outcome is None
        for s in weather_data(root / result["features"]).samples
        if s.event_id == event
    )


def rehash_cycle(root: Path) -> None:
    from entropytrade.data.sources import file_hash

    result = json.loads((root / "result.json").read_text())
    inputs = json.loads((root / "decision-inputs.json").read_text())
    result["decisions"] = reproduce(inputs)
    for artifact in result["artifacts"]:
        path = root / artifact["path"]
        artifact.update(sha256=file_hash(path), bytes=path.stat().st_size)
    (root / "result.json").write_text(json.dumps(result))


def test_controlled_post_close_decisions_remain_receipts_but_cannot_enter_models(
    tmp_path: Path,
) -> None:
    # CONTROLLED execution clock after close. Original source receipt clocks never change.
    from decimal import Decimal

    from entropytrade.families.public import forward_data

    captures = sorted(SOURCE.glob("*/*/public"))
    root = tmp_path / "controlled-closed"
    shutil.copytree(captures[0].parent, root)
    original = forward_data(root / "public")
    at = max(s.close_time for s in original.samples) + timedelta(hours=1)
    inputs = json.loads((root / "decision-inputs.json").read_text())
    originals = {s.ticker: s for s in original.samples}
    for sample in inputs["data"]["samples"]:
        close = datetime.fromisoformat(sample["close_time"].replace("Z", "+00:00"))
        sample["decision_time"] = at.isoformat()
        sample["features"]["hours_to_close"] = str(
            Decimal(str((close - at).total_seconds())) / Decimal(3600)
        )
        sample["feature_hash"] = scientific_hash(
            {
                "source_features": originals[sample["ticker"]].feature_hash,
                "decision": at.isoformat(),
                "features": sample["features"],
            }
        )
    (root / "decision-inputs.json").write_text(json.dumps(inputs))
    summary = json.loads((root / "execution/summary.json").read_text())
    summary["decision_time"] = at.isoformat()
    (root / "execution/summary.json").write_text(json.dumps(summary))
    result = json.loads((root / "result.json").read_text())
    result["execution"] = summary
    (root / "result.json").write_text(json.dumps(result))
    rehash_cycle(root)
    assert verified_inputs(root)
    frozen = build_snapshot(tmp_path / "datasets", [root / "public", captures[1]])
    dataset = tmp_path / "datasets" / frozen["dataset_id"].removeprefix("sha256:")
    data = weather_data(dataset / frozen["features"])
    assert data.samples
    assert all(s.decision_time < s.close_time for s in data.samples)
    assert all(s.decision_time != at for s in data.samples)
    projection = json.loads((dataset / "shadow-replay.json").read_text())
    closed = [
        d
        for c in projection["cycles"]
        for d in c["saved_decisions"]
        if d["decision_time"] == at.isoformat()
    ]
    assert closed
    assert all("open_market" in d["reasons"] and d["intent"] is None for d in closed)
    assert frozen["shadow_audit"]["closed_decisions"] == len(closed)


@pytest.mark.parametrize("fault", ["source_version", "source_kind", "features", "book", "clock"])
def test_self_consistent_replay_cannot_forge_causal_source_binding(
    tmp_path: Path, fault: str
) -> None:
    source = next(
        p
        for p in SOURCE.glob("*/*")
        if json.loads((p / "execution/summary.json").read_text())["book_count"]
    )
    root = tmp_path / "controlled-tampering"
    shutil.copytree(source, root)
    inputs = json.loads((root / "decision-inputs.json").read_text())
    sample = next(s for s in inputs["data"]["samples"] if s["book"])
    if fault == "source_version":
        inputs["data"]["feature_version"] = scientific_hash({"forged": True})
    elif fault == "source_kind":
        inputs["data"]["data_kind"] = "synthetic"
    elif fault == "features":
        sample["features"]["forecast_high_f"] = "999"
    elif fault == "book":
        sample["book"]["asks"][0]["quantity"] = "999"
    else:
        sample["decision_time"] = (
            datetime.fromisoformat(sample["decision_time"].replace("Z", "+00:00"))
            + timedelta(seconds=1)
        ).isoformat()
    (root / "decision-inputs.json").write_text(json.dumps(inputs))
    rehash_cycle(root)
    assert verify(root)["verified"]  # Replay consistency alone cannot establish source truth.
    with pytest.raises(
        ValueError, match=r"shadow (source version|decision clock/features|book differs)"
    ):
        verified_inputs(root)


@pytest.mark.parametrize(
    "fault",
    ["stale_depth", "future_exchange", "missing_labels", "uncertified_fees", "forward_predictions"],
)
def test_controlled_experiment_refusals_remain_explicit(fault: str) -> None:
    # CONTROLLED execution accounting only; generated family fixture is not market support.
    from entropytrade.experiments.data import RecordedPredictions
    from entropytrade.experiments.engine import evaluate_candidate
    from tests.r4_support import nonweather

    data, provider, research, config = nonweather()
    if fault in {"stale_depth", "future_exchange", "missing_labels"}:
        samples = []
        for sample in data.samples:
            book = sample.book
            assert book is not None
            if fault == "stale_depth":
                sample = sample.revalidated(
                    book=book.revalidated(received_at=sample.decision_time - timedelta(seconds=61))
                )
            elif fault == "future_exchange":
                sample = sample.revalidated(
                    book=book.revalidated(exchange_ts=sample.decision_time + timedelta(seconds=1))
                )
            else:
                sample = sample.revalidated(outcome=None, outcome_available_at=None)
            samples.append(sample)
        data = data.revalidated(samples=tuple(samples))
    elif fault == "uncertified_fees":
        assert config.fee_policy is not None
        data = data.revalidated(data_kind="real")
        provider = RecordedPredictions(
            provider.bundle.revalidated(
                model_metadata={**provider.bundle.model_metadata, "data_kind": "real"}
            )
        )
        config = config.revalidated(fee_policy=config.fee_policy.revalidated(certified=False))
    else:
        provider = RecordedPredictions(
            provider.bundle.revalidated(
                records=tuple(p.revalidated(partition="forward") for p in provider.bundle.records)
            )
        )
    result = evaluate_candidate(research["candidates"][0], research, data, provider, config)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert not result["tested"]
    assert result["scenarios"] == []
    expected = {
        "stale_depth": "depth is stale",
        "future_exchange": "future exchange clock",
        "missing_labels": "labels or known rules",
        "uncertified_fees": "fee schedule unavailable",
        "forward_predictions": "no permitted validation predictions",
    }
    assert any(expected[fault] in reason for reason in result["reasons"])
