"""Readiness service uses actual synthetic history and real owner-session guards."""

import asyncio
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.owner import OwnerAuth, OwnerAuthError, initialize
from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.domain.strategy import ProbabilityModelRef, StrategySpec
from entropytrade.domain.time import SimulatedClock
from entropytrade.exchange.gateway import GatewayError
from entropytrade.exchange.kalshi.gateway import KalshiGateway
from entropytrade.execution.fee_evidence import FeeEvidenceStore, FeeVersion
from entropytrade.research.readiness import ReadinessEligibilityError, ResearchReadinessService
from entropytrade.research.readiness_evidence import ReadinessFacts
from entropytrade.tracking.evaluate import shadow_limits
from entropytrade.tracking.store import TrackingStore
from tests.research_paper_forward_support import (
    commit_controlled_cycle,
    controlled_forward_environment,
)
from tests.research_paper_support import PaperFixture
from tests.research_readiness_support import readiness_fixture
from tests.support import order_request

REPO = Path(__file__).resolve().parents[3]
AUDIENCE = "http://127.0.0.1:43128"
PASSWORD = secrets.token_urlsafe(32)
ENVELOPE = {"capital_dollars": "100.00", "max_loss_dollars": "10.00"}


@pytest.fixture(scope="module")
def source(tmp_path_factory: pytest.TempPathFactory) -> tuple[PaperFixture, ReadinessFacts]:
    return readiness_fixture(tmp_path_factory.mktemp("readiness-service-source") / "workspace")


@dataclass
class Case:
    paper: PaperFixture
    service: ResearchReadinessService
    facts: ReadinessFacts
    clock: SimulatedClock
    auth: OwnerAuth
    cookie: str
    timer: list[float]


@pytest.fixture
def case(source: tuple[PaperFixture, ReadinessFacts], tmp_path: Path) -> Case:
    original, facts = source
    workspace = tmp_path / "workspace"

    def isolated(source: str, destination: str) -> str:
        # SQLite is mutable; all other receipts/artifacts are immutable hard links.
        if source.endswith((".sqlite", "-wal", "-shm")):
            shutil.copy2(source, destination)
        else:
            os.link(source, destination)
        return destination

    shutil.copytree(original.jobs.root, workspace, copy_function=isolated)
    tracking = TrackingStore(Jobs(workspace))
    clock = SimulatedClock(facts.evidence_as_of)
    service = ResearchReadinessService(
        workspace, tracking, clock=clock, expected_data_kind="synthetic"
    )
    paper = PaperFixture(
        tracking.jobs,
        tracking,
        original.service,
        original.job_id,
        original.experiment_id,
        original.request,
        original.result,
    )
    private = tmp_path / "owner-private"
    private.mkdir(mode=0o700)
    path = initialize(private / "owner.json", REPO, "controlled-owner", PASSWORD)
    timer = [0.0]
    auth = OwnerAuth(REPO, path, clock=clock, timer=lambda: timer[0])
    cookie = auth.set_cookie(auth.login(PASSWORD, AUDIENCE)).split(";", 1)[0]
    return Case(paper, service, facts, clock, auth, cookie, timer)


def create(case: Case) -> dict[str, Any]:
    with controlled_forward_environment(case.clock):
        return case.service.create(case.facts.monitor_id, ENVELOPE)


def detail(case: Case, proposal: str) -> dict[str, Any]:
    with controlled_forward_environment(case.clock):
        return case.service.detail(proposal)


def prepare(case: Case, proposal: str, revision: int = 0) -> Any:
    with controlled_forward_environment(case.clock):
        return case.service.prepare_review(
            proposal,
            {
                "decision": "approve",
                "expected_revision": revision,
                "note": "CONTROLLED owner reviewed actual synthetic paper evidence",
            },
        )


def test_freeze_is_idempotent_when_only_current_clock_advances(case: Case) -> None:
    first = create(case)
    case.clock.advance(timedelta(hours=2))
    second = create(case)
    assert first["id"] == second["id"]
    assert first["proposal"]["payload"] == second["proposal"]["payload"]
    assert first["proposal"]["payload"]["facts"]["scores"]["independent_events"] == 21
    assert first["proposal"]["payload"]["facts"]["source_refs"]["data_kind"] == "synthetic"
    assert first["proposal"]["payload"]["execution_authorized"] is False


def test_authenticated_owner_review_never_enables_exchange_submission(case: Case) -> None:
    created = create(case)
    before = case.paper.tracking.get(case.facts.monitor_id)["paper_account"]  # type: ignore[index]
    prepared = prepare(case, created["id"])
    with case.auth.authorize(case.cookie, AUDIENCE) as principal:
        reviewed = case.service.commit_review(prepared, principal)
    assert reviewed["status"] == "approved"
    assert reviewed["events"][-1]["actor"]["kind"] == "human"
    assert reviewed["payload"]["submission_enabled"] is False
    assert reviewed["payload"]["execution_authorized"] is False
    assert case.paper.tracking.get(case.facts.monitor_id)["paper_account"] == before  # type: ignore[index]
    requests: list[httpx.Request] = []

    def receive(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    async def attempt() -> None:
        gateway = KalshiGateway(
            environment=KalshiEnvironment.PRODUCTION,
            environ={"ENTROPYTRADE_LIVE_TRADING_ENABLED": "true"},
            transport=httpx.MockTransport(receive),
        )
        try:
            with pytest.raises(GatewayError, match="read_only"):
                await gateway.submit_order(order_request())
        finally:
            await gateway.aclose()

    asyncio.run(attempt())
    assert requests == []


def test_caller_cannot_replace_owner_authentication_with_actor_object(case: Case) -> None:
    created = create(case)
    prepared = prepare(case, created["id"])
    with pytest.raises(OwnerAuthError, match="authenticated owner"):
        case.service.commit_review(prepared, {"kind": "human", "actor_id": "fake"})  # type: ignore[arg-type]
    assert case.service.store.get(created["id"])["status"] == "proposed"  # type: ignore[index]


def test_owner_session_is_rechecked_at_privileged_commit(case: Case) -> None:
    created = create(case)
    prepared = prepare(case, created["id"])
    with case.auth.authorize(case.cookie, AUDIENCE) as principal:
        case.timer[0] = 1801.0
        with pytest.raises(OwnerAuthError, match="expired"):
            case.service.commit_review(prepared, principal)
    assert case.service.store.get(created["id"])["status"] == "proposed"  # type: ignore[index]


def test_expiry_during_fee_verification_refuses_review(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = create(case)
    prepared = prepare(case, created["id"])
    original = FeeEvidenceStore.snapshot

    def slow_snapshot(store: FeeEvidenceStore) -> tuple[FeeVersion, ...]:
        fees = original(store)
        case.timer[0] = 1801.0
        return fees

    with case.auth.authorize(case.cookie, AUDIENCE) as principal:
        monkeypatch.setattr(FeeEvidenceStore, "snapshot", slow_snapshot)
        with pytest.raises(OwnerAuthError, match="expired"):
            case.service.commit_review(prepared, principal)
    assert case.service.store.get(created["id"])["status"] == "proposed"  # type: ignore[index]


def test_production_service_refuses_actual_synthetic_fixture(case: Case) -> None:
    production = ResearchReadinessService(
        case.paper.jobs.root, case.paper.tracking, clock=case.clock
    )
    with controlled_forward_environment(case.clock):
        record = production.create(case.facts.monitor_id, ENVELOPE)
        assert not record["proposal"]["payload"]["eligible"]
        with pytest.raises(ReadinessEligibilityError):
            production.prepare_review(
                record["id"],
                {
                    "decision": "approve",
                    "expected_revision": 0,
                    "note": "CONTROLLED real-policy refusal",
                },
            )


@pytest.mark.parametrize(
    "extra",
    [
        {"actor": {"kind": "human"}},
        {"facts": {"eligible": True}},
        {"risk_limits": {}},
        {"data_kind": "real"},
    ],
)
def test_request_cannot_override_actor_proof_risk_or_provenance(
    case: Case, extra: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="only"):
        case.service.create(case.facts.monitor_id, ENVELOPE | extra)


def test_current_fee_expiry_invalidates_frozen_proposal(case: Case) -> None:
    created = create(case)
    case.clock.advance(timedelta(days=400))
    current = detail(case, created["id"])
    assert current["status"] == "invalidated"
    assert not current["current_checks"]["eligible"]
    assert any(
        c["name"].startswith("current_fees") and not c["passed"]
        for c in current["current_checks"]["checks"]
    )


def test_risk_policy_change_requires_new_review(
    case: Case, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.research import readiness

    created = create(case)
    original = shadow_limits()
    monkeypatch.setattr(
        readiness, "shadow_limits", lambda: original.revalidated(max_loss=Decimal("999"))
    )
    current = detail(case, created["id"])
    assert current["status"] == "invalidated"
    assert not current["current_checks"]["eligible"]


def test_changed_model_cannot_reuse_approval(case: Case) -> None:
    created = create(case)
    spec = StrategySpec.model_validate(case.paper.tracking.get(case.facts.monitor_id)["spec"])  # type: ignore[index]
    spec = spec.revalidated(
        model_ref=ProbabilityModelRef(family="ridge", version="sha256:" + "a" * 64)
    )
    with case.paper.jobs.connect() as db:
        db.execute(
            "UPDATE monitors SET spec=?,spec_hash=? WHERE id=?",
            (spec.model_dump_json(), spec.spec_hash(), case.facts.monitor_id),
        )
    current = detail(case, created["id"])
    assert current["status"] == "invalidated"
    assert not current["current_checks"]["eligible"]


def test_no_review_can_commit_after_emergency_halt(case: Case) -> None:
    created = create(case)
    prepared = prepare(case, created["id"])
    case.service.store.halt("CONTROLLED emergency halt after source verification")
    with (
        case.auth.authorize(case.cookie, AUDIENCE) as principal,
        pytest.raises(ValueError, match="changed"),
    ):
        case.service.commit_review(prepared, principal)
    assert case.service.store.get(created["id"])["status"] != "approved"  # type: ignore[index]


def test_append_only_cycle_blocks_stale_cas_but_allows_fresh_review(case: Case) -> None:
    created = create(case)
    prepared = prepare(case, created["id"])
    next_point = case.clock.now().replace(minute=0, second=5) + timedelta(days=1)
    commit_controlled_cycle(case.paper, next_point, clock=case.clock)
    with (
        case.auth.authorize(case.cookie, AUDIENCE) as principal,
        pytest.raises(ValueError, match="changed"),
    ):
        case.service.commit_review(prepared, principal)
    current = detail(case, created["id"])
    assert current["status"] == "proposed"
    assert current["current_checks"]["eligible"]
    refreshed = prepare(case, created["id"])
    with case.auth.authorize(case.cookie, AUDIENCE) as principal:
        assert case.service.commit_review(refreshed, principal)["status"] == "approved"


def test_stalled_collection_blocks_review_without_background_runner(case: Case) -> None:
    created = create(case)
    case.clock.advance(timedelta(days=2))
    with pytest.raises(ReadinessEligibilityError):
        prepare(case, created["id"])
