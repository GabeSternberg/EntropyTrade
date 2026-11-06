"""Headless, bounded operation of authentic forward collection.

Runs the existing private website server for a fixed window and drives it only through the
same localhost HTTP API the browser uses. It keeps one continuous shadow monitor collecting
public market/forecast receipts and, once retained inputs exist, one opt-in forward-validation
schedule acquiring source-matched settlement labels. Everything is read-only: the server has no
order transport, submissions stay disabled and no credentials are read or forwarded.

The operator never resumes a paused monitor or schedule. A pause (operator or the automatic
repeated-failure pause) is reported as requiring review instead of being overridden. Original
receipt clocks, frozen calendars and protected holdouts are owned by the existing services and
are not touched here. Summaries describe this run's activity; they are not empirical evidence
of model quality or profitability.

Usage (workspace must be stopped/unused; see docs/forward-operator.md):

    python -m entropytrade.operations.forward --workspace data/cache/forward \
        --seconds 1500 --summary data/cache/forward-summary.json
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

SCHEMA = "entropytrade-forward-operator-v1"
# Recorded-mode local-template research on the bundled weather dataset. It only provides a
# typed candidate spec for the monitor; it is never promoted and its insufficiency is kept.
OPERATOR_IDEA = "Test forecast_high_f > 70"
JOB_REQUEST = {
    "idea": OPERATOR_IDEA,
    "family": "weather",
    "mode": "recorded",
    "reasoning": "local",
    "enable_provider": False,
}
SCHEDULE_RETRY_SECONDS = 300.0
TERMINAL_JOB = {"completed", "failed", "cancelled", "interrupted"}


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class Api(Protocol):
    def get(self, path: str) -> Any: ...

    def post(self, path: str, body: dict[str, Any]) -> Any: ...


class HttpApi:
    """Same-origin JSON client for the localhost workbench."""

    def __init__(self, port: int, timeout: float = 300.0) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self.timeout = timeout
        self.token = ""

    def _send(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            try:
                message = str(json.loads(exc.read()).get("error", exc.reason))
            except ValueError:
                message = str(exc.reason)
            raise ApiError(exc.code, message) from exc

    def get(self, path: str) -> Any:
        # Fixed http://127.0.0.1 base; paths are constants from this module.
        return self._send(urllib.request.Request(self.base + path))  # noqa: S310

    def post(self, path: str, body: dict[str, Any]) -> Any:
        if not self.token:
            self.token = str(self.get("/api/catalog")["csrf_token"])
        data = json.dumps(body).encode()
        request = urllib.request.Request(  # noqa: S310 - fixed localhost base
            self.base + path,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "X-EntropyTrade-CSRF": self.token},
        )
        return self._send(request)


def now() -> datetime:
    return datetime.now(UTC)


def _typed_candidates(job: dict[str, Any]) -> list[str]:
    result = job.get("result") or {}
    if job.get("status") != "completed" or result.get("data_kind") != "real":
        return []
    return [str(p["candidate_id"]) for p in result.get("proposals", []) if p.get("spec")]


def ensure_monitor(
    api: Api,
    interval_seconds: int,
    *,
    sleep: Callable[[float], None] = time.sleep,
    job_timeout: float = 300.0,
) -> dict[str, Any]:
    """Keep exactly the existing active monitor, or create the first one. Never resume."""
    monitors = api.get("/api/monitors")
    active = [m for m in monitors if m.get("status") == "active"]
    if active:
        return {"action": "monitor_kept", "monitor_id": active[0]["id"]}
    if monitors:
        return {
            "action": "operator_review_required",
            "reason": "existing monitor is not active; the operator never resumes a pause",
            "monitors": [{"id": m["id"], "status": m.get("status")} for m in monitors],
        }
    jobs = [
        api.get("/api/jobs/" + j["id"])
        for j in api.get("/api/jobs")
        if j.get("request", {}).get("idea") == OPERATOR_IDEA and j.get("status") == "completed"
    ]
    job = next((j for j in jobs if _typed_candidates(j)), None)
    created_job = False
    if job is None:
        job_id = str(api.post("/api/jobs", dict(JOB_REQUEST))["id"])
        created_job = True
        deadline = time.monotonic() + job_timeout
        while True:
            job = api.get("/api/jobs/" + job_id)
            if job.get("status") in TERMINAL_JOB:
                break
            if time.monotonic() > deadline:
                return {
                    "action": "monitor_blocked",
                    "reason": "research job deadline",
                    "job_id": job_id,
                }
            sleep(2.0)
    candidates = _typed_candidates(job)
    if not candidates:
        return {
            "action": "monitor_blocked",
            "reason": "research job produced no typed real candidate",
            "job_id": job["id"],
            "job_status": job.get("status"),
        }
    monitor = api.post(
        "/api/monitors",
        {"job_id": job["id"], "candidate_id": candidates[0], "interval_seconds": interval_seconds},
    )
    return {
        "action": "monitor_created",
        "monitor_id": monitor["id"],
        "job_id": job["id"],
        "job_created": created_job,
        "candidate_id": candidates[0],
        "interval_seconds": interval_seconds,
    }


def schedule_id(schedule: dict[str, Any]) -> str:
    """Schedule summaries nest their identity in the validated configuration."""
    return str(schedule["config"]["id"])


def ensure_schedule(api: Api, interval_seconds: int) -> dict[str, Any]:
    """Enable one following forward-validation schedule once retained inputs exist."""
    schedules = api.get("/api/weather/schedules")
    if schedules:
        active = [s for s in schedules if s.get("status") == "active"]
        if active:
            return {"action": "schedule_kept", "schedule_id": schedule_id(active[0])}
        return {
            "action": "operator_review_required",
            "reason": "existing schedule is not active; the operator never resumes a pause",
            "schedules": [{"id": schedule_id(s), "status": s.get("status")} for s in schedules],
        }
    partitions = api.get("/api/weather/partitions")
    if not partitions.get("total_inputs"):
        return {"action": "schedule_waiting", "reason": "no retained public/shadow inputs yet"}
    snapshot = api.post("/api/weather/datasets", {})
    dataset_id = str(snapshot["dataset_id"]).removeprefix("sha256:")
    schedule = api.post(
        "/api/weather/schedules",
        {
            "id": str(uuid.uuid4()),
            "dataset_id": dataset_id,
            "enabled": True,
            "interval_seconds": interval_seconds,
            "batch_dates": 8,
            "follow_retained": True,
        },
    )
    return {
        "action": "schedule_created",
        "schedule_id": schedule_id(schedule),
        "dataset_id": dataset_id,
        "follow_retained": True,
        "interval_seconds": interval_seconds,
    }


def summarize(api: Api, started_at: datetime) -> dict[str, Any]:
    """Describe workspace state and this run's activity without copying raw evidence."""
    monitors = []
    for row in api.get("/api/monitors"):
        detail = api.get("/api/monitors/" + row["id"])
        cycles = detail.get("cycles", [])
        recent = [c for c in cycles if str(c.get("started_at", "")) >= started_at.isoformat()]
        latest = max(cycles, key=lambda c: int(c.get("sequence", 0)), default=None)
        monitors.append(
            {
                "id": detail["id"],
                "status": detail.get("status"),
                "failures": detail.get("failures"),
                "cycle_count": detail.get("cycle_count"),
                "next_at": detail.get("next_at"),
                "model_binding": (detail.get("model_binding") or {}).get("status")
                if isinstance(detail.get("model_binding"), dict)
                else detail.get("model_binding"),
                "cycles_this_run": dict(sorted(Counter(c.get("status") for c in recent).items())),
                "latest_cycle": None
                if latest is None
                else {k: latest.get(k) for k in ("sequence", "status", "detail", "started_at")},
                "fills": len(detail.get("fills") or []),
                "submission_enabled": detail.get("submission_enabled"),
            }
        )
    at = now()
    schedules = [
        {
            "id": schedule_id(s),
            "follow_retained": s["config"].get("follow_retained"),
            **{k: s.get(k) for k in ("status", "detail", "updated_at", "next_discovery", "counts")},
            "inflight": s.get("inflight"),
            "backlog": label_backlog(s, at),
        }
        for s in api.get("/api/weather/schedules")
    ]
    partitions = api.get("/api/weather/partitions")
    alerts = api.get("/api/alerts")
    return {
        "monitors": monitors,
        "schedules": schedules,
        "retained_inputs": {
            "total_inputs": partitions.get("total_inputs"),
            "partitions": len(partitions.get("partitions", [])),
        },
        "label_requests": len(api.get("/api/weather/labels")),
        "alerts": [alert_summary(a) for a in alerts.get("alerts", [])],
        "readiness": readiness(api, [m["id"] for m in monitors]),
        "submission_enabled": bool(alerts.get("submission_enabled")),
    }


def label_backlog(schedule: dict[str, Any], at: datetime) -> dict[str, Any]:
    """Per-date label work, so zero labels reads as 'not yet due' or 'overdue', never vague.

    A pending/retry date becomes due at the end of its local day (then on backoff). Work that
    is due at summary time while no request is in flight means the schedule did not advance
    while the server was running; it is reported, never repaired here.
    """
    dates = []
    for work in schedule.get("work") or []:
        targets = work.get("targets") or []
        dates.append(
            {
                "day": work.get("day"),
                "status": work.get("status"),
                "next_at": work.get("next_at"),
                "attempts": work.get("attempts"),
                "failures": work.get("failures"),
                "targets": len(targets),
                "stations": sorted({str(t.get("station")) for t in targets}),
                "detail": work.get("detail"),
            }
        )
    dates.sort(key=lambda d: (str(d["day"]), str(d["next_at"])))
    waiting = []
    for d in dates:
        if d["status"] in {"pending", "retry"}:
            try:
                when = datetime.fromisoformat(str(d["next_at"]))
            except ValueError:
                when = None
            if when is None or when.tzinfo is None:
                d["next_at_invalid"] = True  # Reported; the schedule service owns validation.
                continue
            waiting.append((when, d))
    due = [d for when, d in waiting if when <= at]
    first = min(waiting, key=lambda item: item[0], default=None)
    return {
        "dates": dates,
        "next_due_at": None if first is None else first[1]["next_at"],
        "overdue_dates": [] if schedule.get("inflight") else [d["day"] for d in due],
        "summarized_at": at.isoformat(),
    }


def alert_summary(alert: dict[str, Any]) -> dict[str, Any]:
    """Alerts carry lifecycle clocks; derive the state rather than reading absent keys."""
    status = (
        "resolved"
        if alert.get("resolved_at")
        else "acknowledged"
        if alert.get("acknowledged_at")
        else "open"
    )
    return {
        "status": status,
        **{
            k: alert.get(k)
            for k in ("id", "kind", "monitor_id", "opened_at", "acknowledged_at", "resolved_at")
        },
    }


def _prospective(api: Api, monitor_id: str) -> dict[str, Any]:
    try:
        report = api.get(f"/api/monitors/{monitor_id}/evaluation")
    except ApiError as exc:
        # A verification refusal is reported, never repaired or retried into a pass.
        return {"monitor_id": monitor_id, "status": "verification_failed", "error": str(exc)}
    counts = report.get("counts", {})
    policy = report.get("policy", {})
    need_events = int(policy.get("minimum_matched_events", 0))
    need_dates = int(policy.get("minimum_matched_dates", 0))
    matched_events = int(counts.get("matched_events", 0))
    matched_dates = int(counts.get("matched_dates", 0))
    return {
        "monitor_id": monitor_id,
        "status": report.get("status"),
        "report_hash": report.get("report_hash"),
        **{
            k: counts.get(k)
            for k in (
                "contracts",
                "pending",
                "refused",
                "matched",
                "independent_events",
                "independent_dates",
            )
        },
        "matched_events": matched_events,
        "matched_dates": matched_dates,
        "minimum_matched_events": need_events,
        "minimum_matched_dates": need_dates,
        "events_remaining": max(0, need_events - matched_events),
        "dates_remaining": max(0, need_dates - matched_dates),
        "diagnostic_groups": [
            {k: g.get(k) for k in ("data_kind", "status", "independent_events", "reason")}
            for g in report.get("diagnostics", [])
        ],
    }


def _labels(api: Api) -> dict[str, Any]:
    """Distinct station/day labels across every retained partition (revisions count once)."""
    verified: dict[str, dict[str, Any]] = {}
    refused: dict[str, str] = {}
    partitions = api.get("/api/weather/label-partitions")
    for partition in partitions:
        for request in api.get("/api/weather/label-partitions/" + partition["partition_id"]):
            for record in (request.get("result") or {}).get("records", []):
                target = record["target"]
                if record.get("observation") is not None:
                    verified[target["event_id"]] = target
                else:
                    refused[target["event_id"]] = str(record.get("refusal", ""))
    never_verified = {e: r for e, r in refused.items() if e not in verified}
    return {
        "partitions": len(partitions),
        "verified_events": len(verified),
        "verified_dates": len({t["target_date"] for t in verified.values()}),
        "verified_stations": sorted({t["station"] for t in verified.values()}),
        "unverified_events": len(never_verified),
        "unverified_reasons": dict(sorted(Counter(never_verified.values()).items())),
    }


def readiness(api: Api, monitor_ids: list[str]) -> dict[str, Any]:
    """Progress toward the existing evidence thresholds; counts only, never a quality claim."""
    try:
        labels: dict[str, Any] = _labels(api)
    except (ApiError, KeyError, TypeError) as exc:
        labels = {"status": "verification_failed", "error": f"{type(exc).__name__}: {exc}"}
    return {
        "prospective": [_prospective(api, m) for m in monitor_ids],
        "settlement_labels": labels,
        "note": "Counts of retained authentic evidence; not model quality, returns or V1.",
    }


def wait_ready(api: Api, process: subprocess.Popen[bytes], timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited during startup with code {process.returncode}")
        try:
            catalog = api.get("/api/catalog")
        except (OSError, ApiError):
            time.sleep(1.0)
            continue
        if catalog.get("submission_enabled") is not False:
            raise RuntimeError("refusing to operate: server reports submissions enabled")
        return
    raise RuntimeError("server did not become ready")


def stop(process: subprocess.Popen[bytes], timeout: float = 240.0) -> int:
    """Request the server's normal Ctrl-C shutdown so workers record interruptions."""
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=30)
    return int(process.returncode)


def operate(
    repo: Path,
    workspace: Path,
    *,
    port: int,
    seconds: int,
    monitor_interval: int,
    schedule_interval: int,
    log_path: Path,
    create_monitor: bool = True,
    poll: float = 30.0,
) -> dict[str, Any]:
    started_at = now()
    actions: list[dict[str, Any]] = []
    errors: list[str] = []
    api = HttpApi(port)
    with log_path.open("ab") as log:
        # Fixed argv: this interpreter, the bundled server module and validated options.
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "entropytrade.api.server",
                "--workspace",
                str(workspace),
                "--port",
                str(port),
            ],
            cwd=repo,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        summary: dict[str, Any] = {}
        try:
            wait_ready(api, process)
            if create_monitor:
                actions.append({"at": now().isoformat(), **ensure_monitor(api, monitor_interval)})
            deadline = time.monotonic() + seconds
            scheduled = False
            next_attempt = 0.0
            while True:
                if not scheduled and time.monotonic() >= next_attempt:
                    try:
                        result = ensure_schedule(api, schedule_interval)
                    except (ApiError, OSError, KeyError, TypeError, ValueError) as exc:
                        # Retried later; an already-created schedule is then found and kept.
                        result = {
                            "action": "schedule_error",
                            "reason": f"{type(exc).__name__}: {exc}",
                        }
                        next_attempt = time.monotonic() + SCHEDULE_RETRY_SECONDS
                    if (
                        result["action"] != "schedule_waiting"
                        or not actions
                        or (actions[-1].get("action") != "schedule_waiting")
                    ):
                        actions.append({"at": now().isoformat(), **result})
                    scheduled = result["action"] not in {"schedule_waiting", "schedule_error"}
                if time.monotonic() >= deadline or process.poll() is not None:
                    break
                time.sleep(min(poll, max(0.0, deadline - time.monotonic())))
            summary = summarize(api, started_at)
        except (ApiError, OSError, RuntimeError, KeyError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            exit_code = stop(process)
    return {
        "schema": SCHEMA,
        "started_at": started_at.isoformat(),
        "finished_at": now().isoformat(),
        "window_seconds": seconds,
        "actions": actions,
        "errors": errors,
        "server_exit_code": exit_code,
        **summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded headless authentic forward collection")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=1500)
    parser.add_argument("--port", type=int, default=43128)
    parser.add_argument("--monitor-interval", type=int, default=600)
    parser.add_argument("--schedule-interval", type=int, default=3600)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if not 60 <= args.seconds <= 5 * 3600:
        parser.error("--seconds must be 60-18000")
    if args.summary.exists():
        parser.error("--summary already exists; use a new path")
    repo = Path(__file__).resolve().parents[4]
    workspace = args.workspace if args.workspace.is_absolute() else repo / args.workspace
    log = args.log or args.summary.with_suffix(".server.log")
    result = operate(
        repo,
        workspace,
        port=args.port,
        seconds=args.seconds,
        monitor_interval=args.monitor_interval,
        schedule_interval=args.schedule_interval,
        log_path=log,
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief = {k: result.get(k) for k in ("actions", "errors", "server_exit_code", "readiness")}
    brief["open_alerts"] = [a for a in result.get("alerts", []) if a.get("status") != "resolved"]
    sys.stdout.write(json.dumps(brief) + "\n")
    if result["errors"] or result["server_exit_code"] != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
