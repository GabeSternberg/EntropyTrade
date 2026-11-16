"""Persistent paper origin/terminal controls; controlled fixtures never imply profitability."""

import copy
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from entropytrade.agents.fixture import demo_specs
from entropytrade.api.jobs import Jobs
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.research.paper import ResearchPaperService
from entropytrade.tracking.evaluate import shadow_limits
from entropytrade.tracking.store import (
    SOURCE_SCHEMA,
    TrackingStore,
    research_deployment_key,
    validate_research_source,
)
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_support import paper_fixture
from tests.unit.test_tracking import monitor


def origin() -> dict[str, Any]:
    job_id = str(uuid4())
    spec = demo_specs()[0]
    source = {
        "schema": SOURCE_SCHEMA,
        "research_job_id": job_id,
        "experiment_id": "sha256:" + "e" * 64,
        "hypothesis_id": "controlled-hypothesis",
        "spec_hash": spec.spec_hash(),
        "binding_hash": "sha256:" + "b" * 64,
        "eligibility": {
            "schema": "research-paper-eligibility-v1",
            "policy_version": "research-paper-gates-v1",
            "risk_limits": shadow_limits().model_dump(mode="json"),
            "eligible": True,
            "proposal_hash": "sha256:" + "c" * 64,
        },
    }
    source["source_hash"] = scientific_hash(source)
    return {
        "source_kind": "autonomous_research",
        "job_id": job_id,
        "research_job_id": job_id,
        "experiment_id": source["experiment_id"],
        "candidate_id": source["hypothesis_id"],
        "spec_hash": source["spec_hash"],
        "spec": spec.model_dump(mode="json"),
        "model_binding": {"binding_hash": source["binding_hash"]},
        "source_ref": source,
        "deployment_key": research_deployment_key(source),
    }


@pytest.mark.parametrize(
    "field", ["research_job_id", "experiment_id", "spec_hash", "deployment_key"]
)
def test_origin_binding_detects_changed_persistent_references(field: str) -> None:
    original = origin()
    assert validate_research_source(original) == original["source_ref"]
    altered = copy.deepcopy(original)
    altered[field] = "changed"
    with pytest.raises(ValueError, match="mismatch"):
        validate_research_source(altered)


def test_eligibility_proof_and_source_hash_are_frozen() -> None:
    original = origin()
    altered = copy.deepcopy(original)
    altered["source_ref"]["eligibility"]["eligible"] = False
    with pytest.raises(ValueError, match="mismatch"):
        validate_research_source(altered)
    # Rehashing a denied proof cannot turn it into a valid deployment.
    source = altered["source_ref"]
    source["source_hash"] = scientific_hash({k: v for k, v in source.items() if k != "source_hash"})
    with pytest.raises(ValueError, match="eligibility"):
        validate_research_source(altered)


def test_changed_strategy_rules_cannot_reuse_the_frozen_source_hash() -> None:
    altered = origin()
    altered["spec"]["entry_rules"]["all_of"][0]["threshold"] = "0.0001"
    with pytest.raises(ValueError, match="strategy hash mismatch"):
        validate_research_source(altered)


@pytest.mark.parametrize("action", ["cancel", "suspend"])
def test_terminal_control_prevents_late_commit_and_restart_reactivation(
    tmp_path: Path, action: str
) -> None:
    store = TrackingStore(Jobs(tmp_path))
    monitor_id = monitor(store)
    before = store.get(monitor_id)
    assert before is not None
    assert before["source_kind"] == "legacy"
    assert before["source_ref"] is None
    claimed = store.claim()
    assert claimed is not None
    store.control(monitor_id, action)
    result = {"detail": "late controlled result", "submission_enabled": False, "artifacts": []}
    assert not store.finish(monitor_id, claimed[1], result)
    current = store.get(monitor_id)
    assert current is not None
    assert current["status"] == ("cancelled" if action == "cancel" else "suspended")
    assert current["cycles"][0]["status"] == "interrupted"
    assert current["paper_account"] == before["paper_account"]
    for bypass in ("pause", "resume"):
        with pytest.raises(ValueError, match=r"cannot|require"):
            store.control(monitor_id, bypass)
    store.control(monitor_id, action)  # terminal repeated requests are idempotent
    reopened = TrackingStore(Jobs(tmp_path))
    reopened.recover()
    assert reopened.get(monitor_id)["status"] == current["status"]  # type: ignore[index]
    assert reopened.claim() is None


@pytest.fixture(scope="module")
def fitted_paper_template(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str, dict[str, Any]]:
    case = paper_fixture(tmp_path_factory.mktemp("controlled-paper-store"))
    return case.jobs.root, case.job_id, case.request


def reopen_case(
    template: tuple[Path, str, dict[str, Any]], destination: Path
) -> tuple[TrackingStore, ResearchPaperService, str, dict[str, Any]]:
    workspace, job_id, request = template
    shutil.copytree(workspace, destination)
    store = TrackingStore(Jobs(destination))
    service = ResearchPaperService(
        destination, store, clock=SimulatedClock(MODEL_NOW), expected_data_kind="synthetic"
    )
    return store, service, job_id, request


def test_actual_fitted_research_deployment_is_persistent_and_idempotent(
    fitted_paper_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: MODEL_NOW.isoformat())
    store, service, job_id, request = reopen_case(fitted_paper_template, tmp_path / "research")
    created = service.create(job_id, request)
    current = store.get(created["id"])
    assert current is not None
    assert current["source_kind"] == "autonomous_research"
    assert current["research_job_id"] == job_id
    assert current["source_ref"]["eligibility"]["data_kind"] == "synthetic"
    assert current["model_binding"]["snapshot"]["data_kind"] == "synthetic"
    assert current["submission_enabled"] is False
    with store.jobs.connect() as db:
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    repeated = service.create(job_id, request)
    assert repeated["id"] == created["id"]
    assert repeated["created"] is False
    reopened = TrackingStore(Jobs(store.jobs.root))
    reopened.recover()
    assert reopened.get(created["id"])["source_ref"] == current["source_ref"]  # type: ignore[index]
    store.control(created["id"], "cancel")
    same_proposal = service.create(job_id, request)
    assert same_proposal["id"] == created["id"]
    assert same_proposal["deployment"]["status"] == "cancelled"
    assert len(store.history()) == 1


def test_research_cycles_use_only_real_trained_windows_and_skip_missed_decisions(
    fitted_paper_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [MODEL_NOW]
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock[0].isoformat())
    store, service, job_id, request = reopen_case(fitted_paper_template, tmp_path / "schedule")
    monitor_id = service.create(job_id, request)["id"]
    original = store.get(monitor_id)
    assert original is not None
    scheduled = datetime.fromisoformat(original["next_at"])
    assert scheduled > MODEL_NOW
    clock[0] = scheduled + timedelta(minutes=5)
    assert store.claim() is None
    missed = store.get(monitor_id)
    assert missed is not None
    assert missed["cycle_count"] == 0
    assert "missed trained decision" in missed["events"][-1]["action"]
    next_window = datetime.fromisoformat(missed["next_at"])
    assert next_window > clock[0]
    clock[0] = next_window + timedelta(seconds=1)
    claim = store.claim()
    assert claim is not None
    assert claim[0] == monitor_id
    assert store.claim() is None
    assert store.finish(
        monitor_id,
        claim[1],
        {"detail": "Controlled scheduler cycle", "submission_enabled": False, "artifacts": []},
    )
    completed = store.get(monitor_id)
    assert completed is not None
    assert completed["cycles"][0]["started_at"] == clock[0].isoformat()
    assert datetime.fromisoformat(completed["next_at"]) > clock[0]
    assert completed["paper_account"] is None


def test_changed_research_strategy_cannot_commit_a_pending_account_transition(
    fitted_paper_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [MODEL_NOW]
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock[0].isoformat())
    store, service, job_id, request = reopen_case(fitted_paper_template, tmp_path / "changed-proof")
    monitor_id = service.create(job_id, request)["id"]
    current = store.get(monitor_id)
    assert current is not None
    clock[0] = datetime.fromisoformat(current["next_at"]) + timedelta(seconds=1)
    claim = store.claim()
    assert claim is not None
    altered = copy.deepcopy(current["spec"])
    altered["minimum_edge"] = "0.0001"
    with store.jobs.connect() as db:
        db.execute("UPDATE monitors SET spec=? WHERE id=?", (json.dumps(altered), monitor_id))
    assert store.finish(monitor_id, claim[1], {"detail": "uncommitted", "paper": {}}) is False
    assert store.history()[0]["status"] == "suspended"
    with store.jobs.connect() as db:
        assert db.execute("SELECT count(*) FROM shadow_accounts").fetchone()[0] == 0
        assert (
            db.execute("SELECT status FROM shadow_cycles WHERE id=?", (claim[1],)).fetchone()[0]
            == "interrupted"
        )


@pytest.mark.parametrize("drift", ["policy", "risk"])
def test_policy_drift_suspends_before_claim_or_pending_commit(
    fitted_paper_template: tuple[Path, str, dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
) -> None:
    from entropytrade.research import paper

    clock = [MODEL_NOW]
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock[0].isoformat())
    store, service, job_id, request = reopen_case(fitted_paper_template, tmp_path / drift)
    first = service.create(job_id, request)["id"]
    current = store.get(first)
    assert current is not None
    clock[0] = datetime.fromisoformat(current["next_at"]) + timedelta(seconds=1)
    claim = store.claim()
    assert claim is not None
    if drift == "policy":
        monkeypatch.setattr(paper, "POLICY", "changed-paper-gates")
    else:
        original = shadow_limits
        monkeypatch.setattr(
            paper, "shadow_limits", lambda: original().revalidated(config_version="changed-policy")
        )
    assert not store.finish(first, claim[1], {"detail": "late changed-policy result"})
    assert store.history()[0]["status"] == "suspended"
    with store.jobs.connect() as db:
        assert db.execute("SELECT count(*) FROM shadow_accounts").fetchone()[0] == 0
        db.execute("UPDATE monitors SET status='active'")
    assert store.claim() is None
    assert store.history()[0]["status"] == "suspended"


def test_research_only_creation_never_writes_into_a_collector_chain(tmp_path: Path) -> None:
    store = TrackingStore(Jobs(tmp_path / "chain" / "restored"))
    with pytest.raises(ValueError, match="collector"):
        store.create_research(
            research_job_id=str(uuid4()),
            experiment_id="sha256:" + "e" * 64,
            hypothesis_id="controlled",
            spec=demo_specs()[0],
            binding={},
            eligibility={},
        )
    assert store.history() == []
