"""Research paper promotion uses immutable actual C evidence and deterministic gates."""

import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from entropytrade.data.sources import file_hash
from entropytrade.domain.time import SimulatedClock
from entropytrade.execution.fee_evidence import FeeEvidenceStore
from entropytrade.research.paper import (
    PaperEligibilityError,
    ResearchPaperService,
    verify_paper_origin,
)
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_support import PaperFixture, paper_fixture


@pytest.fixture(scope="module")
def original(tmp_path_factory: pytest.TempPathFactory) -> PaperFixture:
    return paper_fixture(tmp_path_factory.mktemp("controlled-paper-source"))


@pytest.fixture
def controlled(original: PaperFixture, tmp_path: Path) -> PaperFixture:
    from entropytrade.api.jobs import Jobs
    from entropytrade.tracking.store import TrackingStore

    workspace = tmp_path / "workspace"
    shutil.copytree(original.jobs.root, workspace)
    jobs = Jobs(workspace)
    tracking = TrackingStore(jobs)
    service = ResearchPaperService(
        workspace, tracking, clock=SimulatedClock(MODEL_NOW), expected_data_kind="synthetic"
    )
    return PaperFixture(
        jobs,
        tracking,
        service,
        original.job_id,
        original.experiment_id,
        dict(original.request),
        original.result,
    )


def test_actual_controlled_promotion_is_idempotent_and_preserves_proof(
    controlled: PaperFixture,
) -> None:
    first = controlled.service.create(controlled.job_id, controlled.request)
    again = controlled.service.create(controlled.job_id, controlled.request)
    assert first["id"] == again["id"]
    assert first["created"] is True
    assert again["created"] is False
    assert first["submission_enabled"] is False
    monitor = first["deployment"]
    assert monitor["source_ref"]["eligibility"]["data_kind"] == "synthetic"
    assert controlled.jobs.history() == []
    verify_paper_origin(controlled.jobs.root, monitor)


def test_production_policy_refuses_synthetic_proof(controlled: PaperFixture) -> None:
    actual = ResearchPaperService(
        controlled.jobs.root, controlled.tracking, clock=SimulatedClock(MODEL_NOW)
    )
    with pytest.raises(PaperEligibilityError) as error:
        actual.create(controlled.job_id, controlled.request)
    assert any(
        c["name"] == "authentic_evidence" and not c["passed"]
        for c in error.value.proposal["checks"]
    )
    assert controlled.tracking.history() == []


def test_preference_never_prevents_promotion(controlled: PaperFixture) -> None:
    with controlled.jobs.connect() as db:
        # Research metadata is a distinct database; no fake legacy job is inserted.
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    import sqlite3

    path = controlled.jobs.root / "research/research.sqlite"
    with sqlite3.connect(path) as db:
        request = json.loads(
            db.execute(
                "SELECT request FROM research_jobs WHERE id=?", (controlled.job_id,)
            ).fetchone()[0]
        )
        request["paper_preference"] = "never"
        db.execute(
            "UPDATE research_jobs SET request=? WHERE id=?",
            (json.dumps(request), controlled.job_id),
        )
    with pytest.raises(PaperEligibilityError) as error:
        controlled.service.create(controlled.job_id, controlled.request)
    assert any(
        c["name"] == "paper_preference" and not c["passed"] for c in error.value.proposal["checks"]
    )
    assert controlled.tracking.history() == []


def test_clock_refresh_does_not_change_immutable_proposal_hash(controlled: PaperFixture) -> None:
    first, _, _ = controlled.service.evaluate(controlled.job_id, controlled.experiment_id, "ridge")
    controlled.service.clock = SimulatedClock(MODEL_NOW + timedelta(days=1))
    second, _, _ = controlled.service.evaluate(controlled.job_id, controlled.experiment_id, "ridge")
    assert first["eligible"] is True
    assert first["proposal_hash"] == second["proposal_hash"]


@pytest.mark.parametrize(
    "extra", [{"risk_limits": {}}, {"binding": {}}, {"data_kind": "synthetic"}]
)
def test_browser_cannot_submit_bindings_risk_or_provenance(
    controlled: PaperFixture, extra: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="only"):
        controlled.service.create(controlled.job_id, controlled.request | extra)
    assert controlled.tracking.history() == []


def test_missing_current_certified_fee_refuses_promotion(controlled: PaperFixture) -> None:
    for path in FeeEvidenceStore(controlled.jobs.root).root.glob("*.json"):
        path.unlink()
    with pytest.raises(PaperEligibilityError) as error:
        controlled.service.create(controlled.job_id, controlled.request)
    assert any(
        c["name"].startswith("current_fees:") and not c["passed"]
        for c in error.value.proposal["checks"]
    )


def test_promotion_fee_proof_cannot_disappear_on_restore(controlled: PaperFixture) -> None:
    value = controlled.service.create(controlled.job_id, controlled.request)
    for path in FeeEvidenceStore(controlled.jobs.root).root.glob("*.json"):
        path.unlink()
    with pytest.raises(FileNotFoundError):
        verify_paper_origin(controlled.jobs.root, value["deployment"])


def test_frozen_risk_profile_change_invalidates_origin(
    controlled: PaperFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.research import paper

    value = controlled.service.create(controlled.job_id, controlled.request)
    from entropytrade.tracking.evaluate import shadow_limits

    original = shadow_limits
    monkeypatch.setattr(
        paper, "shadow_limits", lambda: original().revalidated(config_version="changed-policy")
    )
    with pytest.raises(ValueError, match="risk configuration"):
        verify_paper_origin(controlled.jobs.root, value["deployment"])


def test_gate_policy_change_requires_new_validation(
    controlled: PaperFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.research import paper

    value = controlled.service.create(controlled.job_id, controlled.request)
    monkeypatch.setattr(paper, "POLICY", "changed-paper-gates")
    with pytest.raises(ValueError, match="policy changed"):
        verify_paper_origin(controlled.jobs.root, value["deployment"])


def test_corrupt_model_refuses_before_creating_monitor(controlled: PaperFixture) -> None:
    root = (
        controlled.jobs.root
        / "research/experiments"
        / controlled.experiment_id.replace("sha256:", "sha256-")
    )
    (root / "ridge.paper.json").write_text("{}")
    with pytest.raises(PaperEligibilityError):
        controlled.service.create(controlled.job_id, controlled.request)
    assert controlled.tracking.history() == []


@pytest.mark.parametrize("mutation", ["single_scenario", "reduced_fidelity", "unsettled"])
def test_replay_status_alone_cannot_bypass_execution_gates(
    controlled: PaperFixture, mutation: str
) -> None:
    import sqlite3

    root = (
        controlled.jobs.root
        / "research/experiments"
        / controlled.experiment_id.replace("sha256:", "sha256-")
    )
    report = json.loads((root / "results.json").read_text())
    backtest = report["models"]["ridge"]["backtest"]
    if mutation == "single_scenario":
        backtest["performance"]["scenarios"] = backtest["performance"]["scenarios"][:1]
    elif mutation == "reduced_fidelity":
        backtest["execution_fidelity"] = "sensitivity_study"
    else:
        backtest["performance"]["scenarios"][0]["unsettled_positions"] = 1
        backtest["performance"]["scenarios"][0]["net_pnl"] = None
    (root / "results.json").write_text(json.dumps(report, sort_keys=True))
    checksums = json.loads((root / "checksums.json").read_text())
    checksums["results.json"] = file_hash(root / "results.json")
    (root / "checksums.json").write_text(json.dumps(checksums))
    with sqlite3.connect(controlled.jobs.root / "research/research.sqlite") as db:
        db.execute(
            "UPDATE research_experiments SET result=? WHERE job_id=? AND id=?",
            (json.dumps(report), controlled.job_id, controlled.experiment_id),
        )
    with pytest.raises(PaperEligibilityError):
        controlled.service.create(controlled.job_id, controlled.request)
    assert controlled.tracking.history() == []
