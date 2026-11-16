"""One bounded diagnostic per incident, including crash/terminal retries; no real research."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from entropytrade.api.jobs import Jobs
from entropytrade.domain.strategy import ProbabilityModelRef, StrategySpec
from entropytrade.domain.time import SimulatedClock
from entropytrade.features.registry import scientific_hash
from entropytrade.research.investigations import enqueue_investigation, verify_investigation
from entropytrade.research.model import JobStatus, ResearchRequest
from entropytrade.research.service import ResearchService
from entropytrade.research.store import ResearchStore, investigation_job_id
from entropytrade.tracking.readiness_store import ReadinessStore
from entropytrade.tracking.store import TrackingStore
from tests.unit.test_tracking import monitor as create_monitor

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)
POLICY = scientific_hash("CONTROLLED incident policy; no trading permission")
OBJECTIVE = "Explain the retained forecast-skill incident without new source observations."


@pytest.fixture
def case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ResearchService, ReadinessStore, dict[str, Any]]:
    def forbid(*_: Any, **__: Any) -> Any:
        pytest.fail("an offline investigation attempted provider or network work")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbid)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: NOW.isoformat())
    root = tmp_path / "workspace"
    tracking = TrackingStore(Jobs(root))
    mid = create_monitor(tracking)
    value = tracking.get(mid)
    assert value is not None
    # Deliberately metadata-only CONTROLLED frozen scope. The diagnostic cannot score
    # this object, fit it, claim model compatibility or authorize any trading.
    spec = StrategySpec.model_validate(value["spec"]).revalidated(
        model_ref=ProbabilityModelRef(family="forecast_error", version="sha256:" + "a" * 64)
    )
    assert spec.model_ref is not None
    binding = {
        "status": "bound",
        "model_ref": spec.model_ref.model_dump(mode="json"),
        "snapshot": {
            "family": spec.model_ref.family,
            "model_hash": spec.model_ref.version,
            "series": ["KXHIGHPHIL", "KXHIGHCHI"],
        },
    }
    binding["binding_hash"] = scientific_hash(binding)
    with tracking.jobs.connect() as db:
        db.execute(
            "UPDATE monitors SET spec=?,spec_hash=?,model_binding=? WHERE id=?",
            (spec.model_dump_json(), spec.spec_hash(), json.dumps(binding), mid),
        )
    value = tracking.get(mid)
    assert value is not None
    research = ResearchService(root, REPO, clock=SimulatedClock(NOW), proposer=forbid)
    readiness = ReadinessStore(tracking.jobs, clock=SimulatedClock(NOW))
    return research, readiness, value


def enqueue(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]], **changes: Any
) -> dict[str, Any]:
    research, readiness, monitor = case
    arguments = {"policy_hash": POLICY, "objective": OBJECTIVE}
    return enqueue_investigation(
        research, readiness, monitor, "incident-1", **(arguments | changes)
    )


def test_incident_job_is_offline_scoped_and_keeps_primary_request_and_protections(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, _, _ = case
    primary = research.submit(
        {
            "objective": "Find forecast revisions using the explicitly selected paid provider.",
            "family": "weather",
            "provider": {"provider": "openai", "model_name": "controlled-not-called"},
            "budget": {"ai_usd": "1.00"},
        }
    )
    before = research.store.get_job(primary["id"])
    cuts = ["2026-01-01", "2026-04-01", "2026-08-01"]
    research.store.freeze_boundaries("weather-global", cuts, now=NOW)
    value = enqueue(case)
    job = research.store.get_job(value["research_job_id"])
    assert job is not None
    request = ResearchRequest.model_validate(job["request"])
    assert request.universe == ("KXHIGHPHIL",)  # no model-wide Chicago expansion
    assert request.provider.provider == "local_templates"
    assert request.provider.model_name == ""
    assert request.budget.ai_usd == 0
    assert request.budget.max_http_requests == request.budget.max_bytes == 0
    assert request.budget.max_retries == 0
    assert 60 <= request.budget.max_runtime_seconds <= 120
    assert request.acquisition == "none"
    assert request.paper_preference == "never"
    assert research.store.get_job(primary["id"]) == before
    assert research.store.freeze_boundaries("weather-global", [], now=NOW) == cuts
    assert research.wake.is_set()
    verify_investigation(research.workspace, value)


def test_existing_worker_advances_diagnostic_without_provider_or_acquisition(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, _, _ = case
    value = enqueue(case, objective="Use a paid OpenAI model and download fresh data now.")
    research.run_until_idle()
    detail = research.detail(value["research_job_id"])
    assert detail is not None
    assert detail["status"] == JobStatus.AWAITING_OBSERVATIONS
    assert detail["acquisitions"] == []
    assert detail["usage"]["ai_requests"] == detail["usage"]["http_requests"] == 0
    assert all(
        row["spec"]["provenance"]["generator"] == "local_templates" for row in detail["hypotheses"]
    )


def test_crash_after_enqueue_before_link_reuses_destination_even_after_cancel(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    research, readiness, monitor = case
    original = readiness.investigate

    def lose_link(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("research_job_id") is not None:
            raise OSError("CONTROLLED crash before linking")
        return original(*args, **kwargs)

    monkeypatch.setattr(readiness, "investigate", lose_link)
    with pytest.raises(OSError, match="before linking"):
        enqueue(case)
    pending = original(monitor["id"], "incident-1", POLICY)
    assert pending["research_job_id"] is None
    assert pending["request_json"]
    jobs = research.store.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == investigation_job_id(pending["id"])
    research.cancel(jobs[0]["id"])
    verify_investigation(research.workspace, pending)  # offline proof never repairs the outbox
    assert original(monitor["id"], "incident-1", POLICY)["research_job_id"] is None
    monkeypatch.setattr(readiness, "investigate", original)
    linked = enqueue(case)
    assert linked["research_job_id"] == jobs[0]["id"]
    assert linked["created"] is False
    assert linked["status"] == JobStatus.CANCELLED
    assert len(research.store.list_jobs()) == 1


def test_incident_input_drift_refuses_without_creating_a_second_job(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, _, _ = case
    original = enqueue(case)
    with pytest.raises(ValueError, match="immutable"):
        enqueue(case, objective=OBJECTIVE + " Changed intent.")
    assert [job["id"] for job in research.store.list_jobs()] == [original["research_job_id"]]


def test_unverified_strategy_scope_cannot_create_an_outbox_or_job(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, readiness, monitor = case
    changed = dict(monitor)
    spec = StrategySpec.model_validate(changed["spec"])
    changed["spec"] = spec.revalidated(
        market_universe=spec.market_universe.revalidated(
            series_tickers=("KXHIGHCHI",), market_tickers=(), event_tickers=()
        )
    ).model_dump(mode="json")
    with pytest.raises(ValueError, match="scope checksum"):
        enqueue_investigation(
            research, readiness, changed, "incident-1", policy_hash=POLICY, objective=OBJECTIVE
        )
    assert not research.started()
    assert readiness.listing() == []


@pytest.mark.parametrize("status", list(JobStatus))
def test_internal_origin_reuses_all_states_before_queue_limits(
    tmp_path: Path, status: JobStatus
) -> None:
    store = ResearchStore(tmp_path / "research")
    request = ResearchRequest(objective=OBJECTIVE, family="weather", universe=("KXHIGHPHIL",))
    origin = scientific_hash("CONTROLLED incident origin")
    normal, _ = store.create_job(request, universe=request.universe, now=NOW)
    target, created = store.create_job(
        request, universe=request.universe, now=NOW, origin_key=origin
    )
    assert created
    assert target != normal
    with store.connect() as db:
        db.execute("UPDATE research_jobs SET status=? WHERE id=?", (status.value, target))
    assert store.create_job(
        request, universe=request.universe, now=NOW, limit=0, origin_key=origin
    ) == (target, False)
    with pytest.raises(ValueError, match="content changed"):
        store.create_job(
            request.revalidated(paper_preference="never"),
            universe=request.universe,
            now=NOW,
            origin_key=origin,
        )


def test_internal_origin_is_not_a_browser_request_field(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="origin_key"):
        ResearchRequest.model_validate(
            {"objective": OBJECTIVE, "family": "weather", "origin_key": scientific_hash("fake")}
        )
    store = ResearchStore(tmp_path / "research")
    request = ResearchRequest(objective=OBJECTIVE, family="weather")
    with pytest.raises(ValueError, match="content hash"):
        store.create_job(request, universe=("KXHIGHPHIL",), now=NOW, origin_key="browser-chosen")


def test_distinct_incidents_do_not_alias_even_with_identical_requests(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path / "research")
    request = ResearchRequest(objective=OBJECTIVE, family="weather", universe=("KXHIGHPHIL",))
    first, _ = store.create_job(
        request, universe=request.universe, now=NOW, origin_key=scientific_hash("incident one")
    )
    second, created = store.create_job(
        request, universe=request.universe, now=NOW, origin_key=scientific_hash("incident two")
    )
    assert created
    assert first != second
    with pytest.raises(ValueError, match="content changed"):
        store.create_job(
            request,
            universe=("KXHIGHCHI",),
            now=NOW,
            origin_key=scientific_hash("incident one"),
        )


def test_read_only_restore_checks_references_and_safe_request_without_writes(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, _, _ = case
    value = enqueue(case)
    before = {
        path.relative_to(research.workspace).as_posix(): path.read_bytes()
        for path in research.workspace.rglob("*")
        if path.is_file()
    }
    verify_investigation(research.workspace, value)
    assert before == {
        path.relative_to(research.workspace).as_posix(): path.read_bytes()
        for path in research.workspace.rglob("*")
        if path.is_file()
    }
    with pytest.raises(ValueError, match="different research destination"):
        verify_investigation(research.workspace, value | {"research_job_id": value["monitor_id"]})
    request = json.loads(value["request_json"])
    request["budget"]["ai_usd"] = "1.00"
    with pytest.raises(ValueError, match="bounded and offline"):
        verify_investigation(research.workspace, value | {"request_json": json.dumps(request)})


def test_restore_never_silently_ignores_live_wal_metadata(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, _, _ = case
    value = enqueue(case)
    with research.store.connect() as db:
        db.execute(
            "UPDATE research_jobs SET detail='CONTROLLED committed WAL' WHERE id=?",
            (value["research_job_id"],),
        )
        db.commit()
        with pytest.raises(ValueError, match="checkpointed SQLite"):
            verify_investigation(research.workspace, value)
    verify_investigation(research.workspace, value)


def test_restore_refuses_a_pending_rollback_journal(
    case: tuple[ResearchService, ReadinessStore, dict[str, Any]],
) -> None:
    research, _, _ = case
    value = enqueue(case)
    journal = research.workspace / "research/research.sqlite-journal"
    journal.write_bytes(b"CONTROLLED pending rollback metadata")
    with pytest.raises(ValueError, match="checkpointed SQLite"):
        verify_investigation(research.workspace, value)
