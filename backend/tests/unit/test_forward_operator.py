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
    label_backlog,
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
            "POST /api/weather/schedules": lambda body: {"config": body, "status": "active"},
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
    kept = FakeApi({"/api/weather/schedules": [{"config": {"id": "s1"}, "status": "active"}]})
    assert ensure_schedule(kept, 3600) == {"action": "schedule_kept", "schedule_id": "s1"}
    paused = FakeApi({"/api/weather/schedules": [{"config": {"id": "s1"}, "status": "paused"}]})
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
            "/api/weather/schedules": [
                {
                    "config": {"id": "s1", "follow_retained": True},
                    "status": "active",
                    "detail": "ok",
                }
            ],
            "/api/weather/partitions": {"total_inputs": 2, "partitions": [{}]},
            "/api/weather/labels": [{}, {}],
            "/api/alerts": {"alerts": [], "submission_enabled": False},
            "/api/monitors/m1/evaluation": _evaluation(matched_events=0, matched_dates=0),
            "/api/weather/label-partitions": [],
        }
    )
    summary = summarize(api, start)
    monitor = summary["monitors"][0]
    assert monitor["cycles_this_run"] == {"completed": 1, "failed": 1}
    assert monitor["latest_cycle"]["sequence"] == 3
    assert monitor["model_binding"] == "blocked"
    assert summary["retained_inputs"] == {"total_inputs": 2, "partitions": 1}
    assert summary["label_requests"] == 2
    assert summary["schedules"][0]["id"] == "s1"
    assert summary["schedules"][0]["follow_retained"] is True
    assert summary["schedules"][0]["backlog"]["dates"] == []
    assert summary["schedules"][0]["backlog"]["next_due_at"] is None
    assert summary["submission_enabled"] is False
    assert summary["alerts"] == []
    prospective = summary["readiness"]["prospective"]
    assert prospective[0]["events_remaining"] == 10
    assert prospective[0]["dates_remaining"] == 5
    assert summary["readiness"]["settlement_labels"]["verified_events"] == 0


def _work(day: str, status: str, next_at: str, *stations: str) -> dict[str, Any]:
    return {
        "day": day,
        "status": status,
        "next_at": next_at,
        "attempts": 0,
        "failures": 0,
        "detail": "Waiting for source receipt",
        "targets": [{"station": s, "event_id": f"{s}-{day}"} for s in stations],
    }


def test_label_backlog_distinguishes_not_yet_due_from_overdue() -> None:
    at = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    schedule = {
        "inflight": None,
        "work": [
            _work("2026-11-06", "pending", "2026-11-07T08:00:00Z", "KLAX", "KNYC"),
            _work("2026-11-05", "pending", "2026-11-06T08:00:00Z", "KLAX"),
            _work("2026-11-04", "retry", "2026-11-06T05:00:00Z", "KNYC"),
            _work("2026-11-03", "verified", "2026-11-07T00:00:00Z", "KNYC"),
            _work("2026-11-02", "refused", "2026-11-01T00:00:00Z", "KNYC"),
        ],
    }
    backlog = label_backlog(schedule, at)
    assert [d["day"] for d in backlog["dates"]] == [
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
    ]
    assert backlog["dates"][-1]["targets"] == 2
    assert backlog["dates"][-1]["stations"] == ["KLAX", "KNYC"]
    # Verified revision checks and refused dates are neither due nor the next label.
    assert backlog["next_due_at"] == "2026-11-06T05:00:00Z"
    assert backlog["overdue_dates"] == ["2026-11-04"]
    # An in-flight request is the schedule advancing, not a stuck backlog.
    assert label_backlog({**schedule, "inflight": "r1"}, at)["overdue_dates"] == []


def test_label_backlog_reports_unparseable_clocks_without_raising() -> None:
    at = datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    schedule = {
        "work": [
            _work("2026-11-05", "pending", "not-a-time", "KNYC"),
            _work("2026-11-04", "pending", "2026-11-05T05:00:00", "KNYC"),
        ]
    }
    backlog = label_backlog(schedule, at)
    assert backlog["next_due_at"] is None
    assert backlog["overdue_dates"] == []
    assert all(d["next_at_invalid"] for d in backlog["dates"])
    assert label_backlog({}, at)["dates"] == []


def _evaluation(*, matched_events: int, matched_dates: int) -> dict[str, Any]:
    return {
        "status": "insufficient",
        "report_hash": "sha256:" + "0" * 64,
        "policy": {"minimum_matched_events": 10, "minimum_matched_dates": 5},
        "counts": {
            "contracts": 24,
            "pending": 20,
            "refused": 4,
            "matched": 0,
            "independent_events": 4,
            "independent_dates": 2,
            "matched_events": matched_events,
            "matched_dates": matched_dates,
        },
        "diagnostics": [],
    }


def _record(event: str, station: str, day: str, *, verified: bool) -> dict[str, Any]:
    return {
        "target": {"event_id": event, "station": station, "target_date": day},
        "observation": {"high_f": 61} if verified else None,
        "refusal": "" if verified else "preliminary report",
    }


def test_readiness_counts_distinct_labels_across_partitions_and_revisions() -> None:
    """A revision re-verifying an event, or an earlier refusal later verified, counts once."""
    first = [
        {"result": {"records": [_record("e1", "KPHL", "2026-11-04", verified=True)]}},
        {"result": {"records": [_record("e2", "KMDW", "2026-11-05", verified=False)]}},
        {"result": None},  # queued request: no batch yet
    ]
    second = [
        {
            "result": {
                "records": [
                    _record("e1", "KPHL", "2026-11-04", verified=True),
                    _record("e2", "KMDW", "2026-11-05", verified=True),
                    _record("e3", "KMDW", "2026-11-06", verified=False),
                ]
            }
        }
    ]
    api = FakeApi(
        {
            "/api/monitors/m1/evaluation": _evaluation(matched_events=12, matched_dates=3),
            "/api/weather/label-partitions": [
                {"partition_id": "00000000"},
                {"partition_id": "00000001"},
            ],
            "/api/weather/label-partitions/00000000": first,
            "/api/weather/label-partitions/00000001": second,
        }
    )
    result = forward.readiness(api, ["m1"])
    labels = result["settlement_labels"]
    assert labels["partitions"] == 2
    assert labels["verified_events"] == 2
    assert labels["verified_dates"] == 2
    assert labels["verified_stations"] == ["KMDW", "KPHL"]
    assert labels["unverified_events"] == 1
    assert labels["unverified_reasons"] == {"preliminary report": 1}
    prospective = result["prospective"][0]
    assert prospective["events_remaining"] == 0  # never negative
    assert prospective["dates_remaining"] == 2
    assert prospective["status"] == "insufficient"
    assert api.posts == []  # readiness never writes


def test_readiness_reports_verification_refusals_without_passing() -> None:
    def refused() -> None:
        raise ApiError(409, "Prospective evidence verification failed; inspect workspace")

    def partitions_refused() -> None:
        raise ApiError(409, "Label partition verification failed")

    api = FakeApi(
        {
            "/api/monitors/m1/evaluation": refused,
            "/api/weather/label-partitions": partitions_refused,
        }
    )
    result = forward.readiness(api, ["m1"])
    assert result["prospective"][0]["status"] == "verification_failed"
    assert "409" in result["prospective"][0]["error"]
    assert result["settlement_labels"]["status"] == "verification_failed"


def test_alert_summary_derives_lifecycle_state_from_clocks() -> None:
    base = {"id": "a", "kind": "stale_collection", "monitor_id": "m1", "opened_at": "t0"}
    assert (
        forward.alert_summary({**base, "acknowledged_at": None, "resolved_at": None})["status"]
        == "open"
    )
    acknowledged = forward.alert_summary({**base, "acknowledged_at": "t1", "resolved_at": None})
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["opened_at"] == "t0"
    assert (
        forward.alert_summary({**base, "acknowledged_at": "t1", "resolved_at": "t2"})["status"]
        == "resolved"
    )


def test_alert_summary_keeps_bounded_evidence_only_while_unresolved() -> None:
    contracts = [{"ticker": f"T{i}", "basis": "close_time"} for i in range(25)]
    alert: dict[str, Any] = {
        "id": "a",
        "kind": "unresolved_reconciliation",
        "monitor_id": "m1",
        "opened_at": "t0",
        "acknowledged_at": None,
        "resolved_at": None,
        "evidence": {"contracts": contracts, "grace_seconds": 3600},
    }
    open_ = forward.alert_summary(alert)
    assert open_["evidence"]["contracts_total"] == 25
    assert [c["ticker"] for c in open_["evidence"]["contracts"]] == [f"T{i}" for i in range(20)]
    assert open_["evidence"]["grace_seconds"] == 3600
    assert alert["evidence"]["contracts"] == contracts  # the API record is not mutated
    small = forward.alert_summary({**alert, "evidence": {"contracts": contracts[:2]}})
    assert small["evidence"] == {"contracts": contracts[:2]}
    assert "evidence" not in forward.alert_summary({**alert, "resolved_at": "t1"})


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
    assert result["readiness"]["prospective"] == []
    assert result["readiness"]["settlement_labels"]["verified_events"] == 0
    assert result["workspace"]["status"] == "ok"
    assert result["workspace"]["areas"]["jobs.sqlite"] > 0
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


def test_label_backlog_reads_the_real_schedule_summary_shape() -> None:
    from datetime import date

    from entropytrade.features.registry import scientific_hash
    from entropytrade.weather.label_schedule import (
        DateWork,
        LabelScheduler,
        Schedule,
        ScheduleConfig,
    )
    from entropytrade.weather.labels import LabelTarget

    dataset = "a" * 64
    day = date(2026, 11, 5)
    targets = (
        LabelTarget(
            event_id="KXHIGHNY-26NOV05",
            station="KNYC",
            target_date=day,
            timezone="America/New_York",
            rules_hashes=("sha256:" + "b" * 64,),
        ),
    )
    work = DateWork(
        key=scientific_hash(
            [dataset, day.isoformat(), [t.model_dump(mode="json") for t in targets]]
        ),
        dataset_id=dataset,
        day=day,
        targets=targets,
        next_at=datetime(2026, 11, 6, 5, tzinfo=UTC),
    )
    created = datetime(2026, 11, 6, 0, tzinfo=UTC)
    schedule = Schedule(
        config=ScheduleConfig(
            id="7ca8e62f-4485-40b7-98aa-446157c1606d", dataset_id=dataset, enabled=True
        ),
        created_at=created,
        updated_at=created,
        next_discovery=created,
        work=(work,),
    )
    summary = json.loads(json.dumps(LabelScheduler.summary(schedule)))
    backlog = label_backlog(summary, datetime(2026, 11, 6, 6, tzinfo=UTC))
    assert backlog["dates"][0]["day"] == "2026-11-05"
    assert backlog["dates"][0]["stations"] == ["KNYC"]
    assert backlog["next_due_at"] == summary["work"][0]["next_at"]
    assert backlog["overdue_dates"] == ["2026-11-05"]


def test_footprint_reports_snapshot_bytes_by_area_against_the_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from entropytrade.api import recovery

    workspace = tmp_path / "workspace"
    for name, size in {
        "jobs.sqlite": 10,
        "jobs.sqlite-wal": 1000,  # runtime: excluded from snapshots and from the footprint
        ".writer.lock": 1000,
        "runs/weather-datasets/abc/snapshot.json": 30,
        "runs/weather-datasets/def/receipts/0000/raw.json": 20,
        "runs/job-1/public/markets.jsonl": 5,
        "shadow/monitor/cycle/result.json": 35,
    }.items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    monkeypatch.setattr(recovery, "MAX_BYTES", 1000)
    report = forward.footprint(workspace)
    assert report["areas"] == {
        "jobs.sqlite": 10,
        "runs": 5,
        "runs/weather-datasets": 50,
        "shadow": 35,
    }
    assert (report["bytes"], report["files"], report["snapshot_budget_bytes"]) == (100, 5, 1000)
    assert (report["budget_used"], report["status"]) == (0.1, "ok")
    monkeypatch.setattr(recovery, "MAX_BYTES", 180)
    assert forward.footprint(workspace)["status"] == "warning"
    monkeypatch.setattr(recovery, "MAX_BYTES", 120)
    assert forward.footprint(workspace)["status"] == "critical"
    assert forward.footprint(tmp_path / "missing")["bytes"] == 0
