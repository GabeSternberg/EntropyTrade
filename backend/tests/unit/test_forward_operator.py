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


def test_label_backlog_shows_what_the_retained_portal_receipt_said() -> None:
    from entropytrade.weather.labels import LabelBatch, LabelTarget
    from tests.unit.test_weather_labels import receipt

    day = "2026-10-30"
    batch = LabelBatch(
        source_dataset="sha256:" + "a" * 64,
        protected_events=(),
        targets=(
            LabelTarget(
                event_id="KXHIGHPHIL-26OCT30",
                station="CLIPHL",
                target_date=datetime.fromisoformat(day).date(),
                timezone="America/New_York",
                rules_hashes=("controlled-unit-rule",),
            ),
        ),
        receipts=(receipt(day),),  # authentic retained bytes; the portal was preliminary
    )
    retry = {**_work(day, "retry", "2026-11-06T13:27:00Z", "CLIPHL"), "last_batch": batch.version}
    corrupt = {
        **_work("2026-10-29", "retry", "2026-11-06T13:27:00Z", "CLIPHL"),
        "last_batch": "sha256:" + "f" * 64,
    }
    pending = {**_work("2026-10-31", "pending", "2026-11-07T06:00:00Z", "CLIPHL")}
    api = FakeApi(
        {
            "/api/weather/labels/" + batch.version.removeprefix("sha256:"): batch.model_dump(
                mode="json"
            ),
            # A server returning a different batch than the recorded version is refused.
            "/api/weather/labels/" + "f" * 64: batch.model_dump(mode="json"),
        }
    )
    schedule = {"inflight": None, "work": [retry, corrupt, pending]}
    backlog = label_backlog(
        schedule,
        datetime(2026, 11, 6, 10, tzinfo=UTC),
        forward.label_sources(api, schedule),
    )
    by_day = {d["day"]: d for d in backlog["dates"]}
    source = by_day[day]["source"]
    assert source["batch"] == batch.version
    assert source["portal"]["preliminaryReports"] == 45
    assert source["stations"]["CLIPHL"]["status"] == "preliminary"
    assert source["stations"]["CLIPHL"]["isOfficial"] is False
    assert by_day["2026-10-29"]["source"] == {"error": "ValueError: label batch identity mismatch"}
    assert "source" not in by_day["2026-10-31"]  # pending dates have no receipt yet
    assert len(api.gets) == 2


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
    # No monitor, so no cycles: growth cannot be attributed and nothing is projected.
    assert result["runway"]["status"] == "unmeasured"
    assert result["runway"]["cycles_this_run"] == 0
    # Start and end rows join the chain ledger; with no cycles nothing is projected.
    assert [r["monitor_cycles"] for r in result["runway_ledger"]] == [0, 0]
    assert result["chain_runway"]["status"] == "unmeasured"
    assert result["chain_runway"]["ledger_reset"] is None
    assert result["disk"]["free_bytes"] > 0
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
    for name, (size, fill) in {
        "jobs.sqlite": (10, b"j"),
        "jobs.sqlite-wal": (1000, b"w"),  # runtime: excluded from snapshots and the footprint
        ".writer.lock": (1000, b"l"),
        "runs/weather-datasets/abc/snapshot.json": (30, b"a"),
        # An immutable dataset copy of the shadow receipt below: stored once in a snapshot.
        "runs/weather-datasets/def/shadow/digest/result.json": (35, b"r"),
        "runs/job-1/public/markets.jsonl": (5, b"m"),
        "shadow/monitor/cycle/result.json": (35, b"r"),
    }.items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fill * size)
    monkeypatch.setattr(recovery, "MAX_BYTES", 1000)
    monkeypatch.setattr(recovery, "MAX_EXPANDED_BYTES", 2000)
    report = forward.footprint(workspace)
    assert report["areas"] == {
        "jobs.sqlite": 10,
        "runs": 5,
        "runs/weather-datasets": 65,
        "shadow": 35,
    }
    assert (report["bytes"], report["distinct_bytes"], report["files"]) == (115, 80, 5)
    assert (report["snapshot_budget_bytes"], report["expanded_budget_bytes"]) == (1000, 2000)
    assert (report["budget_used"], report["status"]) == (0.08, "ok")
    # Distinct bytes bind the archive budget; expanded bytes bind what a restore writes.
    monkeypatch.setattr(recovery, "MAX_BYTES", 150)
    assert forward.footprint(workspace)["status"] == "warning"
    monkeypatch.setattr(recovery, "MAX_BYTES", 95)
    assert forward.footprint(workspace)["status"] == "critical"
    monkeypatch.setattr(recovery, "MAX_BYTES", 1000)
    monkeypatch.setattr(recovery, "MAX_EXPANDED_BYTES", 140)
    assert forward.footprint(workspace)["status"] == "critical"
    assert forward.footprint(tmp_path / "missing")["bytes"] == 0


def _footprint(bytes_: int, distinct: int, files: int) -> dict[str, Any]:
    return {
        "bytes": bytes_,
        "distinct_bytes": distinct,
        "files": files,
        "snapshot_budget_bytes": 2000,
        "expanded_budget_bytes": 4000,
    }


def test_runway_projects_the_binding_budget_from_measured_growth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from entropytrade.api import recovery

    monkeypatch.setattr(recovery, "MAX_FILES", 1000)
    at = datetime(2026, 11, 6, 15, tzinfo=UTC)
    # Expanded bytes grow 2.5x faster than distinct bytes (datasets copy receipts).
    start, end = _footprint(1000, 500, 100), _footprint(1100, 540, 110)
    report = forward.runway(
        start, end, 4, at=at, boundaries=["2026-12-16", "2026-12-28", "2027-01-27"]
    )
    budgets = report["budgets"]
    assert budgets["expanded_bytes"] == {
        "growth_this_run": 100,
        "per_cycle": 25.0,
        "remaining": 2900,
        "cycles_left": 116,
    }
    assert budgets["distinct_bytes"]["cycles_left"] == 146  # 1460 // 10
    assert budgets["files"]["cycles_left"] == 356  # 890 // 2.5
    assert (report["binding"], report["cycles_left"]) == ("expanded_bytes", 116)
    # 116 cycles at the stated 6/day assumption: 19.3 days, before the validation end.
    assert (report["days_left"], report["exhausted_on"]) == (19.3, "2026-11-25")
    assert report["validation_end"] == "2027-01-27"
    assert report["status"] == "short_of_validation_end"
    longer = forward.runway(
        start,
        end,
        4,
        at=at,
        boundaries=["2026-12-16", "2026-12-28", "2027-01-27"],
        cycles_per_day=1.0,
    )
    assert (longer["exhausted_on"], longer["status"]) == ("2027-03-02", "covers_validation_end")
    assert forward.runway(start, end, 4, at=at, boundaries=None)["status"] == "measured"


def test_runway_refuses_to_project_without_measured_growth() -> None:
    at = datetime(2026, 11, 6, tzinfo=UTC)
    same = _footprint(1000, 500, 100)
    assert forward.runway(None, same, 3, at=at, boundaries=None)["status"] == "unmeasured"
    assert forward.runway(same, same, 0, at=at, boundaries=None)["status"] == "unmeasured"
    flat = forward.runway(same, same, 2, at=at, boundaries=None)
    assert flat["status"] == "unmeasured"
    assert flat["budgets"]["expanded_bytes"]["cycles_left"] is None
    # Already over a budget: zero cycles left, never negative.
    over = forward.runway(
        _footprint(3990, 500, 100), _footprint(4010, 510, 101), 1, at=at, boundaries=None
    )
    assert (over["binding"], over["cycles_left"], over["days_left"]) == ("expanded_bytes", 0, 0.0)


def test_frozen_calendar_reads_the_shared_dataset_partition(tmp_path: Path) -> None:
    root = tmp_path / "runs" / "weather-datasets"
    assert forward.frozen_calendar(tmp_path) is None
    (root / ("b" * 64)).mkdir(parents=True)
    (root / ("b" * 64) / "snapshot.json").write_text(
        json.dumps(
            {"identity": {"temporal_boundaries": ["2026-12-16", "2026-12-28", "2027-01-27"]}}
        )
    )
    (root / ".building-x").mkdir()  # never read: not a published dataset
    (root / ("a" * 64)).mkdir()
    (root / ("a" * 64) / "snapshot.json").write_text("{not json")
    assert forward.frozen_calendar(tmp_path) == ["2026-12-16", "2026-12-28", "2027-01-27"]


def _row(at: str, cycles: int, bytes_: int, distinct: int, files: int, run: str) -> dict[str, Any]:
    return {
        "at": at,
        "run_id": run,
        "monitor_cycles": cycles,
        "bytes": bytes_,
        "distinct_bytes": distinct,
        "files": files,
    }


def test_chain_runway_averages_uneven_runs_over_the_trailing_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from entropytrade.api import recovery

    monkeypatch.setattr(recovery, "MAX_FILES", 1000)
    at = datetime(2026, 11, 6, 16, tzinfo=UTC)
    ledger = [
        # Outside the 7-day window: never used for the projection.
        _row("2026-10-28T00:00:00+00:00", 0, 100, 50, 10, "old"),
        # Run A wrote a discovery dataset: 2 cycles, 100 expanded bytes.
        _row("2026-11-06T10:00:00+00:00", 10, 1000, 500, 100, "a"),
        _row("2026-11-06T11:00:00+00:00", 12, 1100, 540, 110, "a"),
        # Run B wrote none: 2 cycles, only 20 expanded bytes. Alone it overstates runway.
        _row("2026-11-06T14:00:00+00:00", 12, 1110, 542, 111, "b"),
        _row("2026-11-06T15:00:00+00:00", 14, 1130, 550, 114, "b"),
    ]
    end = _footprint(1130, 550, 114)
    report = forward.chain_runway(
        ledger, end, at=at, boundaries=["2026-12-16", "2026-12-28", "2027-01-27"]
    )
    assert report["basis"] == "chain"
    assert report["since"] == "2026-11-06T10:00:00+00:00"
    assert (report["rows_in_window"], report["runs_in_window"]) == (4, 2)
    assert report["cycles_in_window"] == 4
    expanded = report["budgets"]["expanded_bytes"]
    assert expanded == {
        "growth_in_window": 130,
        "per_cycle": 32.5,
        "remaining": 2870,
        "cycles_left": 88,  # 2870 // 32.5
    }
    assert (report["binding"], report["cycles_left"]) == ("expanded_bytes", 88)
    assert report["status"] == "short_of_validation_end"
    # The single run B alone measures 10 bytes/cycle and projects far more runway.
    alone = forward.runway(ledger[3], end, 2, at=at, boundaries=None)
    assert alone["budgets"]["expanded_bytes"]["cycles_left"] == 287
    assert forward.chain_runway([], end, at=at, boundaries=None)["status"] == "unmeasured"
    single = forward.chain_runway(ledger[-1:], end, at=at, boundaries=None)
    assert single["status"] == "unmeasured"


def test_ledger_extends_only_a_continuing_chain_and_retires_old_rows(tmp_path: Path) -> None:
    at = datetime(2026, 11, 6, 16, tzinfo=UTC)
    previous = [
        _row("2026-10-01T00:00:00+00:00", 0, 10, 10, 1, "ancient"),
        _row("2026-11-06T10:00:00+00:00", 10, 1000, 500, 100, "a"),
    ]
    new = [
        _row("2026-11-06T14:00:00+00:00", 10, 1010, 505, 101, "b"),
        _row("2026-11-06T15:00:00+00:00", 11, 1020, 510, 102, "b"),
    ]
    chained, reset = forward.extend_ledger(previous, new, at=at)
    assert reset is None
    assert [r["run_id"] for r in chained] == ["a", "b", "b"]  # 30-day retirement
    # A fork restored from an older snapshot has fewer cycles: old rows are dropped.
    fork = [_row("2026-11-06T14:00:00+00:00", 5, 900, 450, 90, "fork")]
    chained, reset = forward.extend_ledger(previous, fork, at=at)
    assert chained == fork
    assert reset is not None
    assert "restarted" in reset
    # Clocks that run backwards also restart the ledger.
    late = [_row("2026-11-06T09:00:00+00:00", 12, 1100, 540, 110, "c")]
    assert forward.extend_ledger(previous, late, at=at)[0] == late
    # Reading: absent is empty; any malformed row discards the whole file with a reason.
    assert forward.read_ledger(None) == ([], None)
    assert forward.read_ledger(tmp_path / "missing.jsonl") == ([], None)
    good = tmp_path / "ledger.jsonl"
    good.write_text("".join(json.dumps(r) + "\n" for r in previous))
    assert forward.read_ledger(good) == (previous, None)
    for bad in (
        "{not json",
        json.dumps({**previous[1], "bytes": -1}),
        json.dumps({**previous[1], "bytes": True}),
        json.dumps({**previous[1], "at": "2026-11-06T10:00:00"}),
        json.dumps({k: v for k, v in previous[1].items() if k != "files"}),
    ):
        path = tmp_path / "bad.jsonl"
        path.write_text(json.dumps(previous[0]) + "\n" + bad + "\n")
        rows, reason = forward.read_ledger(path)
        assert rows == []
        assert reason is not None
        assert reason.startswith("previous ledger unreadable")


def test_disk_headroom_reports_the_workspace_filesystem(tmp_path: Path) -> None:
    report = forward.disk_headroom(tmp_path / "not" / "yet" / "created")
    assert report["total_bytes"] > 0
    assert 0 <= report["free_bytes"] <= report["total_bytes"]


def test_main_writes_the_chained_ledger_and_carries_it_through_unmeasured_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = [_row("2026-11-06T10:00:00+00:00", 10, 1000, 500, 100, "a")]
    ledger_in = tmp_path / "in.jsonl"
    ledger_in.write_text("".join(json.dumps(r) + "\n" for r in previous))
    seen: dict[str, Any] = {}

    def fake_operate(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        chained = [*kwargs["ledger"], _row("2026-11-06T15:00:00+00:00", 11, 1010, 505, 101, "b")]
        return {
            "errors": [],
            "server_exit_code": 0,
            "runway_ledger": chained,
            "chain_runway": {"status": "measured", "ledger_reset": None},
        }

    def run(*extra: str) -> None:
        monkeypatch.setattr(forward, "operate", fake_operate)
        monkeypatch.setattr("sys.argv", ["forward", "--workspace", str(tmp_path), *extra])
        forward.main()

    out = tmp_path / "out.jsonl"
    summary = tmp_path / "summary.json"
    run(
        "--summary", str(summary), "--ledger-in", str(ledger_in), "--ledger-out", str(out),
        "--run-id", "b",
    )  # fmt: skip
    assert seen["run_id"] == "b"
    assert seen["ledger"] == previous
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["run_id"] for r in rows] == ["a", "b"]
    assert "runway_ledger" not in json.loads(summary.read_text())  # kept out of the summary

    # A run that measured nothing (e.g. the API failed) carries the previous rows unchanged.
    def unmeasured(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"errors": [], "server_exit_code": 0}

    monkeypatch.setattr(forward, "operate", unmeasured)
    carried = tmp_path / "carried.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "forward", "--workspace", str(tmp_path), "--summary", str(tmp_path / "s2.json"),
            "--ledger-in", str(out), "--ledger-out", str(carried),
        ],
    )  # fmt: skip
    forward.main()
    assert carried.read_text() == out.read_text()

    # An unreadable previous ledger is reported, never silently trusted.
    ledger_in.write_text("{broken\n")
    run(
        "--summary", str(tmp_path / "s3.json"), "--ledger-in", str(ledger_in),
        "--ledger-out", str(tmp_path / "o3.jsonl"),
    )  # fmt: skip
    assert seen["ledger"] == []
    reset = json.loads((tmp_path / "s3.json").read_text())["chain_runway"]["ledger_reset"]
    assert reset.startswith("previous ledger unreadable")
