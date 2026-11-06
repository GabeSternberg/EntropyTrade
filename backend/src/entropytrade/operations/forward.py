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
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
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
            "backlog": label_backlog(s, at, label_sources(api, s)),
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


FOOTPRINT_WARNING = 0.5
FOOTPRINT_CRITICAL = 0.8


def footprint(workspace: Path) -> dict[str, Any]:
    """Bytes the next snapshot will carry, by area, against both snapshot budgets.

    Read-only. Snapshots store each distinct content once, so file contents are hashed to
    count distinct bytes (against ``MAX_BYTES``); expanded bytes are what a restore writes
    (against ``MAX_EXPANDED_BYTES``). The tighter of the two drives ``status``. Runtime files
    the snapshot excludes (locks, WAL/SHM, caches) are excluded here too.
    """
    from entropytrade.api.recovery import MAX_BYTES, MAX_EXPANDED_BYTES, RUNTIME
    from entropytrade.data.sources import file_hash

    areas: Counter[str] = Counter()
    distinct: dict[str, int] = {}
    files = 0

    def count(area: str, path: Path) -> None:
        nonlocal files
        size = path.stat().st_size
        areas[area] += size
        distinct.setdefault(file_hash(path), size)
        files += 1

    if workspace.is_dir():
        for child in sorted(workspace.iterdir()):
            if child.name in RUNTIME or child.is_symlink():
                continue
            if child.is_file():
                count(child.name, child)
                continue
            for path in sorted(child.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    parts = path.relative_to(workspace).parts
                    area = (
                        "/".join(parts[:2])
                        if parts[:2] == ("runs", "weather-datasets")
                        else (parts[0])
                    )
                    count(area, path)
    total = sum(areas.values())
    unique = sum(distinct.values())
    used = max(unique / MAX_BYTES, total / MAX_EXPANDED_BYTES)
    return {
        "bytes": total,
        "distinct_bytes": unique,
        "files": files,
        "areas": dict(sorted(areas.items())),
        "snapshot_budget_bytes": MAX_BYTES,
        "expanded_budget_bytes": MAX_EXPANDED_BYTES,
        "budget_used": round(used, 4),
        "status": "critical"
        if used >= FOOTPRINT_CRITICAL
        else "warning"
        if used >= FOOTPRINT_WARNING
        else "ok",
    }


# Projection cadence: the 4-hourly cron (6 windows/day) at one monitor cycle per scheduled
# window. An assumption stated in every summary, never a measurement.
CYCLES_PER_DAY = 6.0


def frozen_calendar(workspace: Path) -> list[str] | None:
    """Temporal boundaries every frozen weather dataset shares (read-only, unverified copy).

    The dataset builder refuses conflicting partitions, so any one manifest names them.
    """
    root = workspace / "runs" / "weather-datasets"
    for manifest in sorted(root.glob("[0-9a-f]" * 64 + "/snapshot.json")):
        try:
            boundaries = json.loads(manifest.read_text())["identity"]["temporal_boundaries"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(boundaries, list) and len(boundaries) == 3:
            return [str(b) for b in boundaries]
    return None


def runway(
    start: dict[str, Any] | None,
    end: dict[str, Any],
    cycles: int,
    *,
    at: datetime,
    boundaries: list[str] | None,
    cycles_per_day: float = CYCLES_PER_DAY,
) -> dict[str, Any]:
    """How many more monitor cycles fit before a snapshot budget refuses the workspace.

    Growth is measured between this run's start and end footprints and divided by the cycles
    completed in this run, so it includes the discovery datasets and label receipts the same
    window wrote. A workspace over any budget cannot be snapshotted and the chain stalls
    (receipts are never deleted to make room). Days are extrapolated at ``cycles_per_day``.
    The calendar's validation end is the last date the fixed fit/calibration/validation
    partitions need; a runway shorter than that cannot reach the empirical model gates.
    """
    from entropytrade.api.recovery import MAX_FILES

    result: dict[str, Any] = {
        "cycles_this_run": cycles,
        "cycles_per_day_assumed": cycles_per_day,
        "validation_end": boundaries[2] if boundaries else None,
    }
    if start is None or cycles <= 0:
        return {**result, "status": "unmeasured", "reason": "no start footprint or no cycles"}
    budgets = {
        "expanded_bytes": ("bytes", end["expanded_budget_bytes"]),
        "distinct_bytes": ("distinct_bytes", end["snapshot_budget_bytes"]),
        "files": ("files", MAX_FILES),
    }
    limits: dict[str, Any] = {}
    for name, (key, budget) in budgets.items():
        growth = int(end[key]) - int(start[key])
        per_cycle = growth / cycles
        left = budget - int(end[key])
        limits[name] = {
            "growth_this_run": growth,
            "per_cycle": round(per_cycle, 1),
            "remaining": left,
            "cycles_left": None if per_cycle <= 0 else max(0, int(left // per_cycle)),
        }
    finite = {k: v["cycles_left"] for k, v in limits.items() if v["cycles_left"] is not None}
    result["budgets"] = limits
    if not finite:
        return {**result, "status": "unmeasured", "reason": "no measured growth this run"}
    binding = min(finite, key=lambda k: finite[k])
    days = finite[binding] / cycles_per_day
    exhausted = (at + timedelta(days=days)).date()
    result.update(
        binding=binding,
        cycles_left=finite[binding],
        days_left=round(days, 1),
        exhausted_on=exhausted.isoformat(),
    )
    if boundaries is None:
        return {**result, "status": "measured"}
    short = exhausted < date.fromisoformat(boundaries[2])
    return {**result, "status": "short_of_validation_end" if short else "covers_validation_end"}


# Chain ledger: one row per footprint measurement (start and end of every run), carried from
# run to run beside the snapshot. Operational metadata only; never evidence, never restored
# into the workspace. A single run's growth is uneven (a window may or may not write a
# discovery dataset or label receipts), so the chain projection averages over a trailing
# window of runs instead.
LEDGER_KEYS = ("at", "monitor_cycles", "bytes", "distinct_bytes", "files")
LEDGER_MAX_ROWS = 256
LEDGER_RETAIN_DAYS = 30
CHAIN_WINDOW_DAYS = 7.0


def read_ledger(path: Path | None) -> tuple[list[dict[str, Any]], str | None]:
    """Parse a previous ledger; any malformed row discards the whole ledger (with a reason)."""
    if path is None or not path.is_file():
        return [], None
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or any(k not in row for k in LEDGER_KEYS):
                raise ValueError("ledger row lacks required keys")
            if any(
                isinstance(row[k], bool) or not isinstance(row[k], int) or row[k] < 0
                for k in LEDGER_KEYS[1:]
            ):
                raise ValueError("ledger counts must be non-negative integers")
            at = datetime.fromisoformat(str(row["at"]))
            if at.tzinfo is None:
                raise ValueError("ledger clocks must be timezone-aware")
            rows.append(row)
    except (OSError, ValueError) as exc:
        return [], f"previous ledger unreadable: {type(exc).__name__}: {exc}"
    return rows, None


def ledger_row(
    footprint_: dict[str, Any], *, at: datetime, monitor_cycles: int, run_id: str | None
) -> dict[str, Any]:
    return {
        "at": at.isoformat(),
        "run_id": run_id,
        "monitor_cycles": monitor_cycles,
        "bytes": int(footprint_["bytes"]),
        "distinct_bytes": int(footprint_["distinct_bytes"]),
        "files": int(footprint_["files"]),
    }


def extend_ledger(
    previous: list[dict[str, Any]], rows: list[dict[str, Any]], *, at: datetime
) -> tuple[list[dict[str, Any]], str | None]:
    """Append this run's rows; restart the ledger if it does not continue this workspace.

    A previous ledger continues this workspace only if its clocks and monitor cycle counts
    never decrease into this run's first row. Otherwise (a fresh chain, a fork restored from
    an older snapshot, a clock error) the old rows describe another workspace and are dropped,
    so they can never distort the projection. Rows older than 30 days are retired.
    """
    reason = None
    combined = [*previous, *rows]
    for before, after in pairwise(combined):
        if (
            datetime.fromisoformat(after["at"]) < datetime.fromisoformat(before["at"])
            or after["monitor_cycles"] < before["monitor_cycles"]
        ):
            reason = "previous ledger does not continue this workspace; restarted"
            combined = list(rows)
            break
    cutoff = at - timedelta(days=LEDGER_RETAIN_DAYS)
    kept = [r for r in combined if datetime.fromisoformat(r["at"]) >= cutoff]
    return kept[-LEDGER_MAX_ROWS:], reason


def chain_runway(
    ledger: list[dict[str, Any]],
    end: dict[str, Any],
    *,
    at: datetime,
    boundaries: list[str] | None,
    cycles_per_day: float = CYCLES_PER_DAY,
    window_days: float = CHAIN_WINDOW_DAYS,
) -> dict[str, Any]:
    """The same projection as ``runway`` over a trailing window of chained runs.

    Growth is measured from the oldest ledger row inside the window to the newest row (this
    run's end), divided by the monitor cycles completed between them. It therefore averages
    runs that wrote discovery datasets or label receipts with runs that did not.
    """
    if not ledger:
        return {"basis": "chain", "status": "unmeasured", "reason": "no ledger rows"}
    newest = ledger[-1]
    since = datetime.fromisoformat(newest["at"]) - timedelta(days=window_days)
    oldest = next(r for r in ledger if datetime.fromisoformat(r["at"]) >= since)
    cycles = newest["monitor_cycles"] - oldest["monitor_cycles"]
    report = runway(
        oldest,
        {**end, **{k: newest[k] for k in ("bytes", "distinct_bytes", "files")}},
        cycles,
        at=at,
        boundaries=boundaries,
        cycles_per_day=cycles_per_day,
    )
    report.pop("cycles_this_run", None)
    for budget in report.get("budgets", {}).values():
        budget["growth_in_window"] = budget.pop("growth_this_run")
    return {
        "basis": "chain",
        "window_days": window_days,
        "since": oldest["at"],
        "rows_in_window": sum(1 for r in ledger if datetime.fromisoformat(r["at"]) >= since),
        "runs_in_window": len(
            {r.get("run_id") for r in ledger if datetime.fromisoformat(r["at"]) >= since}
        ),
        "cycles_in_window": cycles,
        **report,
    }


def disk_headroom(workspace: Path) -> dict[str, Any]:
    """Free space on the filesystem holding the workspace (evidence for a budget decision).

    A snapshot copies the whole workspace into a staging payload before compressing it, so a
    restored workspace needs roughly twice its expanded bytes free at snapshot time. Read-only.
    """
    import shutil

    target = workspace if workspace.exists() else workspace.parent
    while not target.exists() and target != target.parent:
        target = target.parent
    usage = shutil.disk_usage(target)
    return {"total_bytes": usage.total, "free_bytes": usage.free}


DATASET_DIR = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,127}$")
# Parts of a frozen dataset: the capture copies (`receipts/NNNN/`, `shadow/<digest>/`), label
# copies, the replay/rows/features derived from them, and the manifest.
DATASET_PARTS = {
    "receipts": "receipts",
    "shadow": "shadow",
    "labels": "labels",
    "scalar-labels": "scalar_labels",
    "shadow-replay.json": "shadow_replay",
    "dataset": "rows",
    "features": "features",
    "snapshot.json": "manifest",
}


def dataset_ids(workspace: Path) -> set[str]:
    """Published weather dataset directories (by content id); read-only."""
    root = workspace / "runs" / "weather-datasets"
    if not root.is_dir():
        return set()
    return {p.name for p in root.iterdir() if p.is_dir() and DATASET_DIR.match(p.name)}


def _tree_bytes(root: Path) -> tuple[int, int]:
    size = files = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            size += path.stat().st_size
            files += 1
    return size, files


def _input_bytes(workspace: Path, input_id: str) -> int | None:
    """Bytes of one retained catalog input (shadow cycle or public job), if it is found."""
    if not SAFE_ID.match(input_id):
        return None
    roots = [workspace / "runs" / input_id, *sorted(workspace.glob(f"shadow/*/{input_id}"))]
    found = [r for r in roots if r.is_dir() and not r.is_symlink()]
    if len(found) != 1:
        return None
    return _tree_bytes(found[0])[0]


def dataset_costs(workspace: Path, before: set[str] | None) -> dict[str, Any]:
    """What the datasets published during this run cost, per discovered input (read-only).

    One run's dataset growth depends on how many inputs its discovery froze: discovery runs
    on the schedule's own clock, so a window can freeze several earlier windows' cycles at
    once, or none. This turns that attribution into a measurement: for each new dataset, the
    inputs its selection names, their current retained bytes, the dataset's bytes split by
    part, and the ratio. Unfinished `.building-*` staging directories (left by an interrupted
    freeze) are reported separately because the footprint counts them too.
    """
    root = workspace / "runs" / "weather-datasets"
    if before is None:
        return {"status": "unmeasured", "reason": "no start inventory"}
    written = []
    for name in sorted(dataset_ids(workspace) - before):
        directory = root / name
        parts: Counter[str] = Counter()
        files = 0
        for path in directory.rglob("*"):
            if path.is_file() and not path.is_symlink():
                top = path.relative_to(directory).parts[0]
                parts[DATASET_PARTS.get(top, "other")] += path.stat().st_size
                files += 1
        selection: Any = None
        captures: Any = None
        try:
            manifest = json.loads((directory / "snapshot.json").read_text())
            selection = manifest["identity"].get("selection")
            captures = manifest.get("capture_count")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
        inputs = selection.get("inputs") if isinstance(selection, dict) else None
        inputs = [str(i) for i in inputs] if isinstance(inputs, list) else None
        sizes = [_input_bytes(workspace, i) for i in inputs] if inputs else []
        input_bytes = (
            sum(s for s in sizes if s is not None) if sizes and None not in sizes else None
        )
        total = sum(parts.values())
        written.append(
            {
                "dataset_id": name,
                "discovery": selection.get("discovery") if isinstance(selection, dict) else None,
                "inputs": len(inputs) if inputs is not None else None,
                "captures": captures,
                "bytes": total,
                "files": files,
                "parts": dict(sorted(parts.items())),
                "input_bytes": input_bytes,
                "bytes_per_input": round(total / len(inputs), 1) if inputs else None,
                "ratio_to_inputs": round(total / input_bytes, 3) if input_bytes else None,
            }
        )
    staging = (
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith(".building-")]
        if root.is_dir()
        else []
    )
    counted = [w for w in written if w["inputs"]]
    total_inputs = sum(w["inputs"] for w in counted)
    total_bytes = sum(w["bytes"] for w in written)
    measured = [w for w in counted if w["input_bytes"]]
    return {
        "status": "measured",
        "written": written,
        "datasets_this_run": len(written),
        "bytes_this_run": total_bytes,
        "inputs_this_run": total_inputs,
        "bytes_per_input": round(sum(w["bytes"] for w in counted) / total_inputs, 1)
        if total_inputs
        else None,
        "ratio_to_inputs": round(
            sum(w["bytes"] for w in measured) / sum(w["input_bytes"] for w in measured), 3
        )
        if measured
        else None,
        "staging_leftovers": len(staging),
        "staging_bytes": sum(_tree_bytes(p)[0] for p in staging),
    }


BINDING_STATION = re.compile(r"\((CLI[A-Z]{3})\)")


def station_bindings(workspace: Path) -> dict[str, Any]:
    """Whether each configured location's captured contract rules name its station.

    Read-only. Uses the newest retained shadow capture (by its manifest ``decision_time``):
    its frozen ``weather_config`` and its ``markets.jsonl``. For each location it counts the
    captured contracts, the station codes the rules name (``... at Dallas (CLIDFW) ...``), the
    contracts the existing label gate (``compatible_rules``) accepts for that station, and
    whether the label source supports the station/timezone. ``matched`` needs every captured
    contract to pass that gate. A ``mismatch`` (rules name another station) or ``unnamed``
    location receives no labels, because the label gate refuses it; this only reports it.
    """
    from entropytrade.weather.labels import STATIONS, compatible_rules

    newest: tuple[str, Path] | None = None
    for manifest_path in sorted(workspace.glob("shadow/*/*/public/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            continue
        if manifest.get("family") != "weather" or not isinstance(
            manifest.get("decision_time"), str
        ):
            continue
        if newest is None or manifest["decision_time"] > newest[0]:
            newest = (manifest["decision_time"], manifest_path.parent)
    if newest is None:
        return {"status": "no_capture", "locations": []}
    decision, root = newest
    manifest = json.loads((root / "manifest.json").read_text())
    by_series: dict[str, list[dict[str, Any]]] = {}
    for line in (root / "markets.jsonl").read_text().splitlines():
        market = json.loads(line)["market"]
        by_series.setdefault(str(market.get("series_ticker")), []).append(market)
    locations = []
    for location in manifest["weather_config"]["locations"]:
        station = location["station"]
        markets = by_series.get(location["series"], [])
        named: Counter[str] = Counter()
        compatible = 0
        for market in markets:
            rules = market["rules"]
            text = f"{rules.get('rules_primary', '')}\n{rules.get('rules_secondary', '')}"
            named.update(set(BINDING_STATION.findall(text)))
            day = rules.get("settlement_target_date")
            if isinstance(day, str) and compatible_rules(rules, market["ticker"], station, day):
                compatible += 1
        supported = STATIONS.get(station, ("", "", ""))[2] == location["timezone"]
        if not markets:
            status = "no_contracts"
        elif set(named) - {station}:
            status = "mismatch"
        elif not named:
            status = "unnamed"
        elif compatible == len(markets) and supported:
            status = "matched"
        else:
            status = "partial"
        locations.append(
            {
                "series": location["series"],
                "station": station,
                "timezone": location["timezone"],
                "contracts": len(markets),
                "named_stations": dict(sorted(named.items())),
                "label_compatible": compatible,
                "label_source_supported": supported,
                "status": status,
            }
        )
    return {
        "capture_decision_time": decision,
        "capture": root.relative_to(workspace).as_posix(),
        "status": "ok" if all(x["status"] == "matched" for x in locations) else "review",
        "locations": locations,
    }


SOURCE_DATES = 8


def label_sources(api: Api, schedule: dict[str, Any]) -> dict[str, Any]:
    """What the latest retained portal receipt said for each unverified date.

    A refusal such as "preliminary, missing or nonofficial" covers several distinct source
    states; this reads them from the immutable batch so the job log can tell them apart.
    Diagnostics only: failures are reported per date, and nothing is retried or repaired.
    """
    from entropytrade.weather.labels import URL, LabelBatch, source_states

    sources: dict[str, Any] = {}
    unverified = [
        w
        for w in schedule.get("work") or []
        if w.get("status") in {"retry", "refused"} and w.get("last_batch")
    ]
    unverified.sort(key=lambda w: str(w.get("day")), reverse=True)
    for work in unverified[:SOURCE_DATES]:
        day = str(work.get("day"))
        stations = tuple(sorted({str(t.get("station")) for t in work.get("targets") or []}))
        try:
            version = str(work["last_batch"]).removeprefix("sha256:")
            batch = LabelBatch.model_validate(api.get("/api/weather/labels/" + version))
            if batch.version != work["last_batch"]:
                raise ValueError("label batch identity mismatch")
            receipt = next((r for r in batch.receipts if r.url == URL + day), None)
            sources[day] = (
                {"batch": work["last_batch"], "receipt": None}
                if receipt is None
                else {"batch": work["last_batch"], **source_states(receipt, stations)}
            )
        except (ApiError, ValueError, KeyError, TypeError) as exc:
            sources[day] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return sources


def label_backlog(
    schedule: dict[str, Any], at: datetime, sources: dict[str, Any] | None = None
) -> dict[str, Any]:
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
        if sources and str(work.get("day")) in sources:
            dates[-1]["source"] = sources[str(work.get("day"))]
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


ALERT_CONTRACTS = 20


def alert_summary(alert: dict[str, Any]) -> dict[str, Any]:
    """Alerts carry lifecycle clocks; derive the state rather than reading absent keys."""
    status = (
        "resolved"
        if alert.get("resolved_at")
        else "acknowledged"
        if alert.get("acknowledged_at")
        else "open"
    )
    summary = {
        "status": status,
        **{
            k: alert.get(k)
            for k in ("id", "kind", "monitor_id", "opened_at", "acknowledged_at", "resolved_at")
        },
    }
    evidence = alert.get("evidence")
    if status != "resolved" and isinstance(evidence, dict):
        # An unresolved incident is only diagnosable from its evidence; bound contract lists.
        contracts = evidence.get("contracts")
        if isinstance(contracts, list) and len(contracts) > ALERT_CONTRACTS:
            evidence = {
                **evidence,
                "contracts": contracts[:ALERT_CONTRACTS],
                "contracts_total": len(contracts),
            }
        summary["evidence"] = evidence
    return summary


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
    cycles_per_day: float = CYCLES_PER_DAY,
    ledger: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    started_at = now()
    actions: list[dict[str, Any]] = []
    errors: list[str] = []
    api = HttpApi(port)
    try:
        start_footprint: dict[str, Any] | None = footprint(workspace)
    except OSError as exc:
        start_footprint = None
        errors.append(f"start footprint {type(exc).__name__}: {exc}")
    try:
        datasets_before: set[str] | None = dataset_ids(workspace)
    except OSError as exc:
        datasets_before = None
        errors.append(f"start dataset inventory {type(exc).__name__}: {exc}")
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
    try:
        summary["workspace"] = footprint(workspace)
    except OSError as exc:
        errors.append(f"footprint {type(exc).__name__}: {exc}")
    if "workspace" in summary:
        cycles = sum(
            sum(m.get("cycles_this_run", {}).values()) for m in summary.get("monitors", [])
        )
        boundaries = frozen_calendar(workspace)
        summary["runway"] = runway(
            start_footprint,
            summary["workspace"],
            cycles,
            at=now(),
            boundaries=boundaries,
            cycles_per_day=cycles_per_day,
        )
        monitors = summary.get("monitors")
        if isinstance(monitors, list) and all(
            isinstance(m.get("cycle_count"), int) for m in monitors
        ):
            total = sum(int(m["cycle_count"]) for m in monitors)
            rows = []
            if start_footprint is not None:
                rows.append(
                    ledger_row(
                        start_footprint,
                        at=started_at,
                        monitor_cycles=max(0, total - cycles),
                        run_id=run_id,
                    )
                )
            finished = now()
            rows.append(
                ledger_row(summary["workspace"], at=finished, monitor_cycles=total, run_id=run_id)
            )
            chained, reset = extend_ledger(ledger or [], rows, at=finished)
            summary["runway_ledger"] = chained
            summary["chain_runway"] = {
                **chain_runway(
                    chained,
                    summary["workspace"],
                    at=finished,
                    boundaries=boundaries,
                    cycles_per_day=cycles_per_day,
                ),
                "ledger_rows": len(chained),
                "ledger_reset": reset,
            }
    try:
        summary["datasets"] = dataset_costs(workspace, datasets_before)
    except OSError as exc:
        errors.append(f"datasets {type(exc).__name__}: {exc}")
    try:
        summary["disk"] = disk_headroom(workspace)
    except OSError as exc:
        errors.append(f"disk {type(exc).__name__}: {exc}")
    try:
        summary["station_bindings"] = station_bindings(workspace)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        summary["station_bindings"] = {
            "status": "unreadable",
            "error": f"{type(exc).__name__}: {exc}",
        }
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
    parser.add_argument(
        "--cycles-per-day",
        type=float,
        default=CYCLES_PER_DAY,
        help="Projection assumption for the storage runway (not a measurement)",
    )
    parser.add_argument(
        "--ledger-in", type=Path, help="Previous run's runway ledger (JSONL), if any"
    )
    parser.add_argument("--ledger-out", type=Path, help="Write this chain's runway ledger here")
    parser.add_argument("--run-id", help="Identifier recorded on this run's ledger rows")
    args = parser.parse_args()
    if not 60 <= args.seconds <= 5 * 3600:
        parser.error("--seconds must be 60-18000")
    if not 0 < args.cycles_per_day <= 1440:
        parser.error("--cycles-per-day must be in (0, 1440]")
    if args.summary.exists():
        parser.error("--summary already exists; use a new path")
    if args.ledger_out is not None and args.ledger_out.exists():
        parser.error("--ledger-out already exists; use a new path")
    previous_ledger, ledger_note = read_ledger(args.ledger_in)
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
        cycles_per_day=args.cycles_per_day,
        ledger=previous_ledger,
        run_id=args.run_id,
    )
    # Without a measurement this run, carry the previous rows forward unchanged.
    chained = result.pop("runway_ledger", None)
    if chained is None:
        chained = previous_ledger
    if ledger_note and isinstance(result.get("chain_runway"), dict):
        result["chain_runway"]["ledger_reset"] = ledger_note
    if args.ledger_out is not None:
        args.ledger_out.parent.mkdir(parents=True, exist_ok=True)
        args.ledger_out.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in chained), encoding="utf-8"
        )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief = {
        k: result.get(k)
        for k in (
            "actions",
            "errors",
            "server_exit_code",
            "readiness",
            "workspace",
            "runway",
            "chain_runway",
            "disk",
            "station_bindings",
        )
    }
    brief["open_alerts"] = [a for a in result.get("alerts", []) if a.get("status") != "resolved"]
    sys.stdout.write(json.dumps(brief) + "\n")
    if result["errors"] or result["server_exit_code"] != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
