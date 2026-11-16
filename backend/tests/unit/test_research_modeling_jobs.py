"""Durable C orchestration, separate from statistical model correctness tests."""

from pathlib import Path
from typing import Any

import pytest

from entropytrade.research.model import JobStatus
from entropytrade.research.service import ResearchService
from tests.unit.test_research_jobs import NOW, service, submit


def modeling_job(tmp_path: Path) -> tuple[ResearchService, str]:
    svc = service(tmp_path)
    job_id = submit(svc)
    for _ in range(10):
        job = svc.store.get_job(job_id)
        assert job is not None
        if job["status"] == JobStatus.MODELING:
            return svc, job_id
        svc.step()
    raise AssertionError("research never reached its modeling checkpoint")


def test_missing_evidence_refusals_are_persistent_and_deduplicated(tmp_path: Path) -> None:
    svc, job_id = modeling_job(tmp_path)
    svc.run_until_idle()
    rows = svc.store.experiments(job_id)
    assert len(rows) == 5
    assert all(r["status"] == "refused" and r["result"] for r in rows)
    assert all(r["result"]["backtest"]["submission_enabled"] is False for r in rows)
    assert svc.detail(job_id)["submission_enabled"] is False  # type: ignore[index]
    restarted = service(tmp_path)
    restarted.recover()
    assert restarted.store.experiments(job_id) == rows
    restarted.resume(job_id)
    restarted.run_until_idle()
    assert restarted.store.experiments(job_id) == rows
    report = restarted.report(job_id)
    assert report is not None
    assert report["job"]["experiments"] == rows


def test_start_and_late_completion_cannot_outlive_cancellation(tmp_path: Path) -> None:
    svc, job_id = modeling_job(tmp_path)
    store = svc.store
    store.plan_experiment(job_id, "x", "h", {}, now=NOW)
    assert store.start_experiment(job_id, "x", now=NOW)
    assert svc.cancel(job_id)
    assert not store.finish_experiment(
        job_id, "x", status="completed", result={"status": "completed"}, now=NOW
    )
    store.plan_experiment(job_id, "late", "h", {}, now=NOW)
    assert not store.start_experiment(job_id, "late", now=NOW)
    assert [(r["id"], r["status"]) for r in store.experiments(job_id)] == [("x", "cancelled")]


def test_restart_requeues_running_experiment_without_duplicate_identity(tmp_path: Path) -> None:
    from entropytrade.research.model import HypothesisSpec
    from entropytrade.research.modeling import plan_hypothesis

    svc, job_id = modeling_job(tmp_path)
    spec = HypothesisSpec.model_validate(svc.store.hypotheses(job_id)[0]["spec"])
    plan = plan_hypothesis(
        root=svc.store.root,
        registry=svc.registry,
        spec=spec,
        artifacts=[],
        validation_depth="standard",
    )
    svc.store.plan_experiment(job_id, plan["experiment_id"], spec.hypothesis_id, plan, now=NOW)
    assert svc.store.start_experiment(job_id, plan["experiment_id"], now=NOW)
    restarted = service(tmp_path)
    restarted.recover()
    assert restarted.store.experiments(job_id)[0]["status"] == "queued"
    restarted.run_until_idle()
    rows = restarted.store.experiments(job_id)
    assert len(rows) == 5
    assert rows[0]["attempts"] == 2
    assert all(r["status"] == "refused" for r in rows)


def test_training_error_retries_existing_experiment_and_preserves_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.research import modeling

    svc, job_id = modeling_job(tmp_path)
    original = modeling.run_hypothesis

    def fail(**_: Any) -> dict[str, Any]:
        raise ArithmeticError("private external content should never enter the report")

    monkeypatch.setattr(modeling, "run_hypothesis", fail)
    svc.step()
    job = svc.store.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.RECOVERABLE_ERROR
    assert job["error"]["type"] == "ArithmeticError"
    row = svc.store.experiments(job_id)[0]
    assert row["status"] == "failed"
    assert "private external" not in str(svc.report(job_id))
    monkeypatch.setattr(modeling, "run_hypothesis", original)
    svc.resume(job_id)
    svc.run_until_idle()
    rows = svc.store.experiments(job_id)
    assert len(rows) == 5
    assert rows[0]["status"] == "refused"
    assert rows[0]["attempts"] == 2
    assert rows[0]["error"] is None


def test_runtime_budget_stops_before_any_fit(tmp_path: Path) -> None:
    svc, job_id = modeling_job(tmp_path)
    svc.store.add_usage(job_id, runtime_seconds=100_000)
    svc.step()
    job = svc.store.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.FAILED
    assert svc.store.experiments(job_id) == []


def test_validation_boundaries_survive_new_jobs_and_expanded_windows(tmp_path: Path) -> None:
    svc = service(tmp_path)
    original = ["2026-08-01", "2026-09-01", "2026-10-01"]
    assert svc.store.freeze_boundaries("weather-phil", original, now=NOW) == original
    assert (
        svc.store.freeze_boundaries(
            "weather-phil", ["2026-09-01", "2026-10-01", "2026-11-01"], now=NOW
        )
        == original
    )
    assert service(tmp_path).store.freeze_boundaries("weather-phil", [], now=NOW) == original
    with pytest.raises(ValueError, match="ordered"):
        svc.store.freeze_boundaries("bad", list(reversed(original)), now=NOW)


def test_cancellation_during_fitting_refuses_late_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.research import modeling

    svc, job_id = modeling_job(tmp_path)

    def cancel(**_: Any) -> dict[str, Any]:
        svc.cancel(job_id)
        return {"status": "completed"}

    monkeypatch.setattr(modeling, "run_hypothesis", cancel)
    svc.step()
    row = svc.store.experiments(job_id)[0]
    assert row["status"] == "cancelled"
    assert row["result"] is None
    assert svc.store.get_job(job_id)["status"] == JobStatus.CANCELLED  # type: ignore[index]


def synthetic_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, days: int = 220
) -> tuple[ResearchService, str]:
    from entropytrade.domain.time import SimulatedClock
    from entropytrade.research import modeling
    from entropytrade.research.model import HypothesisStatus
    from tests.research_modeling_support import MODEL_NOW, modeling_fixture
    from tests.unit.test_research_jobs import REPO

    original_plan, original_run = modeling.plan_hypothesis, modeling.run_hypothesis
    original_verify = modeling.verify_hypothesis

    def plan(**kwargs: Any) -> dict[str, Any]:
        return original_plan(**(kwargs | {"data_kind": "synthetic"}))

    def run(**kwargs: Any) -> dict[str, Any]:
        return original_run(**(kwargs | {"data_kind": "synthetic"}))

    def verify(**kwargs: Any) -> dict[str, Any]:
        return original_verify(**(kwargs | {"data_kind": "synthetic"}))

    # Test-only evidence adapter. Production always requests authentic datasets.
    monkeypatch.setattr(modeling, "plan_hypothesis", plan)
    monkeypatch.setattr(modeling, "run_hypothesis", run)
    monkeypatch.setattr(modeling, "verify_hypothesis", verify)
    svc = ResearchService(tmp_path / "workspace", REPO, clock=SimulatedClock(MODEL_NOW))
    job_id = submit(svc)
    spec, artifacts = modeling_fixture(svc.store.root, days=days)
    svc.store.save_hypotheses(job_id, [(spec, HypothesisStatus.PROPOSED, (), "")], now=MODEL_NOW)
    for manifest in artifacts:
        svc.store.register_feature(job_id, manifest, [spec.hypothesis_id], now=MODEL_NOW)
    for status in (
        JobStatus.GENERATING,
        JobStatus.PLANNING,
        JobStatus.FEATURIZING,
        JobStatus.MODELING,
    ):
        svc.store.transition(job_id, status, "Controlled synthetic fixture", now=MODEL_NOW)
    return svc, job_id


def test_eligible_synthetic_model_reaches_persistent_results_and_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.features.registry import scientific_hash

    svc, job_id = synthetic_job(tmp_path, monkeypatch)
    svc.run_until_idle()
    row = svc.store.experiments(job_id)[0]
    assert row["status"] == "completed"
    result = row["result"]
    assert result["status"] == "evaluated"
    assert result["experiment_id"] == row["id"]
    assert result["data_kind"] == "synthetic"
    assert "ridge" in result["models"]
    assert result["models"]["ridge"]["metrics"]["brier"] >= 0
    assert result["backtest"]["eligible"] is False
    assert result["backtest"]["performance"] is None
    assert result["validation"]["holdout_evaluated"] is False
    assert result["validation"]["prospective"] is False
    bounds = svc.store.freeze_boundaries(scientific_hash({"family": "weather"}), [], now=NOW)
    assert bounds == result["boundaries"]
    assert svc.store.get_job(job_id)["status"] == JobStatus.EVALUATED  # type: ignore[index]
    restarted = service(tmp_path)
    restarted.recover()
    assert restarted.store.experiments(job_id) == [row]


def test_insufficient_data_does_not_freeze_unusable_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.features.registry import scientific_hash
    from tests.research_modeling_support import MODEL_NOW, modeling_fixture

    svc, job_id = synthetic_job(tmp_path, monkeypatch, days=30)
    svc.run_until_idle()
    assert svc.store.experiments(job_id)[0]["status"] == "refused"
    scope = scientific_hash({"family": "weather"})
    assert svc.store.freeze_boundaries(scope, [], now=NOW) == []
    # New verified evidence can make this same durable job eligible.
    spec, artifacts = modeling_fixture(svc.store.root, days=220)
    for manifest in artifacts:
        svc.store.register_feature(job_id, manifest, [spec.hypothesis_id], now=MODEL_NOW)
    svc.store.transition(job_id, JobStatus.PLANNING, "New synthetic evidence", now=MODEL_NOW)
    svc.store.transition(job_id, JobStatus.FEATURIZING, "New synthetic features", now=MODEL_NOW)
    svc.store.transition(job_id, JobStatus.MODELING, "Reevaluate synthetic evidence", now=MODEL_NOW)
    svc.run_until_idle()
    rows = svc.store.experiments(job_id)
    assert len(rows) == 2
    assert rows[-1]["status"] == "completed"
    assert svc.store.freeze_boundaries(scope, [], now=NOW)


def test_resume_refuses_corrupt_completed_model_instead_of_reusing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, job_id = synthetic_job(tmp_path, monkeypatch)
    svc.run_until_idle()
    row = svc.store.experiments(job_id)[0]
    checkpoint = svc.store.root / "experiments" / row["id"].replace("sha256:", "sha256-")
    (checkpoint / "ridge.joblib").write_bytes(b"corrupt model")
    svc.resume(job_id)
    svc.run_until_idle()
    job = svc.store.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.FAILED
    assert job["error"]["type"] == "ArtifactIntegrityError"
    assert svc.store.experiments(job_id)[0]["status"] == "failed"


def test_modeling_window_can_cover_calibration_without_loosening_resource_budgets() -> None:
    from entropytrade.research.model import ResearchRequest

    request = ResearchRequest(
        objective="Study a sufficiently long weather history", family="weather", lookback_days=240
    )
    assert request.lookback_days == 240
    assert request.budget.max_http_requests == 240
    assert request.budget.max_bytes == 96_000_000
    with pytest.raises(ValueError, match="lookback_days"):
        request.revalidated(lookback_days=366)


def test_model_artifacts_and_frozen_partitions_survive_verified_offline_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    from uuid import uuid4

    from entropytrade.api.jobs import Jobs
    from entropytrade.api.recovery import restore, snapshot
    from entropytrade.data.sources import file_hash
    from entropytrade.domain.time import SimulatedClock
    from entropytrade.tracking.store import TrackingStore
    from tests.research_modeling_support import MODEL_NOW
    from tests.unit.test_research_jobs import REPO

    base = REPO / "data/cache" / ("pytest-model-restore-" + uuid4().hex)
    try:
        svc, job_id = synthetic_job(base, monkeypatch)
        TrackingStore(Jobs(svc.workspace))
        svc.run_until_idle()
        row = svc.store.experiments(job_id)[0]
        assert row["status"] == "completed"
        before = {
            str(p.relative_to(svc.store.root)): file_hash(p)
            for p in (svc.store.root / "experiments").rglob("*")
            if p.is_file()
        }
        archive = base / "backup.zip"
        snapshot(REPO, svc.workspace, archive)
        restored = base / "restored"
        restore(REPO, archive, restored)
        again = ResearchService(restored, REPO, clock=SimulatedClock(MODEL_NOW))
        assert again.store.experiments(job_id) == [row]
        after = {
            str(p.relative_to(again.store.root)): file_hash(p)
            for p in (again.store.root / "experiments").rglob("*")
            if p.is_file()
        }
        assert before == after
        again.resume(job_id)
        again.run_until_idle()
        assert again.store.experiments(job_id) == [row]
    finally:
        shutil.rmtree(base, ignore_errors=True)


def attach_execution(svc: ResearchService, job_id: str) -> str:
    from entropytrade.execution.fee_evidence import FeeEvidenceStore
    from entropytrade.research.model import HypothesisSpec
    from tests.research_execution_support import execution_fixture
    from tests.research_modeling_support import MODEL_NOW

    row = svc.store.hypotheses(job_id)[0]
    spec = HypothesisSpec.model_validate(row["spec"])
    dataset_id, fees = execution_fixture(svc.store.root, spec, svc.store.job_features(job_id))
    acquisition = svc.store.plan_acquisition(
        dataset_id,
        "controlled-execution-evidence",
        {"entity": "CLIPHL"},
        status="queued",
        now=MODEL_NOW,
    )
    svc.store.link_acquisition(job_id, acquisition, "controlled-execution", "automatic")
    svc.store.finish_acquisition(
        acquisition,
        "completed",
        "Declared synthetic acquired market evidence",
        dataset_id=dataset_id,
        now=MODEL_NOW,
    )
    for fee in fees:
        FeeEvidenceStore(svc.workspace).put(fee)
    return dataset_id


def test_persistent_job_runs_actual_acquired_contract_replay_with_synthetic_fills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc, job_id = synthetic_job(tmp_path, monkeypatch)
    # Test a typed model-probability hypothesis; it has no extra constant bias hurdle.
    with svc.store.connect() as db:
        from entropytrade.research.model import HypothesisSpec

        row = svc.store.hypotheses(job_id)[0]
        spec = HypothesisSpec.model_validate(row["spec"]).revalidated(rules=())
        db.execute(
            "UPDATE research_hypotheses SET spec=? WHERE job_id=?",
            (spec.model_dump_json(), job_id),
        )
    dataset_id = attach_execution(svc, job_id)
    svc.run_until_idle()
    rows = svc.store.experiments(job_id)
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    result = rows[0]["result"]
    assert result["experiment_id"] == rows[0]["id"]
    assert result["provenance"]["identity"]["execution_datasets"] == [dataset_id]
    backtest = result["backtest"]
    assert backtest["eligible"] is True
    assert backtest["execution_fidelity"] == "order_book_simulation"
    assert backtest["submission_enabled"] is False
    assert backtest["paper_eligible"] is False
    assert backtest["performance"]["tested"] is True
    assert backtest["performance"]["scenarios"]
    assert result["validation"]["holdout_evaluated"] is False
    assert result["validation"]["prospective"] is False
    # Reusing the same acquisition and fee identities cannot start another experiment.
    svc.resume(job_id)
    svc.run_until_idle()
    assert svc.store.experiments(job_id) == rows


def test_authentic_philadelphia_source_bytes_enter_persistent_modeling_with_honest_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.domain.time import SimulatedClock
    from entropytrade.research import model
    from tests.research_fixture_support import ReplayTransport
    from tests.unit.test_research_acquisition import NOW as CAPTURE_NOW
    from tests.unit.test_research_jobs import REPO

    # Short captured window tests authentic byte plumbing; model minima remain unchanged.
    monkeypatch.setitem(model.MIN_EVENTS, "quick", 5)
    transport = ReplayTransport()
    svc = ResearchService(
        tmp_path / "workspace",
        REPO,
        clock=SimulatedClock(CAPTURE_NOW),
        transport=transport,
        transport_label="controlled_replay",
        sleep=lambda _: None,
    )
    job_id = str(
        svc.submit(
            {
                "objective": "Study NWS forecast bias against Philadelphia settlement highs",
                "family": "weather",
                "universe": ["KXHIGHPHIL"],
                "acquisition": "approved_sources",
                "lookback_days": 7,
                "validation_depth": "quick",
            }
        )["id"]
    )
    svc.run_until_idle()
    rows = svc.store.experiments(job_id)
    bias = next(r for r in rows if r["result"]["eligibility"].get("independent_events"))
    assert bias["result"]["data_kind"] == "real"
    assert bias["result"]["eligibility"]["independent_events"] == 7
    assert bias["result"]["provenance"]["dataset_versions"]
    assert bias["status"] == "refused"
    assert bias["result"]["models"] == {}
    assert bias["result"]["backtest"]["eligible"] is False
    assert bias["result"]["backtest"]["performance"] is None
    assert bias["result"]["backtest"]["submission_enabled"] is False
    assert transport.unknown == []


def test_persistent_job_consumes_verified_restored_snapshot_without_touching_source(
    tmp_path: Path,
) -> None:
    from entropytrade.data.sources import file_hash
    from entropytrade.features.registry import scientific_hash
    from entropytrade.weather.history import build_snapshot
    from tests.integration.weather_history_retained import SOURCE

    svc, job_id = modeling_job(tmp_path)
    snapshots = svc.workspace / "runs/weather-datasets"
    build_snapshot(snapshots, sorted(SOURCE.glob("*/*/public")))
    before = {p: file_hash(p) for p in snapshots.rglob("*") if p.is_file()}
    svc.run_until_idle()
    rows = svc.store.job_acquisitions(job_id, statuses=("completed",))
    assert rows
    assert all(r["source_id"] == "local-restored-execution" for r in rows)
    assert all(r["dataset_id"] for r in rows)
    assert all(file_hash(p) == digest for p, digest in before.items())
    boundaries = svc.store.freeze_boundaries(scientific_hash({"family": "weather"}), [], now=NOW)
    assert len(boundaries) == 3
    assert svc.store.experiments(job_id)
    assert svc.store.get_job(job_id)["status"] != JobStatus.FAILED  # type: ignore[index]


def test_corrupt_restored_snapshot_blocks_modeling_before_fitting(tmp_path: Path) -> None:
    from entropytrade.weather.history import build_snapshot
    from tests.integration.weather_history_retained import SOURCE

    svc, job_id = modeling_job(tmp_path)
    snapshots = svc.workspace / "runs/weather-datasets"
    build_snapshot(snapshots, sorted(SOURCE.glob("*/*/public")))
    payload = next(snapshots.glob("*/receipts/*/raw/0001.json"))
    payload.write_bytes(payload.read_bytes() + b"changed")
    svc.run_until_idle()
    job = svc.store.get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.FAILED
    assert job["error"]["type"] == "LocalEvidenceRefused"
    assert svc.store.experiments(job_id) == []
