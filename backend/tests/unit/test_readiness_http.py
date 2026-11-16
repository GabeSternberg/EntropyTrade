"""HTTP owner/control boundaries, using actual sessions and existing SQLite stores."""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.owner import OwnerAuth, initialize
from entropytrade.api.server import WorkbenchServer
from entropytrade.api.workspace import acquire_workspace
from entropytrade.domain.time import SimulatedClock
from entropytrade.research.readiness import PreparedReview, ResearchReadinessService
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore
from tests.unit.test_workbench_http import REPO, exchange

PHRASE = "CONTROLLED HTTP owner phrase"  # synthetic test input
AUDIENCE = "http://127.0.0.1:43128"
PROPOSAL = "sha256:" + "a" * 64


@pytest.fixture
def governance(tmp_path: Path) -> WorkbenchServer:
    jobs = Jobs(tmp_path / "workspace")
    tracking = TrackingStore(jobs)
    clock = SimulatedClock(datetime(2026, 11, 16, tzinfo=UTC))
    path = initialize(tmp_path / "private/owner.json", REPO, "controlled-owner", PHRASE)
    return cast(
        "WorkbenchServer",
        SimpleNamespace(
            repo=REPO,
            jobs=jobs,
            tracking=tracking,
            server_port=43128,
            token=str(uuid4()),
            owner=OwnerAuth(REPO, path, clock=clock),
            readiness=ResearchReadinessService(jobs.root, tracking, clock=clock),
        ),
    )


def login(server: WorkbenchServer) -> dict[str, str]:
    status, headers, data = exchange(
        server,
        "/api/owner/login",
        method="POST",
        body={"password": PHRASE},
        headers={"X-EntropyTrade-CSRF": server.token},
    )
    assert status == 200
    assert json.loads(data)["authenticated"] is True
    assert "HttpOnly" in headers["Set-Cookie"]
    return {"X-EntropyTrade-CSRF": server.token, "Cookie": headers["Set-Cookie"].split(";", 1)[0]}


def test_owner_bootstrap_login_logout_and_no_setup_endpoint(governance: WorkbenchServer) -> None:
    status, _, data = exchange(governance, "/api/owner")
    assert status == 200
    state = json.loads(data)
    assert state["csrf_token"] == governance.token
    assert state["configured"] is True
    assert state["authenticated"] is False
    assert PHRASE not in data.decode()
    assert (
        exchange(governance, "/api/owner/login", method="POST", body={"password": PHRASE})[0] == 403
    )
    headers = login(governance)
    assert json.loads(exchange(governance, "/api/owner", headers=headers)[2])["authenticated"]
    status, response_headers, data = exchange(
        governance, "/api/owner/logout", method="POST", body={}, headers=headers
    )
    assert status == 200
    assert not json.loads(data)["authenticated"]
    assert "Max-Age=0" in response_headers["Set-Cookie"]
    assert (
        exchange(
            governance,
            "/api/owner/setup",
            method="POST",
            body={"password": PHRASE},
            headers=headers,
        )[0]
        == 404
    )


def test_safe_halt_needs_csrf_and_release_needs_real_owner_session(
    governance: WorkbenchServer,
) -> None:
    csrf = {"X-EntropyTrade-CSRF": governance.token}
    status, _, data = exchange(
        governance,
        "/api/controls/halt",
        method="POST",
        body={"reason": "CONTROLLED safety test"},
        headers=csrf,
    )
    state = json.loads(data)
    assert status == 200
    assert state["halted"]
    assert state["actor"]["kind"] == "system"
    assert state["execution_authorized"] is state["submission_enabled"] is False
    body = {"expected_epoch": state["epoch"], "reason": "CONTROLLED reviewed release"}
    assert (
        exchange(governance, "/api/controls/release", method="POST", body=body, headers=csrf)[0]
        == 401
    )
    headers = login(governance)
    status, _, data = exchange(
        governance, "/api/controls/release", method="POST", body=body, headers=headers
    )
    assert status == 200
    assert not json.loads(data)["halted"]
    assert json.loads(data)["actor"]["actor_id"] == "controlled-owner"


def test_anonymous_review_and_supplied_actor_never_authorize(governance: WorkbenchServer) -> None:
    path = "/api/readiness/" + PROPOSAL + "/review"
    body = {"decision": "approve", "expected_revision": 0, "note": "CONTROLLED"}
    csrf = {"X-EntropyTrade-CSRF": governance.token}
    assert exchange(governance, path, method="POST", body=body, headers=csrf)[0] == 401
    headers = login(governance)
    assert (
        exchange(
            governance,
            path,
            method="POST",
            body={**body, "actor": {"kind": "human"}},
            headers=headers,
        )[0]
        == 400
    )
    assert (
        exchange(governance, "/api/live/orders", method="POST", body={}, headers=headers)[0] == 404
    )


def test_logout_during_evidence_check_blocks_late_http_review(
    governance: WorkbenchServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = login(governance)

    def prepare(proposal_id: str, value: object) -> PreparedReview:
        del value
        governance.owner.logout(headers["Cookie"])
        return PreparedReview(
            proposal_id, "approve", 0, 0, {}, "CONTROLLED", "unused", {}, "2026-11-16T00:00:00Z"
        )

    def forbidden(*args: object) -> None:
        pytest.fail("a logged-out request reached the privileged commit")

    monkeypatch.setattr(governance.readiness, "prepare_review", prepare)
    monkeypatch.setattr(governance.readiness, "commit_review", forbidden)
    assert (
        exchange(
            governance,
            "/api/readiness/" + PROPOSAL + "/review",
            method="POST",
            body={"decision": "approve", "expected_revision": 0, "note": "CONTROLLED"},
            headers=headers,
        )[0]
        == 401
    )


@pytest.mark.parametrize(
    "path", ["/api/controls/halt", "/api/monitors/11111111-1111-4111-8111-111111111111/readiness"]
)
def test_corrupt_sqlite_get_and_post_refuse_with_json(
    governance: WorkbenchServer,
    path: str,
) -> None:
    governance.jobs.path.write_bytes(b"CONTROLLED corrupt SQLite bytes")
    status, _, data = exchange(governance, "/api/controls")
    assert status == 409
    assert "error" in json.loads(data)
    body = (
        {"reason": "CONTROLLED"}
        if path.endswith("halt")
        else {"capital_dollars": "100.00", "max_loss_dollars": "10.00"}
    )
    status, _, data = exchange(
        governance,
        path,
        method="POST",
        body=body,
        headers={"X-EntropyTrade-CSRF": governance.token},
    )
    assert status == 409
    assert "error" in json.loads(data)


def test_existing_runner_invokes_monitoring_and_survives_diagnostic_failure(
    governance: WorkbenchServer,
) -> None:
    runner = ShadowRunner(governance.tracking, REPO)
    calls = []

    def broken() -> None:
        calls.append(True)
        raise sqlite3.DatabaseError("CONTROLLED diagnostic failure")

    runner.health_check = broken
    runner.check_alerts()
    assert calls == [True]
    assert runner.health_error == "DatabaseError"
    runner.next_alert_check = 0
    runner.health_check = lambda: calls.append(False)
    runner.check_alerts()
    assert calls == [True, False]
    assert runner.health_error is None


def test_shutdown_retains_writer_lease_until_monitoring_stops(
    governance: WorkbenchServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = ShadowRunner(governance.tracking, REPO)
    entered, release = threading.Event(), threading.Event()

    def blocked() -> None:
        entered.set()
        assert release.wait(timeout=10)

    runner.health_check = blocked
    runner.start()
    assert entered.wait(timeout=5)
    join = runner.thread.join
    monkeypatch.setattr(runner.thread, "join", lambda timeout: join(timeout=0.01))
    lease = acquire_workspace(governance.jobs.root)
    closed = []
    closer = SimpleNamespace(close=lambda: closed.append(True))
    server = cast(
        "WorkbenchServer",
        SimpleNamespace(research=closer, labels=closer, runner=closer, shadow=runner, lock=lease),
    )
    try:
        with pytest.raises(RuntimeError, match="retain the workspace lease"):
            WorkbenchServer.server_close(server)
        assert closed == [True, True, True]
        assert not lease.closed
        with pytest.raises(BlockingIOError):
            acquire_workspace(governance.jobs.root)
    finally:
        release.set()
        join(timeout=5)
        lease.close()
    assert not runner.thread.is_alive()
