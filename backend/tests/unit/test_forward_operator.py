"""Headless forward-collection operator: decisions, refusals and a real-server lifecycle."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from entropytrade.operations import forward
from entropytrade.operations.forward import (
    ApiError,
    ensure_monitor,
    ensure_schedule,
    operate,
    summarize,
    wait_ready,
)

REPO = Path(__file__).resolve().parents[3]


class FakeApi:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.gets: list[str] = []

    def get(self, path: str) -> Any:
        self.gets.append(path)
        value = self.routes[path]
        return value() if callable(value) else value

    def post(self, path: str, body: dict[str, Any]) -> Any:
        self.posts.append((path, body))
        value = self.routes["POST " + path]
        return value(body) if callable(value) else value


def real_job(job_id: str, *, typed: bool = True, status: str = "completed") -> dict[str, Any]:
    proposals = [
        {"candidate_id": "template-c0", "spec": {"name": "c0"} if typed else None},
        {"candidate_id": "template-c1", "spec": {"name": "c1"}},
    ]
    return {
        "id": job_id,
        "status": status,
        "request": {"idea": forward.OPERATOR_IDEA},
        "result": {"data_kind": "real", "proposals": proposals},
    }


def test_active_monitor_is_kept_without_writes() -> None:
    api = FakeApi({"/api/monitors": [{"id": "m1", "status": "active"}]})
    assert ensure_monitor(api, 600) == {"action": "monitor_kept", "monitor_id": "m1"}
    assert api.posts == []


@pytest.mark.parametrize("status", ["paused", "blocked", "stopped"])
def test_inactive_monitor_is_never_resumed_or_replaced(status: str) -> None:
    api = FakeApi({"/api/monitors": [{"id": "m1", "status": status}]})
    result = ensure_monitor(api, 600)
    assert result["action"] == "operator_review_required"
    assert result["monitors"] == [{"id": "m1", "status": status}]
    assert api.posts == []


def test_first_run_creates_recorded_local_job_then_monitor() -> None:
    polls = iter(
        [
            {"id": "j1", "status": "queued"},
            {"id": "j1", "status": "running"},
            real_job("j1"),
        ]
    )
    api = FakeApi(
        {
            "/api/monitors": [],
            "/api/jobs": [],
            "POST /api/jobs": {"id": "j1"},
            "/api/jobs/j1": lambda: next(polls),
            "POST /api/monitors": {"id": "m9"},
        }
    )
    result = ensure_monitor(api, 900, sleep=lambda _: None)
    assert result["action"] == "monitor_created"
    assert result["monitor_id"] == "m9"
    assert result["job_created"] is True
    job_post, monitor_post = api.posts
    assert job_post == ("/api/jobs", forward.JOB_REQUEST)
    # Local templates only: never a provider, never synthetic data.
    assert job_post[1]["enable_provider"] is False
    assert job_post[1]["mode"] == "recorded"
    assert monitor_post == (
        "/api/monitors",
        {"job_id": "j1", "candidate_id": "template-c0", "interval_seconds": 900},
    )


def test_existing_completed_operator_job_is_reused() -> None:
    api = FakeApi(
        {
            "/api/monitors": [],
            "/api/jobs": [
                {"id": "j0", "status": "completed", "request": {"idea": "other"}},
                {"id": "j1", "status": "completed", "request": {"idea": forward.OPERATOR_IDEA}},
            ],
            "/api/jobs/j1": real_job("j1", typed=False),
            "POST /api/monitors": {"id": "m2"},
        }
    )
    # j1 has typed candidate template-c1 only (template-c0 lacks a spec).
    result = ensure_monitor(api, 600)
    assert result["job_created"] is False
    assert api.posts == [
        ("/api/monitors", {"job_id": "j1", "candidate_id": "template-c1", "interval_seconds": 600})
    ]


def test_job_without_typed_real_candidate_blocks_monitor() -> None:
    job = real_job("j1")
    job["result"]["data_kind"] = "synthetic"
    api = FakeApi(
        {
            "/api/monitors": [],
            "/api/jobs": [],
            "POST /api/jobs": {"id": "j1"},
            "/api/jobs/j1": job,
        }
    )
    result = ensure_monitor(api, 600, sleep=lambda _: None)
    assert result["action"] == "monitor_blocked"
    assert [path for path, _ in api.posts] == ["/api/jobs"]


def test_research_job_deadline_blocks_monitor() -> None:
    api = FakeApi(
        {
            "/api/monitors": [],
            "/api/jobs": [],
            "POST /api/jobs": {"id": "j1"},
            "/api/jobs/j1": {"id": "j1", "status": "running"},
        }
    )
    result = ensure_monitor(api, 600, sleep=lambda _: None, job_timeout=0.0)
    assert result == {
        "action": "monitor_blocked",
        "reason": "research job deadline",
        "job_id": "j1",
    }


def test_schedule_waits_for_retained_inputs() -> None:
    api = FakeApi({"/api/weather/schedules": [], "/api/weather/partitions": {"total_inputs": 0}})
    assert ensure_schedule(api, 3600)["action"] == "schedule_waiting"
    assert api.posts == []


def test_schedule_freezes_dataset_and_opts_in_once() -> None:
    api = FakeApi(
        {
            "/api/weather/schedules": [],
            "/api/weather/partitions": {"total_inputs": 3},
            "POST /api/weather/datasets": {"dataset_id": "sha256:" + "a" * 64},
            "POST /api/weather/schedules": lambda body: {"id": body["id"]},
        }
    )
    result = ensure_schedule(api, 7200)
    assert result["action"] == "schedule_created"
    (freeze_path, freeze), (path, body) = api.posts
    assert (freeze_path, freeze) == ("/api/weather/datasets", {})
    assert path == "/api/weather/schedules"
    assert body["dataset_id"] == "a" * 64
    assert body["enabled"] is True
    assert body["follow_retained"] is True
    assert body["interval_seconds"] == 7200
    assert body["batch_dates"] == 8
    assert result["schedule_id"] == body["id"]


def test_existing_schedules_are_kept_or_reported_never_resumed() -> None:
    kept = FakeApi({"/api/weather/schedules": [{"id": "s1", "status": "active"}]})
    assert ensure_schedule(kept, 3600) == {"action": "schedule_kept", "schedule_id": "s1"}
    paused = FakeApi({"/api/weather/schedules": [{"id": "s1", "status": "paused"}]})
    assert ensure_schedule(paused, 3600)["action"] == "operator_review_required"
    assert kept.posts == paused.posts == []


def test_summary_counts_only_this_runs_cycles() -> None:
    start = datetime(2026, 11, 5, 12, tzinfo=UTC)
    cycles = [
        {"sequence": 1, "status": "completed", "started_at": "2026-11-05T11:00:00+00:00"},
        {"sequence": 2, "status": "failed", "started_at": "2026-11-05T12:05:00+00:00"},
        {"sequence": 3, "status": "completed", "started_at": "2026-11-05T12:15:00+00:00"},
    ]
    api = FakeApi(
        {
            "/api/monitors": [{"id": "m1"}],
            "/api/monitors/m1": {
                "id": "m1",
                "status": "active",
                "failures": 0,
                "cycle_count": 3,
                "cycles": cycles,
                "model_binding": {"status": "blocked"},
                "fills": [],
                "submission_enabled": False,
            },
            "/api/weather/schedules": [{"id": "s1", "status": "active", "detail": "ok"}],
            "/api/weather/partitions": {"total_inputs": 2, "partitions": [{}]},
            "/api/weather/labels": [{}, {}],
            "/api/alerts": {"alerts": [], "submission_enabled": False},
        }
    )
    summary = summarize(api, start)
    monitor = summary["monitors"][0]
    assert monitor["cycles_this_run"] == {"completed": 1, "failed": 1}
    assert monitor["latest_cycle"]["sequence"] == 3
    assert monitor["model_binding"] == "blocked"
    assert summary["retained_inputs"] == {"total_inputs": 2, "partitions": 1}
    assert summary["label_requests"] == 2
    assert summary["submission_enabled"] is False


class _Running:
    returncode = None

    def poll(self) -> None:
        return None


def test_wait_ready_refuses_submission_enabled_server() -> None:
    api = FakeApi({"/api/catalog": {"submission_enabled": True}})
    with pytest.raises(RuntimeError, match="submissions enabled"):
        wait_ready(api, _Running())  # type: ignore[arg-type]


def test_http_api_reports_server_errors() -> None:
    error = ApiError(400, "bad")
    assert error.status == 400
    assert "HTTP 400: bad" in str(error)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
def cache_workspace() -> Any:
    """The server only accepts workspaces under the repository's ignored data/cache."""
    import shutil
    import uuid

    root = REPO / "data" / "cache" / f"test-forward-operator-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_operate_starts_and_cleanly_stops_real_server(cache_workspace: Path) -> None:
    """Real listener lifecycle without a monitor, so no public network request is made."""
    tmp_path = cache_workspace
    log = tmp_path / "server.log"
    result = operate(
        REPO,
        tmp_path / "workspace",
        port=_free_port(),
        seconds=1,
        monitor_interval=600,
        schedule_interval=3600,
        log_path=log,
        create_monitor=False,
        poll=0.2,
    )
    assert result["errors"] == []
    assert result["server_exit_code"] == 0
    assert result["schema"] == forward.SCHEMA
    assert result["monitors"] == []
    assert result["submission_enabled"] is False
    assert [a["action"] for a in result["actions"]] == ["schedule_waiting"]
    json.dumps(result)
    # The workspace lease is released: a second operation can start immediately.
    again = operate(
        REPO,
        tmp_path / "workspace",
        port=_free_port(),
        seconds=1,
        monitor_interval=600,
        schedule_interval=3600,
        log_path=log,
        create_monitor=False,
        poll=0.2,
    )
    assert again["errors"] == []
    assert again["server_exit_code"] == 0
