"""Inventory existing evidence and assess requirements against it. Strictly read-only.

Inventory runs before any acquisition so identical data is never fetched again. A dataset
that merely contains historical values does not satisfy a requirement: its clocks,
fidelity, data kind and window must also match.
"""

import json
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade.data.sources import file_hash
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.features.registry import scientific_hash
from entropytrade.research.model import (
    Assessment,
    AssessmentStatus,
    DataKind,
    DataRequirement,
    DatasetRecord,
)

Coverage = dict[str, set[str]]
Clock = Literal["issuance", "receipt", "unknown"]
Fidelity = Literal["any", "candle", "quote", "order_book"]
COLLECTOR_STATUS_SCHEMA = "entropytrade-collector-status-v1"
_PROBLEMS = (ValueError, OSError, KeyError, TypeError, sqlite3.Error)


def _safe(path: Path, root: Path) -> Path:
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError("inventory paths cannot traverse symlinks")
    return path


def _records(
    *,
    dataset_id: str,
    origin: str,
    data_kind: str,
    family: str,
    slices: dict[tuple[DataKind, str, str, Clock, Fidelity], Coverage],
    created_at: datetime | None = None,
    content_hash: str = "",
    path: str = "",
    verified: bool = False,
    detail: str = "",
) -> list[DatasetRecord]:
    result = []
    for (kind, variable, source, clock, fidelity), coverage in sorted(
        slices.items(), key=lambda item: tuple(str(v) for v in item[0])
    ):
        result.append(
            DatasetRecord.model_validate(
                {
                    "record_id": f"{dataset_id}#{kind.value}:{variable}:{source}",
                    "dataset_id": dataset_id,
                    "origin": origin,
                    "data_kind": data_kind,
                    "kind": kind,
                    "variable": variable,
                    "family": family,
                    "source_id": source,
                    "clock": clock,
                    "fidelity": fidelity,
                    "coverage": {e: tuple(sorted(d)) for e, d in sorted(coverage.items())},
                    "created_at": created_at,
                    "content_hash": content_hash,
                    "path": path,
                    "verified": verified,
                    "detail": detail,
                }
            )
        )
    return result


def feature_directory(
    directory: Path,
    *,
    dataset_id: str,
    origin: str,
    workspace_root: Path,
    holdout_start: date | None = None,
) -> list[DatasetRecord]:
    """Count coverage in an existing weather feature matrix. No values are exposed."""
    manifest = json.loads(_safe(directory / "manifest.json", workspace_root).read_text())
    protected = set(manifest.get("protected_events", []))
    table = pq.read_table(
        _safe(directory / "features.parquet", workspace_root),
        columns=[
            "event_id",
            "market_ticker",
            "target_date",
            "station",
            "feature_values_json",
            "feature_evidence_json",
            "temperature_target_f",
            "execution_fidelity",
        ],
    )
    slices: dict[tuple[DataKind, str, str, Clock, Fidelity], Coverage] = defaultdict(
        lambda: defaultdict(set)
    )
    for row in table.to_pylist():
        day = str(row["target_date"])
        if row["event_id"] in protected or (holdout_start and day >= holdout_start.isoformat()):
            continue
        series = str(row["event_id"]).split("-", 1)[0]
        station = str(row["station"])
        values = json.loads(row["feature_values_json"])
        providers = {
            str(item["provider"])
            for item in json.loads(row["feature_evidence_json"]).get("forecast_evidence", [])
        }
        for provider in providers:
            slices[
                (DataKind.FORECAST_VINTAGES, "hourly_temperature_f", provider, "receipt", "any")
            ][station].add(day)
        if values.get("revision_f") is not None:
            slices[(DataKind.FORECAST_REVISIONS, "hourly_temperature_f", "", "receipt", "any")][
                station
            ].add(day)
        if row["temperature_target_f"] is not None:
            slices[(DataKind.SETTLEMENT_LABELS, "daily_high_f", "", "receipt", "any")][station].add(
                day
            )
        slices[(DataKind.MARKET_CONTRACTS, "contract_terms", "kalshi", "receipt", "any")][
            series
        ].add(day)
        fidelity = row["execution_fidelity"]
        if fidelity in {"order_book", "quote"}:
            slices[(DataKind.DECISION_QUOTES, "yes_quotes", "kalshi", "receipt", fidelity)][
                series
            ].add(day)
    kind = {"real": "authentic", "synthetic": "synthetic"}.get(manifest.get("data_kind"))
    if kind is None:
        raise ValueError("feature matrix has an unknown data kind")
    return _records(
        dataset_id=dataset_id,
        origin=origin,
        data_kind=kind,
        family="weather",
        slices=slices,
        content_hash=str(manifest.get("feature_version", "")),
        path=directory.relative_to(workspace_root).as_posix()
        if directory.is_relative_to(workspace_root)
        else directory.as_posix(),
        detail="Existing weather feature matrix; coverage counted, values withheld.",
    )


def _configured(repo: Path) -> list[DatasetRecord]:
    path = repo / "configs/research/weather.json"
    if not path.is_file():
        return []
    config = json.loads(path.read_text())
    root = (repo / config["root"]).resolve()
    directory = (root / config["features"]).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("configured evidence escaped its root")
    if not directory.is_dir():
        return []
    return feature_directory(
        directory,
        dataset_id="configured:" + Path(config["features"]).name[:16],
        origin="configured_evidence",
        workspace_root=repo,
        holdout_start=date.fromisoformat(config["holdout_start"]),
    )


def _snapshots(workspace: Path) -> list[DatasetRecord]:
    root = workspace / "runs/weather-datasets"
    result: list[DatasetRecord] = []
    for path in sorted(root.glob("[0-9a-f]" * 64)) if root.is_dir() else []:
        manifest = json.loads(_safe(path / "snapshot.json", workspace).read_text())
        if scientific_hash(manifest["identity"]) != manifest["dataset_id"]:
            raise ValueError("weather snapshot identity mismatch")
        records = feature_directory(
            path / manifest["features"],
            dataset_id=manifest["dataset_id"],
            origin="weather_snapshot",
            workspace_root=workspace,
        )
        result.extend(
            r.revalidated(detail="Retained weather snapshot; identity checked, files at use.")
            for r in records
        )
    return result


def _labels(workspace: Path) -> list[DatasetRecord]:
    from entropytrade.weather.labels import load_batch

    root = workspace / "runs/weather-labels"
    coverage: Coverage = defaultdict(set)
    versions = []
    for path in sorted(root.rglob("batches/*.json")) if root.is_dir() else []:
        batch = load_batch(_safe(path, workspace))
        versions.append(batch.version)
        for record in batch.records():
            observation = record["observation"]
            if observation is not None:
                coverage[str(observation["entity_id"])].add(str(observation["valid_on"]))
    if not versions:
        return []
    return _records(
        dataset_id="labels:" + scientific_hash(sorted(versions)).removeprefix("sha256:")[:16],
        origin="label_batch",
        data_kind="authentic",
        family="weather",
        slices={
            (DataKind.SETTLEMENT_LABELS, "daily_high_f", "weather-company", "receipt", "any"): (
                coverage
            )
        },
        content_hash=scientific_hash(sorted(versions)),
        verified=True,
        detail=f"{len(versions)} retained Weather Company label batches (receipt clocks).",
    )


def _shadow(workspace: Path) -> list[DatasetRecord]:
    path = workspace / "jobs.sqlite"
    if not path.is_file():
        return []
    db = sqlite3.connect(f"file:{_safe(path, workspace).resolve()}?mode=ro", uri=True, timeout=2)
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_contracts'").fetchone():
            return []
        tickers = [
            str(row[0])
            for row in db.execute(
                "SELECT DISTINCT c.ticker FROM shadow_contracts c WHERE EXISTS ("
                "SELECT 1 FROM shadow_cycles s WHERE s.monitor_id=c.monitor_id "
                "AND s.status='completed')"
            )
        ]
    finally:
        db.close()
    coverage: Coverage = defaultdict(set)
    for ticker in tickers:
        day = ticker_target_date(ticker)
        if day is not None:
            coverage[ticker.split("-", 1)[0]].add(day.isoformat())
    if not coverage:
        return []
    return _records(
        dataset_id="shadow-monitors",
        origin="shadow_monitor",
        data_kind="authentic",
        family="weather",
        slices={(DataKind.DECISION_QUOTES, "yes_quotes", "kalshi", "receipt", "quote"): coverage},
        detail="Contracts polled by website shadow monitors with completed cycles. Counts "
        "monitored events; decision-schedule alignment is checked at feature build.",
    )


def _fees(workspace: Path) -> list[DatasetRecord]:
    from entropytrade.execution.fee_evidence import FeeEvidenceStore

    store = FeeEvidenceStore(workspace)
    if not store.root.is_dir():
        return []
    certified: Coverage = defaultdict(set)
    captured: Coverage = defaultdict(set)
    for version in store.snapshot():
        if version.evidence_kind != "authentic":
            continue
        for series in version.series:
            (certified if version.policy is not None else captured)[series].add("*")
    slices: dict[tuple[DataKind, str, str, Clock, Fidelity], Coverage] = {}
    if certified:
        slices[(DataKind.FEE_SCHEDULE, "fee_schedule", "kalshi", "receipt", "any")] = certified
    result = _records(
        dataset_id="fee-evidence",
        origin="fee_evidence",
        data_kind="authentic",
        family="market",
        slices=slices,
        verified=True,
        detail="Certified authentic fee policies.",
    )
    if captured:
        result += _records(
            dataset_id="fee-evidence-uncertified",
            origin="fee_evidence",
            data_kind="authentic",
            family="market",
            slices={
                (
                    DataKind.FEE_SCHEDULE,
                    "uncertified_fee_schedule",
                    "kalshi",
                    "receipt",
                    "any",
                ): captured
            },
            verified=True,
            detail="Fee schedule receipts captured but not certified; certification is a human "
            "review action.",
        )
    return result


def _collector(workspace: Path) -> list[DatasetRecord]:
    root = workspace / "research/collector-status"
    result: list[DatasetRecord] = []
    for path in sorted(root.glob("*.json")) if root.is_dir() else []:
        if _safe(path, workspace).stat().st_size > 4_000_000:
            raise ValueError("collector status exceeds size budget")
        value: dict[str, Any] = json.loads(path.read_text())
        if value.get("schema") != COLLECTOR_STATUS_SCHEMA:
            raise ValueError("unknown collector status schema")
        if (
            scientific_hash({"slices": value["slices"], "problems": value["problems"]})
            != value["chain_head"]
        ):
            raise ValueError("collector status checksum mismatch")
        generated = datetime.fromisoformat(value["generated_at"])
        if generated.tzinfo is None or generated.utcoffset() is None:
            raise ValueError("collector status timestamp must have a timezone")
        generated = generated.astimezone(UTC)
        for item in value["slices"]:
            coverage = {str(k): set(map(str, v)) for k, v in item["coverage"].items()}
            result += _records(
                dataset_id="collector:" + str(value["chain_head"])[:24],
                origin="collector_status",
                data_kind="authentic",
                family=str(item.get("family", "weather")),
                slices={
                    (
                        DataKind(item["kind"]),
                        str(item["variable"]),
                        str(item.get("source_id", "")),
                        item.get("clock", "receipt"),
                        item.get("fidelity", "any"),
                    ): coverage
                },
                created_at=generated,
                content_hash=file_hash(path),
                path=path.relative_to(workspace).as_posix(),
                detail="Sanitized canonical-collector status. Raw evidence stays on the "
                "collector host until a verified snapshot is imported.",
            )
    return result


def _acquired(workspace: Path) -> list[DatasetRecord]:
    root = workspace / "research/datasets"
    result: list[DatasetRecord] = []
    for path in sorted(root.glob("sha256-*")) if root.is_dir() else []:
        manifest = json.loads(_safe(path / "manifest.json", workspace).read_text())
        checksums: dict[str, str] = manifest["checksums"]
        if scientific_hash(checksums) != manifest["content_hash"]:
            raise ValueError("research dataset checksum manifest mismatch")
        if "sha256-" + manifest["content_hash"].removeprefix("sha256:") != path.name:
            raise ValueError("research dataset path/identity mismatch")
        for name, digest in checksums.items():
            if file_hash(_safe(path / name, workspace)) != digest:
                raise ValueError("research dataset file checksum mismatch")
        result.extend(DatasetRecord.model_validate(r) for r in manifest["records"])
    return result


LOADERS: tuple[tuple[str, Callable[[Path, Path], list[DatasetRecord]]], ...] = (
    ("research_acquisition", lambda workspace, _: _acquired(workspace)),
    ("configured_evidence", lambda _, repo: _configured(repo)),
    ("weather_snapshot", lambda workspace, _: _snapshots(workspace)),
    ("label_batch", lambda workspace, _: _labels(workspace)),
    ("shadow_monitor", lambda workspace, _: _shadow(workspace)),
    ("fee_evidence", lambda workspace, _: _fees(workspace)),
    ("collector_status", lambda workspace, _: _collector(workspace)),
)


def inventory(workspace: Path, repo: Path) -> tuple[list[DatasetRecord], list[dict[str, str]]]:
    """All evidence slices plus loaders that failed verification (never silently used)."""
    records: list[DatasetRecord] = []
    problems: list[dict[str, str]] = []
    for origin, loader in LOADERS:
        try:
            records.extend(loader(workspace, repo))
        except _PROBLEMS as exc:
            problems.append({"origin": origin, "error": type(exc).__name__})
    return records, problems


def summary(records: Iterable[DatasetRecord]) -> list[dict[str, Any]]:
    return [
        {
            **r.model_dump(mode="json", exclude={"coverage"}),
            "entities": {e: len(d) for e, d in r.coverage.items()},
            "first_date": min(
                (d for v in r.coverage.values() for d in v if d != "*"), default=None
            ),
            "last_date": max((d for v in r.coverage.values() for d in v if d != "*"), default=None),
        }
        for r in records
    ]


_CLOCKS = {"issuance": {"issuance"}, "receipt": {"issuance", "receipt"}, "any": None}
_FIDELITY = {"order_book": {"order_book"}, "quote": {"quote", "order_book"}, "any": None}


def _matches(requirement: DataRequirement, record: DatasetRecord) -> bool:
    return (
        record.kind is requirement.kind
        and record.variable == requirement.variable
        and requirement.entity in record.coverage
    )


def assess(
    requirement: DataRequirement,
    records: Iterable[DatasetRecord],
    now: datetime,
    *,
    expected_data_kind: Literal["authentic", "synthetic"] = "authentic",
) -> Assessment:
    """Deterministic sufficiency: kind, variable, entity, clock, fidelity, provenance, window."""
    if expected_data_kind not in {"authentic", "synthetic"}:
        raise ValueError("unsupported assessment evidence kind")
    clocks = _CLOCKS[requirement.clock]
    fidelity = _FIDELITY[requirement.fidelity]
    reasons: list[str] = []
    sources: dict[str, set[str]] = defaultdict(set)
    datasets: list[str] = []
    for record in records:
        if record.kind is DataKind.FEE_SCHEDULE and record.variable == "uncertified_fee_schedule":
            if requirement.kind is DataKind.FEE_SCHEDULE and requirement.entity in record.coverage:
                reasons.append(record.detail)
            continue
        if not _matches(requirement, record):
            continue
        label = record.source_id or record.origin
        dates = set(record.coverage[requirement.entity])
        if record.data_kind != expected_data_kind:
            reasons.append(
                f"{record.data_kind} dataset {record.dataset_id} cannot support "
                + (
                    "real research"
                    if expected_data_kind == "authentic"
                    else "synthetic verification"
                )
            )
            continue
        if record.origin == "collector_status":
            reasons.append(
                f"canonical collector reports {len(dates)} dates for {requirement.entity}; raw "
                "evidence is on the collector host until a verified snapshot is imported"
            )
            continue
        if clocks is not None and record.clock not in clocks:
            reasons.append(
                f"{label} has {requirement.kind.value} for {requirement.entity} but only "
                f"{record.clock} clocks; {requirement.clock} clocks are required"
            )
            continue
        if fidelity is not None and record.fidelity not in fidelity:
            reasons.append(
                f"{label} has {record.fidelity}-fidelity data; {requirement.fidelity} is required"
            )
            continue
        inside = {
            d
            for d in dates
            if d == "*" or requirement.start.isoformat() <= d <= requirement.end.isoformat()
        }
        if len(inside) < len(dates):
            reasons.append(f"{len(dates) - len(inside)} {label} dates fall outside the window")
        if inside:
            datasets.append(record.dataset_id)
            sources[label] |= inside
    per_date = Counter(d for covered in sources.values() for d in covered)
    events = sum(1 for count in per_date.values() if count >= requirement.min_sources)
    if requirement.min_sources > 1 and per_date and events == 0:
        reasons.append(
            f"{len(sources)} source(s) found; {requirement.min_sources} distinct sources are "
            "required for the same date"
        )
    status = (
        AssessmentStatus.SATISFIED
        if events >= requirement.min_events
        else AssessmentStatus.PARTIAL
        if events
        else AssessmentStatus.MISSING
    )
    unit = "item" if requirement.kind is DataKind.FEE_SCHEDULE else "independent dates"
    reasons.insert(0, f"{events} of {requirement.min_events} {unit} available")
    return Assessment(
        requirement_id=requirement.requirement_id,
        status=status,
        events_available=events,
        events_required=requirement.min_events,
        datasets=tuple(dict.fromkeys(datasets)),
        reasons=tuple(dict.fromkeys(reasons)),
        assessed_at=now,
    )
