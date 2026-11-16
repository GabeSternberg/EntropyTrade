"""Offline, bounded, checksummed workspace snapshot/restore. Never loads executable models."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from entropytrade.api.jobs import identifier, timestamp, validate_request
from entropytrade.api.workspace import workspace_lease, workspace_path
from entropytrade.data.sources import file_hash
from entropytrade.domain.lifecycle import Actor
from entropytrade.domain.strategy import StrategySpec
from entropytrade.features.registry import scientific_hash
from entropytrade.ml.forward import FrozenWeather
from entropytrade.tracking.readiness_store import (
    EMPTY_HASH,
    MAX_CAPITAL_CENTS,
    READINESS_TABLES,
    SYSTEM_ACTOR,
    _capital,
)

# v2 stores each distinct file content once (content-addressed members); every path is still
# restored as its own independent, checksum-verified file. v1 archives remain restorable.
SCHEMA = "entropytrade-workspace-v2"
LEGACY_SCHEMA = "entropytrade-workspace-v1"
MAX_FILES = 100_000
MAX_FILE_BYTES = 256 * 1024 * 1024
# Distinct content bytes an archive may carry (what is compressed, uploaded and decompressed).
MAX_BYTES = 2 * 1024 * 1024 * 1024
# Bytes a restore may write to disk once every path is expanded (v1: equal to MAX_BYTES).
MAX_EXPANDED_BYTES = 4 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
LEGACY_MONITOR_COLUMNS = (
    "id job_id candidate_id family spec spec_hash status interval_seconds next_at "
    "created_at failures model_binding"
)
SOURCE_MONITOR_COLUMNS = "source_kind research_job_id experiment_id deployment_key source_ref"
TABLES = {
    "jobs": "id request status created_at updated_at detail result",
    "events": "sequence job_id at stage detail",
    "monitors": LEGACY_MONITOR_COLUMNS + " " + SOURCE_MONITOR_COLUMNS,
    "shadow_cycles": "id monitor_id sequence status started_at finished_at detail result digest",
    "shadow_events": "sequence monitor_id at action",
    "shadow_contracts": "monitor_id ticker market last_attempt outcome",
    "shadow_accounts": "monitor_id state digest",
    "shadow_alerts": "id monitor_id kind opened_at acknowledged_at resolved_at evidence",
    "shadow_alert_events": "sequence alert_id at action evidence",
}
# Durable top-level directories. ``research`` exists only once a research job was saved.
WORKSPACE_DIRECTORIES = frozenset({"runs", "shadow", "research"})
RUNTIME = {
    ".writer.lock",
    "jobs.sqlite-wal",
    "jobs.sqlite-shm",
    "registry.sqlite-wal",
    "registry.sqlite-shm",
    "matplotlib",
}


def _aware(value: object) -> None:
    if not isinstance(value, str) or datetime.fromisoformat(value).utcoffset() is None:
        raise ValueError("readiness audit requires an explicit timestamp timezone")


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _readiness_guard(
    db: sqlite3.Connection, guard: dict[str, Any], monitor_id: str, epoch: int
) -> None:
    if (
        guard.get("schema") != "readiness-db-guard-v1"
        or guard.get("monitor_id") != monitor_id
        or guard.get("monitor_status") not in {"active", "paused", "cancelled", "suspended"}
        or not _integer(guard.get("control_epoch"))
        or guard["control_epoch"] > epoch
    ):
        raise ValueError("invalid historical readiness guard")
    for field in (
        "spec_hash",
        "binding_hash",
        "source_hash",
        "account_hash",
        "monitor_events_hash",
    ):
        blob_member(guard[field])
    if guard.get("deployment_key") is not None:
        blob_member(guard["deployment_key"])
    head = guard.get("cycle_head")
    if head is not None:
        identifier(head["id"])
        if not db.execute(
            "SELECT 1 FROM shadow_cycles WHERE id=? AND monitor_id=? AND sequence=?",
            (head["id"], monitor_id, head["sequence"]),
        ).fetchone() or head["status"] not in {"running", "completed", "failed", "interrupted"}:
            raise ValueError("readiness guard references an unknown cycle")
        if head["digest"] is not None:
            blob_member(head["digest"])
    alerts = guard["alerts"]
    if not isinstance(alerts, list) or len({a["id"] for a in alerts}) != len(alerts):
        raise ValueError("readiness guard has invalid alert references")
    for alert in alerts:
        if not db.execute(
            "SELECT 1 FROM shadow_alerts WHERE id=? AND monitor_id=?",
            (alert["id"], monitor_id),
        ).fetchone():
            raise ValueError("readiness guard references an unknown alert")
        blob_member(alert["evidence_hash"])
        if alert["acknowledged_at"] is not None:
            _aware(alert["acknowledged_at"])


def _validate_readiness(
    root: Path, db: sqlite3.Connection, monitors: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Verify optional safety/review history without observing HALT or initializing stores."""
    controls = db.execute("SELECT * FROM workspace_controls").fetchall()
    if len(controls) != 1 or controls[0]["singleton"] != 1:
        raise ValueError("workspace readiness control singleton is invalid")
    state = dict(controls[0])
    state["actor"] = json.loads(state["actor"])
    Actor.model_validate(state["actor"])
    _aware(state["updated_at"])
    if state["halted"] not in {0, 1} or not _integer(state["epoch"]):
        raise ValueError("workspace readiness control state is invalid")
    states: dict[int, dict[str, Any]] = {0: {"halted": False, "event_hash": EMPTY_HASH}}
    previous = EMPTY_HASH
    history = db.execute("SELECT * FROM workspace_control_events ORDER BY sequence").fetchall()
    latest: dict[str, Any] | None = None
    for sequence, row in enumerate(history, 1):
        event = dict(row)
        payload = event["payload"] = json.loads(event["payload"])
        _aware(event["at"])
        actor = Actor.model_validate(payload["actor"])
        if (
            event["sequence"] != sequence
            or event["epoch"] != sequence
            or event["previous_hash"] != previous
            or scientific_hash({k: v for k, v in event.items() if k != "digest"}) != event["digest"]
            or event["action"] not in {"halted", "released"}
            or payload["epoch"] != event["epoch"]
            or payload["updated_at"] != event["at"]
            or payload.get("execution_authorized") is not False
            or type(payload["halted"]) is not bool
            or payload["halted"] != (event["action"] == "halted")
            or (event["action"] == "released" and actor.kind.value != "human")
            or (event["action"] == "released" and not states[sequence - 1]["halted"])
        ):
            raise ValueError("workspace readiness control audit is inconsistent")
        previous = event["digest"]
        latest = payload
        states[sequence] = {"halted": payload["halted"], "event_hash": previous}
    if state["epoch"] != len(history) or state["event_hash"] != previous:
        raise ValueError("workspace control differs from its append-only audit")
    if latest is None:
        if state["halted"] or state["actor"] != SYSTEM_ACTOR:
            raise ValueError("unreviewed initial workspace readiness control")
    elif (
        any(state[key] != latest[key] for key in ("epoch", "reason", "updated_at", "actor"))
        or bool(state["halted"]) != latest["halted"]
    ):
        raise ValueError("workspace readiness control payload differs from its audit")

    cycles = {row["id"]: dict(row) for row in db.execute("SELECT * FROM shadow_cycles")}
    cycle_controls: dict[str, dict[str, Any]] = {}
    for row in db.execute("SELECT * FROM shadow_cycle_controls"):
        frozen = json.loads(row["snapshot"])
        epoch = row["epoch"]
        if (
            row["cycle_id"] not in cycles
            or not _integer(epoch)
            or epoch not in states
            or row["mode"] not in {"paper", "reconcile_only"}
            or frozen.get("schema") != "shadow-cycle-control-v1"
            or frozen.get("control_epoch") != epoch
            or frozen.get("cycle_mode") != row["mode"]
            or frozen.get("execution_authorized") is not False
            or frozen.get("halted") is not states[epoch]["halted"]
            or frozen.get("event_hash") != states[epoch]["event_hash"]
            or scientific_hash(frozen) != row["digest"]
            or (row["mode"] == "paper" and frozen["halted"])
        ):
            raise ValueError("frozen paper cycle control proof is invalid")
        cycle_controls[row["cycle_id"]] = frozen
    for cycle in cycles.values():
        result = json.loads(cycle["result"]) if cycle["result"] else None
        if result is None:
            continue
        frozen = cycle_controls.get(cycle["id"])
        if frozen is None:
            supplied = any(
                key in result for key in ("control_snapshot", "control_epoch", "cycle_mode")
            )
            legacy = {
                "schema": "shadow-cycle-control-v1",
                "control_epoch": 0,
                "cycle_mode": "paper",
                "halted": False,
                "event_hash": EMPTY_HASH,
                "execution_authorized": False,
            }
            if supplied and (
                result.get("control_snapshot") != legacy
                or result.get("control_epoch") != 0
                or result.get("cycle_mode") != "paper"
            ):
                raise ValueError("paper result lacks its frozen cycle control")
        else:
            omitted_failure_control = (
                cycle["status"] == "failed"
                and not any(
                    key in result for key in ("control_snapshot", "control_epoch", "cycle_mode")
                )
                and not any(
                    result.get(key)
                    for key in (
                        "paper",
                        "paper_inputs",
                        "contracts",
                        "decisions",
                        "outcomes",
                        "outcome_attempts",
                        "orders",
                        "fills",
                        "settlements",
                    )
                )
            )
            if not omitted_failure_control and (
                result.get("control_snapshot") != frozen
                or result.get("control_epoch") != frozen["control_epoch"]
                or result.get("cycle_mode") != frozen["cycle_mode"]
            ):
                raise ValueError("paper result differs from its frozen cycle control")

    proposals = {r["id"]: dict(r) for r in db.execute("SELECT * FROM readiness_proposals")}
    snapshots: dict[str, dict[str, Any]] = {}
    for proposal_id, row in proposals.items():
        payload = row["proposal"] = json.loads(row["proposal"])
        guard = row["guard"] = json.loads(row["guard"])
        blob_member(proposal_id)
        blob_member(row["source_fingerprint"])
        _aware(row["created_at"])
        _aware(row["updated_at"])
        _readiness_guard(db, guard, row["monitor_id"], state["epoch"])
        if (
            row["monitor_id"] not in monitors
            or scientific_hash(payload) != proposal_id
            or payload.get("monitor_id") != row["monitor_id"]
            or payload.get("source_fingerprint") != row["source_fingerprint"]
            or payload.get("execution_authorized") is not False
            or payload.get("submission_enabled") is not False
            or "proposal_hash" in payload
            or not _integer(row["revision"])
            or not _integer(row["capital_cents"])
            or row["status"]
            not in {"proposed", "approved", "rejected", "revoked", "invalidated", "superseded"}
            or row["capital_cents"] != (_capital(payload) if row["status"] == "approved" else 0)
            or (
                row["status"] == "approved"
                and (payload.get("eligible") is not True or state["halted"])
            )
        ):
            raise ValueError("immutable readiness proposal/review is invalid")
        _capital(payload)
        if payload.get("schema_version") == "readiness-proposal-v1":
            from entropytrade.research.readiness_evidence import (
                verify_facts,
                verify_frozen_evidence,
            )

            facts = verify_facts(payload["facts"])
            material = payload["material_refs"]
            source_verified = any(
                check.name == "source_integrity" and check.passed for check in facts.checks
            )
            if (
                facts.monitor_id != row["monitor_id"]
                or scientific_hash(material) != row["source_fingerprint"]
                or material.get("monitor_events_hash") != guard["monitor_events_hash"]
                or material.get("control_epoch") != guard["control_epoch"]
                or facts.source_refs.get("spec_hash") != guard["spec_hash"]
                or facts.source_refs.get("deployment_key") != guard["deployment_key"]
                or facts.eligible != all(check.passed for check in facts.checks)
                or (payload.get("eligible") and not facts.eligible)
                or (facts.eligible and not source_verified)
            ):
                raise ValueError("readiness frozen scientific evidence/reference is inconsistent")
            # Refusals retain only the source claims they actually established. Complete
            # claims require the original immutable model/account prefix independently.
            verify_frozen_evidence(root, monitors[row["monitor_id"]], facts)
    historical_allocations: dict[str, int] = {}
    historical_monitors: dict[str, str] = {}
    for sequence, row in enumerate(
        db.execute("SELECT * FROM readiness_events ORDER BY sequence"), 1
    ):
        event = dict(row)
        actor = Actor.model_validate_json(event["actor"])
        event["actor"] = actor.model_dump(mode="json")
        event["payload"] = json.loads(event["payload"])
        _aware(event["at"])
        proposal_id = event["proposal_id"]
        before = snapshots.get(proposal_id)
        expected_status = "proposed" if event["action"] == "published" else event["action"]
        if (
            event["sequence"] != sequence
            or proposal_id not in proposals
            or event["action"]
            not in {"published", "approved", "rejected", "revoked", "invalidated", "superseded"}
            or event["previous_hash"] != (before["digest"] if before else EMPTY_HASH)
            or scientific_hash({k: v for k, v in event.items() if k != "digest"}) != event["digest"]
            or event["payload"]["status"] != expected_status
            or event["payload"]["revision"] != (before["payload"]["revision"] + 1 if before else 0)
            or (before is None and event["action"] != "published")
            or (before is not None and event["action"] == "published")
            or (event["action"] in {"approved", "rejected"} and actor.kind.value != "human")
        ):
            raise ValueError("readiness review audit chain is invalid")
        if before is None and event["at"] != proposals[proposal_id]["created_at"]:
            raise ValueError("readiness proposal creation clock differs from publication")
        allowed = {
            "proposed": {"approved", "rejected", "revoked", "invalidated"},
            "approved": {"revoked", "invalidated", "superseded"},
        }
        if before is not None and event["action"] not in allowed.get(
            before["payload"]["status"], set()
        ):
            raise ValueError("readiness review history contains an invalid transition")
        proposal = proposals[proposal_id]
        observed = event["payload"].get("observed_guard")
        if event["action"] in {"approved", "rejected"}:
            if not isinstance(observed, dict):
                raise ValueError("readiness review lacks its observed database guard")
            _readiness_guard(db, observed, proposal["monitor_id"], state["epoch"])
            if any(
                observed[key] != proposal["guard"][key]
                for key in (
                    "monitor_id",
                    "monitor_status",
                    "spec_hash",
                    "binding_hash",
                    "source_hash",
                    "deployment_key",
                    "monitor_events_hash",
                )
            ):
                raise ValueError("readiness source changed before the recorded review")
        expected_capital = _capital(proposal["proposal"]) if expected_status == "approved" else 0
        if (
            event["payload"]["capital_cents"] != expected_capital
            or event["payload"]["source_fingerprint"] != proposal["source_fingerprint"]
            or event["payload"]["guard"] != proposal["guard"]
        ):
            raise ValueError("historical readiness review differs from its frozen proposal")
        historical_allocations[proposal_id] = expected_capital
        if expected_status == "approved":
            historical_monitors[proposal_id] = proposal["monitor_id"]
        else:
            historical_monitors.pop(proposal_id, None)
        if sum(historical_allocations.values()) > MAX_CAPITAL_CENTS or len(
            set(historical_monitors.values())
        ) != len(historical_monitors):
            raise ValueError("historical readiness capital allocations exceed deterministic limits")
        snapshots[proposal_id] = event
    approved = []
    for proposal_id, row in proposals.items():
        last = snapshots.get(proposal_id)
        current = {
            key: row[key]
            for key in ("status", "revision", "capital_cents", "source_fingerprint", "guard")
        }
        if (
            last is None
            or {key: last["payload"].get(key) for key in current} != current
            or last["at"] != row["updated_at"]
        ):
            raise ValueError("readiness review state differs from its append-only audit")
        if row["status"] == "approved":
            approved.append(row)
    if sum(r["capital_cents"] for r in approved) > MAX_CAPITAL_CENTS or len(
        {r["monitor_id"] for r in approved}
    ) != len(approved):
        raise ValueError("readiness virtual capital allocations exceed deterministic limits")
    for row in db.execute("SELECT * FROM readiness_investigations"):
        from entropytrade.research.investigations import verify_investigation

        if row["monitor_id"] not in monitors:
            raise ValueError("readiness investigation identity/reference is invalid")
        _aware(row["created_at"])
        verify_investigation(root, dict(row))
    return cycle_controls


def validate_registry(root: Path, reviews: list[dict[str, Any]]) -> None:
    path = root / "registry.sqlite"
    if not path.is_file():
        if reviews:
            raise ValueError("research workspace is missing its lineage registry")
        return
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA trusted_schema=OFF")
        tables = {
            "strategy_experiments",
            "agent_hypotheses",
            "agent_research_runs",
            "probability_runs",
            "probability_models",
            "probability_predictions",
            "specs",
            "states",
            "verdicts",
            "backtests",
            "transitions",
        }
        if set(db.execute("SELECT type, name FROM sqlite_master WHERE type != 'index'")) != {
            ("table", t) for t in tables
        } or [r[0] for r in db.execute("PRAGMA integrity_check")] != ["ok"]:
            raise ValueError("corrupt or unsupported lineage registry")
        for review in reviews:
            if (
                review.get("status") != "research_failed"
                and not db.execute(
                    "SELECT 1 FROM strategy_experiments WHERE experiment_id=?",
                    (review["experiment_id"],),
                ).fetchone()
            ) or not db.execute(
                "SELECT 1 FROM agent_research_runs WHERE run_id=?", (review["research_run"],)
            ).fetchone():
                raise ValueError("research result is missing registry lineage")
    finally:
        db.close()


def backup_database(source: Path, target: Path) -> None:
    original = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    copied = sqlite3.connect(target)
    try:
        original.backup(copied)
        copied.execute("PRAGMA journal_mode=DELETE")
    finally:
        copied.close()
        original.close()


def confined(repo: Path, path: Path) -> Path:
    """Reject links, including parent links, before reading any workspace/archive bytes."""
    root = repo.absolute()
    path = path.absolute()
    if not path.is_relative_to(root) or ".." in path.parts:
        raise ValueError("recovery paths must stay within this repository")
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("recovery paths must not contain symlinks")
    return path


def relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(p in {".", ".."} for p in path.parts)
        or str(path) != value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError("unsafe snapshot member path")
    return value


def application(repo: Path) -> dict[str, str]:
    return {name: file_hash(repo / name) for name in ("pyproject.toml", "uv.lock")}


def check_artifacts(root: Path, artifacts: list[dict[str, Any]]) -> None:
    seen = set()
    for item in artifacts:
        name = relative(item["path"])
        if name in seen:
            raise ValueError("duplicate evidence artifact")
        seen.add(name)
        path = root / name
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != item["bytes"]
            or file_hash(path) != item["sha256"]
        ):
            raise ValueError("missing or corrupt evidence artifact: " + name)


def validate_database(root: Path) -> dict[str, int]:
    """Read-only schema, references and content validation; no migration or clock changes."""
    db = sqlite3.connect((root / "jobs.sqlite").as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA trusted_schema=OFF")
        objects = db.execute(
            "SELECT type, name FROM sqlite_master WHERE type != 'index'"
        ).fetchall()
        actual = {(r["type"], r["name"]) for r in objects}
        readiness_objects = {("table", t) for t in READINESS_TABLES}
        present_readiness = actual & readiness_objects
        if present_readiness and present_readiness != readiness_objects:
            raise ValueError("incomplete workspace readiness database schema")
        expected = {("table", t) for t in TABLES} | readiness_objects
        optional = {
            ("table", t) for t in ("shadow_accounts", "shadow_alerts", "shadow_alert_events")
        } | readiness_objects
        if not expected - optional <= actual <= expected or (
            (("table", "shadow_alerts") in actual) != (("table", "shadow_alert_events") in actual)
        ):
            raise ValueError("unsupported or incomplete workspace database schema")
        for table, columns in (TABLES | READINESS_TABLES).items():
            if ("table", table) not in actual:
                continue  # Legacy workspace before paper accounting; never invent past fills.
            actual_columns = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
            permitted = [columns.split()]
            if table == "monitors":
                # Archive validation is read-only. Earlier stores gain the additive
                # source columns only when TrackingStore is opened after restore.
                permitted += [
                    LEGACY_MONITOR_COLUMNS.split(),
                    LEGACY_MONITOR_COLUMNS.split()[:-1],
                    LEGACY_MONITOR_COLUMNS.split()[:-1]
                    + SOURCE_MONITOR_COLUMNS.split()
                    + ["model_binding"],
                ]
            if actual_columns not in permitted:
                raise ValueError("unsupported workspace database columns")
        if [r[0] for r in db.execute("PRAGMA integrity_check")] != ["ok"]:
            raise ValueError("corrupt workspace database")
        jobs = {identifier(r["id"]): dict(r) for r in db.execute("SELECT * FROM jobs")}
        reviews = []
        for job_id, job in jobs.items():
            request = validate_request(json.loads(job["request"]), stored=True)
            if request["mode"] == "weather_history":
                from entropytrade.weather.history import load_snapshot

                load_snapshot(root / "runs/weather-datasets" / request["dataset_id"])
            if job["status"] not in {
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled",
                "interrupted",
            }:
                raise ValueError("invalid restored job state")
            if job["status"] == "completed" and job["result"] is None:
                raise ValueError("completed job has no result")
            if job["result"] is not None:
                result = json.loads(job["result"])
                check_artifacts(root / "runs" / job_id / "workflow", result.get("artifacts", []))
                if result.get("schema") == "workbench-review-v1":
                    reviews.append(result)
                    review = root / "runs" / job_id / "review.json"
                    if not review.is_file() or json.loads(review.read_text()) != result:
                        raise ValueError("missing or inconsistent research review")
        from entropytrade.weather.history import load_snapshot

        for parent in (root / "runs/weather-datasets", root / "runs/weather-datasets/.batches"):
            for directory in parent.glob("[0-9a-f]" * 64):
                load_snapshot(directory)
        from entropytrade.execution.fee_evidence import FeeEvidenceStore

        FeeEvidenceStore(root).snapshot()
        from entropytrade.weather.label_service import LabelService, batches

        # Read-only validation; restoring never resumes source acquisition.
        labels = LabelService(root)
        labels.partitions.validate()
        labels.catalog()
        labels.scheduler.validate()
        batches(root)
        validate_registry(root, reviews)
        monitors = {identifier(r["id"]): dict(r) for r in db.execute("SELECT * FROM monitors")}
        if ("table", "shadow_alerts") in actual:
            from entropytrade.tracking.alerts import validate

            validate(db, set(monitors))
        for monitor in monitors.values():
            if monitor["status"] not in {"active", "paused", "cancelled", "suspended"}:
                raise ValueError("invalid restored monitor reference/state")
            origin = monitor.get("source_kind", "legacy")
            if origin == "legacy":
                if monitor["job_id"] not in jobs or any(
                    monitor.get(field) is not None
                    for field in (
                        "research_job_id",
                        "experiment_id",
                        "deployment_key",
                        "source_ref",
                    )
                ):
                    raise ValueError("invalid restored legacy monitor source reference")
            elif origin == "autonomous_research":
                from entropytrade.research.paper import verify_paper_origin

                # Frozen source verification checks the copied ResearchStore metadata
                # and immutable artifacts. It never polls, retrains or reprices.
                verify_paper_origin(root, monitor)
            else:
                raise ValueError("unsupported restored monitor source kind")
            spec = StrategySpec.model_validate_json(monitor["spec"])
            if spec.spec_hash() != monitor["spec_hash"]:
                raise ValueError("restored strategy hash mismatch")
            if monitor.get("model_binding") is None:
                # The store's legacy migration leaves SQL NULL unbound. Preserve it;
                # scoring still refuses it, and recovery must never freeze a model.
                if origin != "legacy":
                    raise ValueError("research paper monitor has no frozen model binding")
                continue
            binding = json.loads(monitor["model_binding"])
            if not isinstance(binding, dict):
                raise ValueError("invalid restored model binding")
            if scientific_hash(
                {k: v for k, v in binding.items() if k != "binding_hash"}
            ) != binding.get("binding_hash"):
                raise ValueError("restored model binding hash mismatch")
            if binding["status"] == "bound":
                if binding.get("kind") == "research_weather_v1":
                    from entropytrade.research.paper_models import verify_research_binding

                    if origin != "autonomous_research":
                        raise ValueError("research model binding requires an autonomous source")
                    source_ref = json.loads(monitor["source_ref"])
                    data_kind = source_ref["eligibility"]["data_kind"]
                    if data_kind not in {"real", "synthetic"}:
                        raise ValueError("restored research model provenance is unsupported")
                    # Controlled deployments remain explicitly synthetic on restore;
                    # restoring cannot reauthorize them to score authentic data.
                    verify_research_binding(spec, binding, data_kind=data_kind)
                    continue
                model = FrozenWeather.model_validate(binding["snapshot"])
                if (
                    model.data_kind != "real"
                    or spec.model_ref is None
                    or model.model_hash != spec.model_ref.version
                    or model.family != spec.model_ref.family
                ):
                    raise ValueError("restored model reference mismatch")
            elif binding["status"] != "blocked" or binding["snapshot"] is not None:
                raise ValueError("invalid restored model binding")
        try:
            frozen_controls = _validate_readiness(root, db, monitors) if present_readiness else {}
        except (KeyError, TypeError, AttributeError, sqlite3.Error) as exc:
            raise ValueError("invalid workspace readiness evidence structure") from exc
        sequences: dict[str, list[int]] = {m: [] for m in monitors}
        previous_accounts: dict[str, dict[str, Any]] = {}
        for row in db.execute("SELECT * FROM shadow_cycles ORDER BY sequence"):
            monitor_id, cycle_id = row["monitor_id"], identifier(row["id"])
            if monitor_id not in monitors or row["status"] not in {
                "running",
                "completed",
                "failed",
                "interrupted",
            }:
                raise ValueError("invalid restored cycle reference/state")
            if row["status"] == "running" and monitors[monitor_id]["status"] != "active":
                raise ValueError("non-active restored monitor has a running cycle")
            sequences[monitor_id].append(row["sequence"])
            if row["status"] in {"completed", "failed"} and row["result"] is None:
                raise ValueError("finished cycle has no result")
            if row["result"] is not None:
                result = json.loads(row["result"])
                if (
                    scientific_hash(result) != row["digest"]
                    or result["submission_enabled"] is not False
                ):
                    raise ValueError("restored cycle digest/safety mismatch")
                cycle = root / "shadow" / monitor_id / cycle_id
                check_artifacts(cycle, result["artifacts"])
                result_file = cycle / "result.json"
                if row["status"] == "completed" and not result_file.is_file():
                    raise ValueError("completed cycle is missing result bytes")
                if result_file.is_file() and json.loads(result_file.read_text()) != result:
                    raise ValueError("cycle result disagrees with database")
                from entropytrade.tracking.reconciliation import (
                    is_reconciliation,
                    verify_reconciliation,
                )

                if is_reconciliation(result):
                    control = frozen_controls.get(cycle_id)
                    if control is None:
                        raise ValueError("reconciliation cycle lacks its frozen safety control")
                    verify_reconciliation(
                        cycle,
                        result,
                        expected_before=previous_accounts.get(monitor_id),
                        expected_control={
                            "control_snapshot": control,
                            "started_at": row["started_at"],
                        },
                    )
                    contracts = {
                        r["ticker"]: json.loads(r["market"])
                        for r in db.execute(
                            "SELECT ticker,market FROM shadow_contracts WHERE monitor_id=?",
                            (monitor_id,),
                        )
                    }
                    if any(
                        contract["ticker"] not in contracts
                        or contract["market"] != contracts[contract["ticker"]]
                        for contract in result["reconciliation_contracts"]
                    ):
                        raise ValueError("reconciliation changed its frozen tracked contract terms")
                if "paper" in result:
                    previous_accounts[monitor_id] = result["paper"]["state"]
        if any(seq != list(range(1, len(seq) + 1)) for seq in sequences.values()):
            raise ValueError("incomplete cycle sequence")
        from entropytrade.tracking.accounting import account_hash, verify_export

        accounts = {}
        if ("table", "shadow_accounts") in actual:
            for row in db.execute("SELECT * FROM shadow_accounts"):
                state = json.loads(row["state"])
                if row["monitor_id"] not in monitors or account_hash(state) != row["digest"]:
                    raise ValueError("orphaned/corrupt paper account")
                accounts[row["monitor_id"]] = state
        for monitor_id in monitors:
            cycles = [
                {**dict(row), "result": json.loads(row["result"]) if row["result"] else None}
                for row in db.execute(
                    "SELECT * FROM shadow_cycles WHERE monitor_id=?", (monitor_id,)
                )
            ]
            verify_export({"cycles": cycles, "paper_account": accounts.get(monitor_id)})
        for table, field, references in (
            ("events", "job_id", jobs),
            ("shadow_events", "monitor_id", monitors),
            ("shadow_contracts", "monitor_id", monitors),
        ):
            if any(r[0] not in references for r in db.execute(f"SELECT {field} FROM {table}")):  # noqa: S608 - fixed names
                raise ValueError("orphaned workspace evidence")
        return {
            "jobs": len(jobs),
            "monitors": len(monitors),
            "cycles": sum(map(len, sequences.values())),
        }
    finally:
        db.close()


def blob_member(digest: Any) -> str:
    """Archive member holding one distinct content; refuses anything but a sha256 digest."""
    hexdigest = digest.removeprefix("sha256:") if isinstance(digest, str) else ""
    if (
        not isinstance(digest, str)
        or not digest.startswith("sha256:")
        or len(hexdigest) != 64
        or any(c not in "0123456789abcdef" for c in hexdigest)
    ):
        raise ValueError("snapshot file has an invalid content digest")
    return "blobs/" + hexdigest


def inventory(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """All regular files with checksums, bounded by expanded and distinct-content budgets."""
    files: list[dict[str, Any]] = []
    directories: list[str] = []
    total = 0
    distinct: dict[str, int] = {}
    distinct_total = 0
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink() or not (path.is_dir() or stat.S_ISREG(path.stat().st_mode)):
            raise ValueError("workspace contains a link or special file")
        if path.is_dir():
            if len(directories) >= MAX_FILES:
                raise ValueError("workspace exceeds directory budget")
            directories.append(name)
            continue
        size = path.stat().st_size
        total += size
        if len(files) >= MAX_FILES or size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES:
            raise ValueError("workspace exceeds snapshot size budget")
        digest = file_hash(path)
        if digest not in distinct:
            distinct[digest] = size
            distinct_total += size
            if distinct_total > MAX_BYTES:
                raise ValueError("workspace exceeds snapshot size budget")
        files.append({"path": name, "bytes": size, "sha256": digest})
    return files, directories


@contextmanager
def snapshot_lease(repo: Path, workspace: Path, archive: Path) -> Iterator[dict[str, Any]]:
    """Snapshot an existing source and retain its lease through the caller's inspection.

    No application store may be opened before entering this context. Keeping the lease
    here lets offline verification inspect/compare the same source without reacquiring it.
    """
    root = workspace_path(repo, confined(repo, workspace))
    archive = confined(repo, archive)
    if archive.is_relative_to(root) or archive.exists():
        raise ValueError("snapshot requires a new archive outside the workspace")
    if not root.is_dir() or not (root / "jobs.sqlite").is_file():
        raise ValueError("workspace has no database")
    confined(repo, root / "jobs.sqlite")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with workspace_lease(root), TemporaryDirectory(prefix=".snapshot-", dir=archive.parent) as name:
        stage = Path(name)
        payload = stage / "payload"
        payload.mkdir()
        # Maintenance holds the same lease as the server. Capture WAL consistently and
        # copy all authoritative data, including opaque model bytes, without loading them.
        for child in root.iterdir():
            if child.is_symlink():
                raise ValueError("workspace contains a symlink")
            if child.name in RUNTIME or child.name in {"jobs.sqlite", "registry.sqlite"}:
                continue
            if child.name == "HALT" and child.is_file():
                shutil.copyfile(child, payload / "HALT")
                continue
            if child.name not in WORKSPACE_DIRECTORIES or not child.is_dir():
                raise ValueError("unexpected workspace entry: " + child.name)
            inventory(child)  # reject nested links/special files before copying
            shutil.copytree(
                child,
                payload / child.name,
                ignore=shutil.ignore_patterns("research.sqlite", "research.sqlite-*"),
            )
            if child.name == "research" and (child / "research.sqlite").is_file():
                # Research jobs use WAL; copy a consistent database like jobs.sqlite.
                backup_database(child / "research.sqlite", payload / "research/research.sqlite")
        backup_database(root / "jobs.sqlite", payload / "jobs.sqlite")
        if (root / "registry.sqlite").is_file():
            backup_database(root / "registry.sqlite", payload / "registry.sqlite")
        counts = validate_database(payload)
        files, directories = inventory(payload)
        manifest = {
            "schema": SCHEMA,
            "created_at": timestamp(),
            "application": application(repo),
            "files": files,
            "directories": directories,
            "counts": counts,
            "submission_enabled": False,
        }
        temporary = stage / "workspace.zip"
        encoded_manifest = json.dumps(manifest, sort_keys=True)
        if len(encoded_manifest.encode()) > MAX_MANIFEST_BYTES:
            raise ValueError("workspace exceeds snapshot manifest budget")
        # Deflate: retained JSON evidence compresses ~10x, which keeps chained uploads and
        # restores fast. Immutable datasets copy shadow receipts byte for byte, so each
        # distinct content is stored once. Restore bounds every member by its declared size
        # and checksum and writes every path as its own file.
        blobs: dict[str, str] = {}
        for item in files:
            blobs.setdefault(item["sha256"], item["path"])
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as bundle:
            bundle.writestr("manifest.json", encoded_manifest)
            for digest, path in sorted(blobs.items()):
                bundle.write(payload / path, blob_member(digest))
        temporary.chmod(0o600)
        os.link(temporary, archive)  # publish without replacing any existing evidence
        yield {
            "archive": str(archive),
            "sha256": file_hash(archive),
            **counts,
            "submission_enabled": False,
        }


def snapshot(repo: Path, workspace: Path, archive: Path) -> dict[str, Any]:
    with snapshot_lease(repo, workspace, archive) as receipt:
        return receipt


def unpack(repo: Path, archive: Path, stage: Path) -> dict[str, Any]:
    with ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or len(names) > MAX_FILES + 1:
            raise ValueError("duplicate/excessive snapshot members")
        for member in members:
            relative(member.filename)
            mode = member.external_attr >> 16
            if (
                member.is_dir()
                or stat.S_IFMT(mode) not in {0, stat.S_IFREG}
                or member.flag_bits & 1
                or member.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
            ):
                raise ValueError("snapshot members must be unencrypted regular files")
        if (
            "manifest.json" not in names
            or bundle.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES
        ):
            raise ValueError("missing/oversized snapshot manifest")
        manifest = json.loads(bundle.read("manifest.json"))
        legacy = manifest["schema"] == LEGACY_SCHEMA
        if (
            manifest["schema"] not in {SCHEMA, LEGACY_SCHEMA}
            or manifest["application"] != application(repo)
            or manifest["submission_enabled"] is not False
        ):
            raise ValueError("unsupported snapshot schema/application/safety")
        files = manifest["files"]
        for item in files:
            parts = PurePosixPath(relative(item["path"])).parts
            if parts not in {("jobs.sqlite",), ("registry.sqlite",), ("HALT",)} and (
                len(parts) < 2 or parts[0] not in WORKSPACE_DIRECTORIES
            ):
                raise ValueError("unexpected snapshot workspace entry")

        def member_name(item: dict[str, Any]) -> str:
            return "files/" + item["path"] if legacy else blob_member(item["sha256"])

        paths = {relative(f["path"]) for f in files}
        expected = {member_name(f) for f in files}
        if (
            len(files) > MAX_FILES
            or len(paths) != len(files)
            or set(names) != expected | {"manifest.json"}
        ):
            raise ValueError("incomplete snapshot member inventory")
        total = 0
        distinct = 0
        seen: set[str] = set()
        for item in files:
            info: ZipInfo = bundle.getinfo(member_name(item))
            size = item["bytes"]
            total += info.file_size
            if info.filename not in seen:
                seen.add(info.filename)
                distinct += info.file_size
            if (
                type(size) is not int
                or size < 0
                or size != info.file_size
                or size > MAX_FILE_BYTES
                or distinct > MAX_BYTES
                or total > (MAX_BYTES if legacy else MAX_EXPANDED_BYTES)
            ):
                raise ValueError("snapshot exceeds size budget or has invalid sizes")
        directories = manifest["directories"]
        if not isinstance(directories, list) or len(directories) > MAX_FILES:
            raise ValueError("snapshot exceeds directory budget")
        for directory in directories:
            if PurePosixPath(relative(directory)).parts[0] not in WORKSPACE_DIRECTORIES:
                raise ValueError("unexpected snapshot directory")
            (stage / relative(directory)).mkdir(parents=True, exist_ok=True)
        for item in files:
            path = stage / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with bundle.open(member_name(item)) as source, path.open("xb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(chunk)
                    digest.update(chunk)
            path.chmod(0o600)
            if "sha256:" + digest.hexdigest() != item["sha256"]:
                raise ValueError("snapshot checksum mismatch: " + item["path"])
        counts = validate_database(stage)
        if counts != manifest["counts"]:
            raise ValueError("snapshot database counts mismatch")
        return counts


def restore(repo: Path, archive: Path, workspace: Path) -> dict[str, Any]:
    archive = confined(repo, archive)
    destination = workspace_path(repo, confined(repo, workspace))
    if destination.exists():
        raise ValueError("restore requires a new workspace; existing data is never overwritten")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".restore-", dir=destination.parent) as name:
        stage = Path(name) / "workspace"
        stage.mkdir(mode=0o700)
        try:
            counts = unpack(repo, archive, stage)
        except (BadZipFile, sqlite3.Error, KeyError, TypeError, UnicodeError, OSError) as exc:
            raise ValueError("invalid or incomplete snapshot: " + type(exc).__name__) from exc
        # No database recovery occurs until normal server startup; paused states and
        # every original timestamp remain untouched. Never fit/promote on restore.
        if destination.exists():
            raise ValueError("restore destination appeared during verification")
        stage.rename(destination)
    return {
        "workspace": str(destination),
        "archive_sha256": file_hash(archive),
        **counts,
        "submission_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["snapshot", "restore"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    try:
        result = (snapshot if args.action == "snapshot" else restore)(
            repo, workspace=args.workspace, archive=args.archive
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Recovery refused: {exc}\n")
    print(json.dumps(result, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
