"""Monitoring exercises real controlled receipts, forecasts, outcomes and paper accounts.

All source dates/outcomes are explicitly synthetic. No mocked score or eligibility result
stands in for the collection, model, scoring or accounting pipeline.
"""

import json
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.owner import OwnerAuth, initialize
from entropytrade.domain.time import SimulatedClock
from entropytrade.research import readiness
from entropytrade.research.model import JobStatus, ResearchRequest
from entropytrade.research.readiness import ResearchReadinessService
from entropytrade.research.readiness_evidence import (
    DegradationFacts,
    ReadinessFacts,
    assess_degradation,
    assess_readiness,
)
from entropytrade.research.service import ResearchService
from entropytrade.tracking import alerts
from entropytrade.tracking.store import TrackingStore
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
    outcome_transport_for_monitor,
)
from tests.research_paper_support import PaperFixture
from tests.research_readiness_support import readiness_fixture
from tests.unit.test_tracking import monitor as create_monitor

REPO = Path(__file__).resolve().parents[3]
AUDIENCE = "http://127.0.0.1:43128"
PASSWORD = secrets.token_urlsafe(32)


def copy_workspace(original: PaperFixture, workspace: Path) -> PaperFixture:
    def isolated(source: str, destination: str) -> str:
        if source.endswith((".sqlite", "-wal", "-shm")):
            shutil.copy2(source, destination)
        else:
            os.link(source, destination)
        return destination

    shutil.copytree(original.jobs.root, workspace, copy_function=isolated)
    tracking = TrackingStore(Jobs(workspace))
    return PaperFixture(
        tracking.jobs,
        tracking,
        original.service,
        original.job_id,
        original.experiment_id,
        original.request,
        original.result,
    )


def owner_approve(
    service: ResearchReadinessService,
    private: Path,
    *,
    capital: str = "100.00",
    loss: str = "50.00",
) -> dict[str, Any]:
    private.mkdir(mode=0o700)
    credentials = initialize(private / "owner.json", REPO, "controlled-monitor-owner", PASSWORD)
    auth = OwnerAuth(REPO, credentials, clock=service.clock)
    cookie = auth.set_cookie(auth.login(PASSWORD, AUDIENCE)).split(";", 1)[0]
    with controlled_forward_environment(service.clock):  # type: ignore[arg-type]
        created = service.create(
            service.tracking.history()[0]["id"],
            {"capital_dollars": capital, "max_loss_dollars": loss},
        )
        prepared = service.prepare_review(
            created["id"],
            {
                "decision": "approve",
                "expected_revision": 0,
                "note": "CONTROLLED owner reviewed actual synthetic receipt evidence",
            },
        )
        with auth.authorize(cookie, AUDIENCE) as principal:
            return service.commit_review(prepared, principal)


@pytest.fixture(scope="module")
def source(tmp_path_factory: pytest.TempPathFactory) -> tuple[PaperFixture, ReadinessFacts]:
    return readiness_fixture(tmp_path_factory.mktemp("monitor-source") / "workspace")


@pytest.fixture(scope="module")
def adverse_source(
    source: tuple[PaperFixture, ReadinessFacts], tmp_path_factory: pytest.TempPathFactory
) -> tuple[PaperFixture, ReadinessFacts]:
    """Freeze an actually qualified reference, then collect 22 actual losing days."""
    original, facts = source
    root = tmp_path_factory.mktemp("monitor-adverse")
    paper = copy_workspace(original, root / "workspace")
    clock = SimulatedClock(facts.evidence_as_of)
    service = ResearchReadinessService(
        paper.jobs.root, paper.tracking, clock=clock, expected_data_kind="synthetic"
    )
    with patch(
        "entropytrade.tracking.store.timestamp", side_effect=lambda: clock.now().isoformat()
    ):
        owner_approve(service, root / "private")
    # The original forecasts and quotes are untouched. Official mock GET receipts now
    # settle genuinely held contracts to NO through the existing outcome/account code.
    with patch(
        "tests.research_paper_forward_support.outcome_transport_for_monitor",
        side_effect=lambda monitor, clock: outcome_transport_for_monitor(monitor, clock, yes=False),
    ):
        for _ in range(22):
            when = clock.now().replace(minute=0, second=5) + timedelta(days=1)
            commit_controlled_cycle(paper, when, clock=clock)
    with controlled_forward_environment(clock):
        current = assess_readiness(
            paper.jobs.root,
            service._monitor(facts.monitor_id),
            clock=clock,
            expected_data_kind="synthetic",
        )
    assert current.scores.independent_events == 43
    assert current.account["settlement_count"] == 43
    return paper, current


@dataclass
class Case:
    paper: PaperFixture
    facts: ReadinessFacts
    clock: SimulatedClock
    research: ResearchService
    service: ResearchReadinessService


def make_case(
    source: tuple[PaperFixture, ReadinessFacts], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Case:
    original, facts = source
    paper = copy_workspace(original, tmp_path / "workspace")
    clock = SimulatedClock(facts.evidence_as_of)

    def forbid(*_: Any, **__: Any) -> Any:
        pytest.fail("monitoring attempted network or paid-provider work")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbid)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbid)
    monkeypatch.setattr("entropytrade.tracking.store.timestamp", lambda: clock.now().isoformat())
    research = ResearchService(paper.jobs.root, REPO, clock=clock, proposer=forbid)
    service = ResearchReadinessService(
        paper.jobs.root, paper.tracking, research, clock=clock, expected_data_kind="synthetic"
    )
    return Case(paper, facts, clock, research, service)


@pytest.fixture
def case(
    source: tuple[PaperFixture, ReadinessFacts], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Case:
    return make_case(source, tmp_path, monkeypatch)


@pytest.fixture
def adverse(
    adverse_source: tuple[PaperFixture, ReadinessFacts],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Case:
    return make_case(adverse_source, tmp_path, monkeypatch)


def monitor(case: Case) -> dict[str, Any]:
    with controlled_forward_environment(case.clock):
        return case.service.monitoring(case.facts.monitor_id)


def diagnostic_jobs(case: Case) -> list[dict[str, Any]]:
    return [
        job
        for job in case.research.store.list_jobs()
        if job["request"]["objective"].startswith("Investigate retained paper incident ")
    ]


def assert_offline(case: Case, job_id: str) -> None:
    job = case.research.store.get_job(job_id)
    assert job is not None
    request = ResearchRequest.model_validate(job["request"])
    assert request.universe == ("KXHIGHPHIL",)
    assert request.provider.provider == "local_templates"
    assert request.budget.ai_usd == 0
    assert request.budget.max_http_requests == request.budget.max_bytes == 0
    assert request.budget.max_retries == 0
    assert request.budget.max_runtime_seconds == 120
    assert request.acquisition == "none"
    assert request.paper_preference == "never"


def test_actual_adverse_window_suspends_and_restarts_without_duplicate_job(adverse: Case) -> None:
    primary = adverse.research.store.get_job(adverse.paper.job_id)
    before = adverse.paper.tracking.get(adverse.facts.monitor_id)["paper_account"]  # type: ignore[index]
    first = monitor(adverse)
    assert first["evaluation"]["status"] == "degraded"
    signal = next(s for s in first["evaluation"]["signals"] if s["kind"] == "forecast_degradation")
    assert signal["recommended_action"] == "suspend_and_investigate"
    assert adverse.paper.tracking.get(adverse.facts.monitor_id)["status"] == "suspended"  # type: ignore[index]
    incident = next(i for i in first["incidents"] if i["kind"] == "forecast_degradation")
    investigation = next(
        row for row in first["investigations"] if row["incident_key"] == incident["id"]
    )
    job_id = investigation["research_job_id"]
    assert_offline(adverse, job_id)
    assert len(diagnostic_jobs(adverse)) == 1
    adverse.research.cancel(job_id)
    for restart in (False, True):
        if restart:
            adverse.service = ResearchReadinessService(
                adverse.paper.jobs.root,
                TrackingStore(Jobs(adverse.paper.jobs.root)),
                ResearchService(
                    adverse.paper.jobs.root,
                    REPO,
                    clock=adverse.clock,
                    proposer=adverse.research.proposer,
                ),
                clock=adverse.clock,
                expected_data_kind="synthetic",
            )
        repeated = monitor(adverse)
        same = [row for row in repeated["investigations"] if row["incident_key"] == incident["id"]]
        assert len(same) == 1
        assert same[0]["research_job_id"] == job_id
        assert repeated["submission_enabled"] is False
        assert len(diagnostic_jobs(adverse)) == 1
    assert adverse.research.store.get_job(job_id)["status"] == JobStatus.CANCELLED  # type: ignore[index]
    assert adverse.research.store.get_job(adverse.paper.job_id) == primary
    assert adverse.paper.tracking.get(adverse.facts.monitor_id)["paper_account"] == before  # type: ignore[index]


def test_monitor_outbox_recovers_crash_after_enqueue_before_link(
    adverse: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = adverse.service.store.investigate

    def lose_link(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("research_job_id") is not None:
            raise OSError("CONTROLLED crash after enqueue before outbox link")
        return original(*args, **kwargs)

    monkeypatch.setattr(adverse.service.store, "investigate", lose_link)
    first = monitor(adverse)
    incident = next(i for i in first["incidents"] if i["kind"] == "forecast_degradation")
    pending = next(i for i in first["investigations"] if i["incident_key"] == incident["id"])
    assert pending["research_job_id"] is None
    assert pending["request_json"]
    jobs = diagnostic_jobs(adverse)
    matching = [j for j in jobs if incident["id"] in j["request"]["objective"]]
    assert len(matching) == 1
    job_id = matching[0]["id"]
    adverse.research.cancel(job_id)
    monkeypatch.setattr(adverse.service.store, "investigate", original)
    retried = monitor(adverse)
    linked = next(i for i in retried["investigations"] if i["incident_key"] == incident["id"])
    assert linked["research_job_id"] == job_id
    matching = [j for j in diagnostic_jobs(adverse) if incident["id"] in j["request"]["objective"]]
    assert len(matching) == 1


def test_incomplete_assessment_cannot_resolve_established_degradation(
    adverse: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = monitor(adverse)
    incident = next(i for i in first["incidents"] if i["kind"] == "forecast_degradation")

    # Exercise the unavailable-observation branch after a genuinely measured episode.
    # This supplies no positive metric, skill claim or new eligibility evidence.
    def pending(*args: Any, **kwargs: Any) -> DegradationFacts:
        reference = kwargs["reference"]
        return DegradationFacts(
            status="pending",
            reference_hash=reference.evidence_hash,
            evidence_hash=adverse.facts.evidence_hash,
            window_id=None,
            signals=(),
            investigation_objective=None,
        )

    monkeypatch.setattr(readiness, "assess_degradation", pending)
    repeated = monitor(adverse)
    retained = next(i for i in repeated["incidents"] if i["id"] == incident["id"])
    assert retained["resolved_at"] is None
    assert repeated["evaluation"]["status"] in {"pending", "degraded"}


def test_pending_actual_evidence_is_not_a_profit_or_readiness_claim(case: Case) -> None:
    result = monitor(case)
    assert result["evaluation"]["status"] == "pending"
    assert result["evaluation"]["signals"] == []
    assert result["submission_enabled"] is False
    assert case.paper.tracking.get(case.facts.monitor_id)["status"] == "active"  # type: ignore[index]
    assert diagnostic_jobs(case) == []
    records = case.service.proposals(case.facts.monitor_id)["proposals"]
    assert all(record["status"] == "proposed" for record in records)


def test_legacy_paper_source_gap_cannot_claim_qualification_or_launch_research(case: Case) -> None:
    legacy = create_monitor(case.paper.tracking)
    with controlled_forward_environment(case.clock):
        result = case.service.monitoring(legacy)
    assert result["evaluation"]["status"] == "pending"
    assert result["evaluation"]["signals"] == []
    assert result["investigations"] == []
    assert result["submission_enabled"] is False
    assert case.service._monitor(legacy)["status"] == "active"
    assert case.service.store.listing(legacy) == []
    assert diagnostic_jobs(case) == []


@pytest.mark.parametrize("field", ["source_ref", "model_binding"])
def test_malformed_frozen_metadata_is_a_structured_durable_safety_refusal(
    case: Case, field: str
) -> None:
    statements = {
        "source_ref": "UPDATE monitors SET source_ref=? WHERE id=?",
        "model_binding": "UPDATE monitors SET model_binding=? WHERE id=?",
    }
    with case.paper.jobs.connect() as db:
        db.execute(statements[field], ("{", case.facts.monitor_id))
    result = monitor(case)
    assert result["evaluation"]["status"] == "blocked"
    assert any(s["kind"] == "readiness_integrity" for s in result["evaluation"]["signals"])
    with case.paper.jobs.connect() as db:
        row = db.execute(
            "SELECT status FROM monitors WHERE id=?", (case.facts.monitor_id,)
        ).fetchone()
        assert row[0] == "suspended"
        assert (
            db.execute(
                "SELECT count(*) FROM shadow_alerts WHERE monitor_id=? "
                "AND kind='readiness_integrity' AND resolved_at IS NULL",
                (case.facts.monitor_id,),
            ).fetchone()[0]
            == 1
        )
    assert result["submission_enabled"] is False


def test_other_monitor_incidents_do_not_leak_or_enqueue_for_this_monitor(case: Case) -> None:
    other = create_monitor(case.paper.tracking)
    with case.paper.jobs.connect() as db:
        alerts.observe_condition(
            db,
            other,
            "forecast_degradation",
            active=True,
            evidence={"reason": "CONTROLLED unrelated monitor incident"},
            now=case.clock.now().isoformat(),
        )
    result = monitor(case)
    assert all(i["monitor_id"] == case.facts.monitor_id for i in result["incidents"])
    assert result["investigations"] == []
    assert diagnostic_jobs(case) == []


def test_periodic_monitor_detects_changed_raw_bytes_without_a_database_change(case: Case) -> None:
    first = monitor(case)
    assert first["evaluation"]["status"] == "pending"
    raw = next(
        p for p in (case.paper.jobs.root / "shadow").rglob("*") if p.is_file() and "raw" in p.parts
    )
    original = raw.read_bytes()
    # Break this case's immutable hard link before controlled corruption; the cached
    # source and every other test continue to retain their original receipt bytes.
    raw.unlink()
    raw.write_bytes(original + b"\nCONTROLLED CORRUPTION\n")
    case.clock.advance(timedelta(seconds=61))
    with controlled_forward_environment(case.clock):
        case.service.refresh_monitoring()
    with case.paper.jobs.connect() as db:
        incident = db.execute(
            "SELECT id FROM shadow_alerts WHERE monitor_id=? "
            "AND kind='readiness_integrity' AND resolved_at IS NULL",
            (case.facts.monitor_id,),
        ).fetchone()
        state = db.execute(
            "SELECT status FROM monitors WHERE id=?", (case.facts.monitor_id,)
        ).fetchone()
    assert incident is not None
    assert state[0] == "suspended"
    result = monitor(case)
    assert result["evaluation"]["status"] == "blocked"
    assert result["submission_enabled"] is False
    assert any(i["incident_key"] == incident[0] for i in result["investigations"])


def test_short_legacy_poll_does_not_starve_background_research_monitoring(case: Case) -> None:
    legacy = create_monitor(case.paper.tracking)
    with case.paper.jobs.connect() as db:
        db.execute(
            "UPDATE monitors SET next_at=? WHERE id=?",
            ((case.clock.now() + timedelta(seconds=60)).isoformat(), legacy),
        )
    assert case.service._evaluations == {}
    with controlled_forward_environment(case.clock):
        case.service.refresh_monitoring()
    result = case.service._evaluations[case.facts.monitor_id][1]
    assert result["monitor_id"] == case.facts.monitor_id
    assert result["evaluation"]["status"] == "pending"
    assert result["submission_enabled"] is False
    assert legacy not in case.service._evaluations


def test_changed_model_scope_blocks_without_broadening_diagnostic(case: Case) -> None:
    monitor(case)
    with case.paper.jobs.connect() as db:
        row = db.execute(
            "SELECT model_binding FROM monitors WHERE id=?", (case.facts.monitor_id,)
        ).fetchone()
        binding = json.loads(row[0])
        binding["snapshot"]["model_hash"] = "sha256:" + "a" * 64
        db.execute(
            "UPDATE monitors SET model_binding=? WHERE id=?",
            (json.dumps(binding), case.facts.monitor_id),
        )
    result = monitor(case)
    assert result["evaluation"]["status"] == "blocked"
    assert any(s["kind"] == "readiness_integrity" for s in result["evaluation"]["signals"])
    assert case.service._monitor(case.facts.monitor_id)["status"] == "suspended"
    assert diagnostic_jobs(case) == []
    assert all(i["research_job_id"] is None for i in result["investigations"])


def test_unreviewed_newer_reference_cannot_reset_window_but_owner_review_can(
    case: Case, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = owner_approve(case.service, tmp_path / "first-private")
    when = case.clock.now().replace(minute=0, second=5) + timedelta(days=1)
    commit_controlled_cycle(case.paper, when, clock=case.clock)
    with controlled_forward_environment(case.clock):
        proposed = case.service.create(
            case.facts.monitor_id, {"capital_dollars": "100.00", "max_loss_dollars": "50.00"}
        )
    references: list[str] = []
    actual = assess_degradation

    def capture(*args: Any, **kwargs: Any) -> DegradationFacts:
        references.append(kwargs["reference"].evidence_hash)
        return actual(*args, **kwargs)

    monkeypatch.setattr(readiness, "assess_degradation", capture)
    monitor(case)
    assert references[-1] == first["payload"]["facts"]["evidence_hash"]
    reviewed = owner_approve(case.service, tmp_path / "second-private")
    assert reviewed["id"] == proposed["id"]
    monitor(case)
    assert references[-1] == reviewed["payload"]["facts"]["evidence_hash"]
    assert references[-1] != first["payload"]["facts"]["evidence_hash"]


def test_current_risk_checks_use_verified_account_cost_and_drawdown(adverse: Case) -> None:
    # A lower explicitly proposed envelope is data only. It does not reset account
    # bankroll, positions, original cash or loss history.
    before = adverse.paper.tracking.get(adverse.facts.monitor_id)["paper_account"]  # type: ignore[index]
    with controlled_forward_environment(adverse.clock):
        proposed = adverse.service.create(
            adverse.facts.monitor_id,
            {"capital_dollars": "100.00", "max_loss_dollars": "0.01"},
        )
    payload = proposed["proposal"]["payload"]
    account = payload["facts"]["account"]
    checks = {c["name"]: c["passed"] for c in payload["checks"]}
    assert account["status"] == "simulated"
    assert Decimal(account["drawdown_at_cost"]) > Decimal("0.01")
    assert checks["loss_limits_at_cost"] is False
    exposure = sum((Decimal(p["total_cost"]) for p in account["positions"]), Decimal(0))
    assert checks["exposure_at_cost"] == (exposure <= Decimal("50"))
    assert adverse.paper.tracking.get(adverse.facts.monitor_id)["paper_account"] == before  # type: ignore[index]
    assert payload["submission_enabled"] is False


def test_missing_outcomes_cannot_hide_actual_open_exposure(case: Case, tmp_path: Path) -> None:
    owner_approve(case.service, tmp_path / "private", capital="10.00", loss="10.00")
    before = case.paper.tracking.get(case.facts.monitor_id)["paper_summary"]  # type: ignore[index]
    before_exposure = sum((Decimal(p["total_cost"]) for p in before["positions"]), Decimal(0))
    assert before_exposure > 0
    unavailable = httpx.MockTransport(lambda _: httpx.Response(404, json={"error": "CONTROLLED"}))
    with patch(
        "tests.research_paper_forward_support.outcome_transport_for_monitor",
        return_value=unavailable,
    ):
        # Each actual fixture fill costs $0.35. Preserve the original two held
        # contracts and collect 27 new dates to cross the reviewed $10 envelope.
        for _ in range(27):
            when = case.clock.now().replace(minute=0, second=5) + timedelta(days=1)
            commit_controlled_cycle(case.paper, when, clock=case.clock)
    result = monitor(case)
    checks = {c["name"]: c["passed"] for c in result["evaluation"]["checks"]}
    account = case.paper.tracking.get(case.facts.monitor_id)["paper_summary"]  # type: ignore[index]
    exposure = sum((Decimal(p["total_cost"]) for p in account["positions"]), Decimal(0))
    # A readiness proposal does not alter the existing paper account's separate
    # limits. At the next evaluation, actual held contracts cross this reviewed
    # envelope even though official outcomes are unavailable; none become zero cost.
    assert exposure > Decimal("10")
    assert exposure > before_exposure
    assert account["fill_count"] > before["fill_count"]
    assert account["settlement_count"] == before["settlement_count"]
    assert checks["exposure_at_cost"] is False
    assert checks["settlement_coverage"] is False
    assert any(s["kind"] == "risk_limit_breach" for s in result["evaluation"]["signals"])
    assert case.service._monitor(case.facts.monitor_id)["status"] == "suspended"
    assert result["submission_enabled"] is False


def test_a_new_pinned_policy_has_one_distinct_offline_destination(
    adverse: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = monitor(adverse)
    incident = next(i for i in first["incidents"] if i["kind"] == "forecast_degradation")
    old = next(i for i in first["investigations"] if i["incident_key"] == incident["id"])
    monkeypatch.setattr(readiness, "POLICY", "CONTROLLED-next-review-policy")
    changed = monitor(adverse)
    repeated = monitor(adverse)
    destinations = [i for i in changed["investigations"] if i["incident_key"] == incident["id"]]
    assert len(destinations) == 2
    assert len({i["research_job_id"] for i in destinations}) == 2
    assert len({i["policy_hash"] for i in destinations}) == 2
    assert old["research_job_id"] in {i["research_job_id"] for i in destinations}
    assert [i["id"] for i in repeated["investigations"]] == [
        i["id"] for i in changed["investigations"]
    ]
    for destination in destinations:
        assert_offline(adverse, destination["research_job_id"])
