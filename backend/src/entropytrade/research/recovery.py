"""Bounded, read-only validation of frozen research evidence for recovery.

Values, labels, models and replay files are opaque bytes here. This module deliberately
never invokes a research service, current-code planner, materializer or model loader.
"""

import json
import math
import re
import sqlite3
import stat
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from entropytrade.data.sources import file_hash
from entropytrade.execution.fee_evidence import FeeVersion
from entropytrade.features.registry import scientific_hash
from entropytrade.research.model import (
    RESEARCH_SETTABLE,
    Assessment,
    DataRequirement,
    DatasetRecord,
    DecisionPoint,
    HypothesisSpec,
    HypothesisStatus,
    JobStatus,
    ResearchRequest,
    requirement_id,
)
from entropytrade.research.registry import Resolution
from entropytrade.research.sources import SourceDecision

HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
DIRECTORY = re.compile(r"sha256-([0-9a-f]{64})\Z")
MAX_FILES = 100_000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024**3
MAX_CONTENT_BYTES = 2 * 1024**3
MAX_JSON_BYTES = 16 * 1024**2
MAX_ROWS = 100_000
TABLES = {
    "research_jobs": "id request fingerprint family universe status detail created_at updated_at "
    "next_run_at attempts checkpoint usage error",
    "research_events": "sequence job_id at stage detail",
    "research_hypotheses": "job_id hypothesis_id version rank spec status reasons facets "
    "search_note updated_at",
    "research_signatures": "signature first_job_id hypothesis_id first_seen searches",
    "research_requirements": "job_id requirement_id spec assessment",
    "research_resolutions": "job_id hypothesis_id requested resolution",
    "research_sources": "job_id requirement_id source_id decision",
    "research_acquisitions": "id acquisition_key source_id params status attempts requests bytes "
    "dataset_id detail error created_at updated_at next_attempt_at",
    "research_acquisition_links": "job_id acquisition_id requirement_id approval",
    "research_forward": "id coverage_key spec source_id collector collector_status events_required "
    "events_observed status detail created_at updated_at next_check_at estimated_ready_at",
    "research_forward_links": "job_id forward_id requirement_id",
    "research_features": (
        "artifact_id feature_id version definition_hash entity manifest created_at"
    ),
    "research_feature_links": "job_id artifact_id hypothesis_ids",
    "research_experiments": "job_id id hypothesis_id status config result error attempts "
    "created_at updated_at",
    "research_validation_boundaries": "scope boundaries created_at",
}
INTEGER_COLUMNS = {
    "sequence",
    "version",
    "rank",
    "searches",
    "attempts",
    "requests",
    "bytes",
    "events_required",
    "events_observed",
}


def _require(condition: bool, message: str) -> None:  # noqa: FBT001 - validation predicate
    if not condition:
        raise ValueError("research recovery: " + message)


def _hash(value: Any) -> str:
    _require(isinstance(value, str) and HASH.fullmatch(value) is not None, "invalid content hash")
    return str(value)


def _uuid(value: str) -> str:
    _require(str(UUID(value)) == value, "invalid job/acquisition ID")
    return value


def _clock(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "naive timestamp")


def _integer(value: Any, *, minimum: int = 0, maximum: int = 2**63 - 1) -> None:
    _require(type(value) is int and minimum <= value <= maximum, "invalid bounded integer")


def _json(value: str) -> Any:
    _require(len(value.encode()) <= MAX_JSON_BYTES, "JSON exceeds metadata budget")
    return json.loads(
        value, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON"))
    )


def _object(path: Path) -> dict[str, Any]:
    _require(path.stat().st_size <= MAX_JSON_BYTES, "JSON exceeds metadata budget")
    result = _json(path.read_text())
    _require(isinstance(result, dict), "metadata must be an object")
    return dict(result)


def _inventory(root: Path) -> dict[Path, str]:
    """Check the complete tree before parsing anything; unfinished bytes stay opaque."""
    _require(not any(p.is_symlink() for p in (root, *root.parents)), "symlink path")
    hashes: dict[Path, str] = {}
    content: dict[str, int] = {}
    total = count = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            count += 1
            _require(count <= MAX_FILES, "file inventory budget exceeded")
            mode = child.lstat().st_mode
            if stat.S_ISDIR(mode):
                pending.append(child)
            else:
                _require(stat.S_ISREG(mode), "symlink or special evidence file")
                size = child.stat().st_size
                total += size
                _require(
                    size <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES, "file byte budget exceeded"
                )
                digest = file_hash(child)
                hashes[child] = digest
                content[digest] = size
    _require(sum(content.values()) <= MAX_CONTENT_BYTES, "distinct content budget exceeded")
    return hashes


def _committed(root: Path, section: str) -> dict[str, Path]:
    directory = root / section
    if not directory.exists():
        return {}
    _require(directory.is_dir(), "artifact section is not a directory")
    result = {}
    for child in directory.iterdir():
        if child.name.startswith(".building-"):
            continue  # Interrupted work is retained, never represented as a completed artifact.
        match = DIRECTORY.fullmatch(child.name)
        _require(match is not None and child.is_dir(), "unexpected committed artifact entry")
        if match is None:
            raise ValueError("invalid committed research directory")
        result["sha256:" + match[1]] = child
    return result


def _datasets(root: Path, hashes: dict[Path, str]) -> dict[str, dict[str, Any]]:
    result = {}
    # Verify even raw responses no longer linked by any dataset.
    raw_root = root / "raw"
    if raw_root.exists():
        _require(raw_root.is_dir(), "raw evidence is not a directory")
        for prefix in raw_root.iterdir():
            _require(
                prefix.is_dir() and re.fullmatch(r"[0-9a-f]{2}", prefix.name) is not None,
                "invalid raw evidence prefix",
            )
            for raw in prefix.iterdir():
                if ".tmp-" in raw.name:
                    continue  # Interrupted raw publication, retained as opaque uncommitted bytes.
                _require(
                    raw.is_file()
                    and re.fullmatch(r"[0-9a-f]{64}", raw.name) is not None
                    and raw.name.startswith(prefix.name),
                    "invalid raw evidence identity",
                )
                _require(hashes[raw] == "sha256:" + raw.name, "raw response checksum mismatch")
    for identifier, path in _committed(root, "datasets").items():
        manifest = _object(path / "manifest.json")
        _require(
            manifest.get("schema") == "entropytrade-research-dataset-v1",
            "unsupported dataset schema",
        )
        _require(manifest.get("data_kind") in {"authentic", "synthetic"}, "invalid dataset kind")
        checksums = manifest["checksums"]
        names = {"records.jsonl", "receipts.jsonl", "parameters.json"}
        _require(
            set(checksums) == names
            and {p.name for p in path.iterdir()} == names | {"manifest.json"},
            "dataset inventory mismatch",
        )
        _require(
            manifest["dataset_id"] == identifier
            and scientific_hash(checksums) == identifier
            and manifest.get("content_hash", identifier) == identifier,
            "dataset identity mismatch",
        )
        for name, digest in checksums.items():
            _require(hashes.get(path / name) == _hash(digest), "dataset checksum mismatch")
        receipt_hashes = set()
        with (path / "receipts.jsonl").open() as receipts:
            for count, line in enumerate(receipts, 1):
                _require(
                    count <= MAX_ROWS and len(line) <= MAX_JSON_BYTES, "receipt budget exceeded"
                )
                if not line.strip():
                    continue
                receipt = _json(line)
                digest = _hash(receipt["sha256"])
                receipt_hashes.add(digest)
                raw = root / "raw" / digest[7:9] / digest[7:]
                _require(hashes.get(raw) == digest, "raw receipt reference mismatch")
                if "received_at" in receipt:
                    _clock(receipt["received_at"])
                if "bytes" in receipt:
                    _integer(receipt["bytes"], maximum=MAX_FILE_BYTES)
                    _require(raw.stat().st_size == receipt["bytes"], "raw receipt size mismatch")
        _require(sorted(receipt_hashes) == manifest["raw_hashes"], "raw receipt inventory mismatch")
        if "created_at" in manifest:
            _clock(manifest["created_at"])
        for record in manifest.get("records", []):
            typed = DatasetRecord.model_validate(record)
            _require(
                typed.dataset_id == identifier
                and typed.content_hash == identifier
                and typed.data_kind == manifest["data_kind"],
                "dataset metadata reference mismatch",
            )
        result[identifier] = manifest
    return result


def _features(
    root: Path, hashes: dict[Path, str], datasets: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    result = {}
    for identifier, path in _committed(root, "features").items():
        manifest = _object(path / "manifest.json")
        keys = (
            "feature_id",
            "version",
            "definition_hash",
            "entity",
            "schedule",
            "window",
            "input_datasets",
            "values",
        )
        _require(
            {p.name for p in path.iterdir()} == {"manifest.json", "values.jsonl"},
            "feature inventory mismatch",
        )
        _require(
            manifest["schema"] == "entropytrade-research-feature-v1"
            and manifest["artifact_id"] == identifier
            and scientific_hash({k: manifest[k] for k in keys}) == identifier,
            "feature identity mismatch",
        )
        _hash(manifest["definition_hash"])
        _require(
            hashes.get(path / "values.jsonl") == _hash(manifest["values"]),
            "feature values checksum mismatch",
        )
        _require(
            re.fullmatch(r"[a-z][a-z0-9_]{0,63}", manifest["feature_id"]) is not None
            and isinstance(manifest["version"], str)
            and 1 <= len(manifest["version"]) <= 20
            and manifest["role"] in {"feature", "label"},
            "invalid feature definition metadata",
        )
        for point in manifest["schedule"]:
            DecisionPoint.model_validate(point)
        window = manifest["window"]
        _require(
            len(window) == 2 and date.fromisoformat(window[0]) <= date.fromisoformat(window[1]),
            "invalid feature window",
        )
        refs = manifest["input_datasets"]
        _require(
            isinstance(refs, list)
            and bool(refs)
            and refs == sorted(set(refs))
            and all(d in datasets for d in refs),
            "feature dataset reference mismatch",
        )
        for key in ("rows", "non_null", "events"):
            _integer(manifest[key])
        _require(
            manifest["events"] <= manifest["non_null"] <= manifest["rows"], "invalid feature counts"
        )
        _clock(manifest["created_at"])
        result[identifier] = manifest
    return result


def _boundaries(value: Any) -> list[str] | None:
    if value is None:
        return None
    _require(isinstance(value, list) and len(value) == 3, "invalid validation boundaries")
    parsed = [date.fromisoformat(d) for d in value]
    _require(parsed[0] < parsed[1] < parsed[2], "unordered validation boundaries")
    return list(value)


def _identity(
    identifier: str,
    identity: dict[str, Any],
    features: dict[str, dict[str, Any]],
    datasets: dict[str, dict[str, Any]],
) -> HypothesisSpec:
    _require(
        identity["schema"] == "entropytrade-research-modeling-v1"
        and scientific_hash(identity) == identifier,
        "experiment identity mismatch",
    )
    spec = HypothesisSpec.model_validate(identity["spec"])
    _require(identity["data_kind"] in {"real", "synthetic"}, "invalid experiment evidence kind")
    expected_kind = "authentic" if identity["data_kind"] == "real" else "synthetic"
    definitions = {
        name: Resolution.model_validate(value) for name, value in identity["definitions"].items()
    }
    _require(
        all(
            need.name in definitions and definitions[need.name].requested == need.name
            for need in (*spec.features, spec.label)
        ),
        "missing frozen feature resolution",
    )
    for reference in identity["features"]:
        artifact = features[reference["artifact_id"]]
        _require(
            all(
                reference[k] == artifact[k]
                for k in ("feature_id", "entity", "definition_hash", "values")
            ),
            "experiment feature reference mismatch",
        )
        matches = [d for d in definitions.values() if d.feature_id == artifact["feature_id"]]
        _require(
            bool(matches)
            and any(
                d.definition_hash == artifact["definition_hash"]
                and d.version == artifact["version"]
                and any(
                    need.role == artifact["role"]
                    and definitions[need.name].feature_id == d.feature_id
                    for need in (*spec.features, spec.label)
                )
                for d in matches
            ),
            "frozen feature definition mismatch",
        )
        _require(
            all(datasets[d]["data_kind"] == expected_kind for d in artifact["input_datasets"]),
            "experiment dataset evidence kind mismatch",
        )
    for dataset in identity["execution_datasets"]:
        _require(
            datasets[dataset]["data_kind"] == expected_kind,
            "execution dataset evidence kind mismatch",
        )
    for value in identity["fee_versions"]:
        version = FeeVersion.model_validate(value)
        _hash(version.version)
    for digest in identity["code"].values():
        _hash(digest)  # Preserve historical code/runtime identities; never compare today's code.
    _boundaries(identity["config"]["boundaries"])
    _require(
        identity["config"].get("evaluate_holdout") is False, "protected holdout evaluation enabled"
    )
    return spec


def _experiments(
    root: Path,
    hashes: dict[Path, str],
    features: dict[str, dict[str, Any]],
    datasets: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    results = {}
    for identifier, path in _committed(root, "experiments").items():
        checksums = _object(path / "checksums.json")
        _require(
            {"results.json", "report.md"} <= set(checksums)
            and set(checksums) == {p.name for p in path.iterdir()} - {"checksums.json"},
            "experiment inventory mismatch",
        )
        for name, digest in checksums.items():
            _require(
                Path(name).name == name and hashes.get(path / name) == _hash(digest),
                "experiment artifact checksum mismatch",
            )
        result = _object(path / "results.json")
        _require(
            result["schema"] == "entropytrade-research-modeling-v1"
            and result["experiment_id"] == identifier,
            "experiment report identity mismatch",
        )
        identity = result["provenance"]["identity"]
        _identity(identifier, identity, features, datasets)
        _require(
            result["config"] == identity["config"]
            and result["data_kind"] == identity["data_kind"]
            and result["boundaries"] == identity["config"]["boundaries"],
            "report frozen config mismatch",
        )
        _require(
            result["report"]
            == {"path": str(path.relative_to(root) / "report.md"), "hash": checksums["report.md"]},
            "report reference mismatch",
        )
        _require(
            result["validation"].get("holdout_evaluated") is False,
            "protected holdout was evaluated",
        )
        _require(
            result["provenance"]["feature_artifacts"] == identity["features"]
            and result["provenance"]["feature_definitions"] == identity["definitions"],
            "report feature provenance mismatch",
        )
        expected_datasets = sorted(
            {d for a in identity["features"] for d in features[a["artifact_id"]]["input_datasets"]}
        )
        _require(
            result["provenance"]["dataset_versions"] == expected_datasets,
            "report dataset provenance mismatch",
        )
        for model in result["models"].values():
            filename = model["file"]
            _require(
                isinstance(filename, str)
                and filename.endswith(".joblib")
                and checksums.get(filename) == _hash(model["artifact_hash"]),
                "model reference checksum mismatch",
            )
            if "portable" in model:
                portable = model["portable"]
                filename = portable["file"]
                _require(
                    isinstance(filename, str)
                    and filename.endswith(".paper.json")
                    and checksums.get(filename) == _hash(portable["sha256"]),
                    "portable model reference checksum mismatch",
                )
        results[identifier] = result
    return results


def _rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_JSON_BYTES)
        db.execute("PRAGMA trusted_schema=OFF")
        # Bound even corrupt/adversarial metadata queries; no executable schema objects.
        steps = 0

        def progress() -> int:
            nonlocal steps
            steps += 1000
            return int(steps > 100_000_000)

        db.set_progress_handler(progress, 1000)
        objects = db.execute("SELECT type,name FROM sqlite_master").fetchall()
        actual = {r["name"] for r in objects if r["type"] == "table"}
        _require(
            actual == set(TABLES) and all(r["type"] in {"table", "index"} for r in objects),
            "unsupported database schema",
        )
        for table, columns in TABLES.items():
            info = list(db.execute(f"PRAGMA table_info({table})"))
            expected = [
                (
                    c,
                    "INTEGER"
                    if c in INTEGER_COLUMNS
                    and not (table == "research_features" and c == "version")
                    else "TEXT",
                )
                for c in columns.split()
            ]
            _require(
                [(r["name"], r["type"]) for r in info] == expected, "unsupported database columns"
            )
        _require([r[0] for r in db.execute("PRAGMA integrity_check")] == ["ok"], "corrupt database")
        result = {}
        count = 0
        for table in TABLES:
            rows = [dict(row) for row in db.execute(f"SELECT * FROM {table} LIMIT {MAX_ROWS + 1}")]  # noqa: S608 - fixed allowlisted table
            count += len(rows)
            _require(count <= MAX_ROWS, "database row budget exceeded")
            result[table] = rows
        return result
    finally:
        db.close()


def _database(
    path: Path,
    features: dict[str, dict[str, Any]],
    datasets: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
) -> dict[str, int]:
    tables = _rows(path)
    jobs = {_uuid(r["id"]): r for r in tables["research_jobs"]}
    for table, rows in tables.items():
        for row in rows:
            for key in (
                "created_at",
                "updated_at",
                "next_run_at",
                "next_attempt_at",
                "next_check_at",
                "estimated_ready_at",
                "first_seen",
                "at",
            ):
                if key in row and row[key] is not None:
                    _clock(row[key])
            if "job_id" in row:
                _require(row["job_id"] in jobs, "orphaned " + table)
            if row.get("error") is not None:
                _require(isinstance(_json(row["error"]), dict), "invalid stored error")
    for job in jobs.values():
        request = ResearchRequest.model_validate_json(job["request"])
        _require(
            request.fingerprint() == job["fingerprint"] and request.family == job["family"],
            "job request identity mismatch",
        )
        ResearchRequest.check_universe(tuple(_json(job["universe"])))
        JobStatus(job["status"])
        _integer(job["attempts"], maximum=1_000_000)
        _require(isinstance(_json(job["checkpoint"]), dict), "invalid checkpoint")
        usage = _json(job["usage"])
        _require(
            set(usage)
            == {
                "ai_usd",
                "ai_requests",
                "input_tokens",
                "output_tokens",
                "http_requests",
                "bytes",
                "runtime_seconds",
            },
            "invalid usage inventory",
        )
        usd = Decimal(str(usage["ai_usd"]))
        _require(usd.is_finite() and 0 <= usd <= Decimal("1000000"), "invalid AI usage")
        for key in ("ai_requests", "input_tokens", "output_tokens", "http_requests", "bytes"):
            _integer(usage[key], maximum=10**12)
        runtime = usage["runtime_seconds"]
        _require(
            type(runtime) in {int, float} and math.isfinite(runtime) and 0 <= runtime <= 10**12,
            "invalid runtime usage",
        )
    hypotheses: dict[tuple[str, str, int], HypothesisSpec] = {}
    for row in tables["research_hypotheses"]:
        spec = HypothesisSpec.model_validate_json(row["spec"])
        _require(
            spec.hypothesis_id == row["hypothesis_id"]
            and spec.version == row["version"]
            and spec.family == jobs[row["job_id"]]["family"],
            "hypothesis identity mismatch",
        )
        _require(
            HypothesisStatus(row["status"]) in RESEARCH_SETTABLE,
            "unsupported research hypothesis status",
        )
        _integer(row["rank"])
        _require(
            isinstance(_json(row["reasons"]), list) and isinstance(_json(row["facets"]), dict),
            "invalid hypothesis assessment",
        )
        hypotheses[(row["job_id"], spec.hypothesis_id, spec.version)] = spec
    hypothesis_links = {(job, identifier) for job, identifier, _ in hypotheses}
    for row in tables["research_signatures"]:
        _hash(row["signature"])
        _require(
            (row["first_job_id"], row["hypothesis_id"]) in hypothesis_links
            and any(
                spec.signature == row["signature"]
                for (job, identifier, _), spec in hypotheses.items()
                if job == row["first_job_id"] and identifier == row["hypothesis_id"]
            ),
            "orphaned hypothesis signature",
        )
        _integer(row["searches"], minimum=1, maximum=MAX_ROWS)
    requirements = {}
    for row in tables["research_requirements"]:
        requirement = DataRequirement.model_validate_json(row["spec"])
        expected = requirement_id(
            kind=requirement.kind,
            family=requirement.family,
            entity=requirement.entity,
            variable=requirement.variable,
            clock=requirement.clock,
            fidelity=requirement.fidelity,
        )
        if requirement.min_sources > 1:
            expected += f"-s{requirement.min_sources}"
        _require(
            requirement.requirement_id == row["requirement_id"] == expected
            and requirement.family == jobs[row["job_id"]]["family"]
            and all(
                (row["job_id"], h) in hypothesis_links
                for h in (*requirement.hypotheses, *requirement.predictive_for)
            ),
            "requirement identity/reference mismatch",
        )
        if row["assessment"] is not None:
            assessment = Assessment.model_validate_json(row["assessment"])
            _require(
                assessment.requirement_id == requirement.requirement_id,
                "assessment reference mismatch",
            )
            # Inventory may also name retained external snapshot/configured datasets.
            for dataset in assessment.datasets:
                if HASH.fullmatch(dataset):
                    _require(dataset in datasets, "assessment dataset reference mismatch")
        requirements[(row["job_id"], row["requirement_id"])] = requirement
    for row in tables["research_resolutions"]:
        resolution = Resolution.model_validate_json(row["resolution"])
        _require(
            (row["job_id"], row["hypothesis_id"]) in hypothesis_links
            and resolution.requested == row["requested"],
            "resolution reference mismatch",
        )
        if resolution.definition_hash is not None:
            _hash(resolution.definition_hash)
    for row in tables["research_sources"]:
        decision = SourceDecision.model_validate_json(row["decision"])
        _require(
            (row["job_id"], row["requirement_id"]) in requirements
            and decision.source_id == row["source_id"]
            and decision.requirement_id == row["requirement_id"],
            "source decision reference mismatch",
        )
    acquisitions = {_uuid(r["id"]): r for r in tables["research_acquisitions"]}
    for row in acquisitions.values():
        _hash(row["acquisition_key"])
        _require(
            row["status"]
            in {"queued", "running", "awaiting_approval", "completed", "failed", "denied"}
            and isinstance(_json(row["params"]), dict),
            "invalid acquisition",
        )
        for key in ("attempts", "requests", "bytes"):
            _integer(row[key], maximum=10**12)
        if row["dataset_id"] is not None:
            _require(row["dataset_id"] in datasets, "acquisition dataset reference mismatch")
        _require(
            row["status"] != "completed" or row["dataset_id"] is not None,
            "completed acquisition lacks dataset",
        )
    for row in tables["research_acquisition_links"]:
        _require(
            row["acquisition_id"] in acquisitions
            and row["approval"] in {"automatic", "pending", "approved", "denied", "inherited"},
            "acquisition link mismatch",
        )
        _require(
            (row["job_id"], row["requirement_id"]) in requirements
            or (
                row["requirement_id"] == "local-execution-evidence"
                and acquisitions[row["acquisition_id"]]["source_id"] == "local-restored-execution"
            ),
            "orphaned acquisition requirement",
        )
    forwards = {_uuid(r["id"]): r for r in tables["research_forward"]}
    for row in forwards.values():
        spec = _json(row["spec"])
        key = scientific_hash(
            {
                k: spec[k]
                for k in (
                    "kind",
                    "family",
                    "entity",
                    "variable",
                    "clock",
                    "fidelity",
                    "min_sources",
                )
            }
        )
        _require(
            row["coverage_key"] == key
            and row["status"] in {"satisfied", "awaiting_observations", "blocked_collector_change"},
            "invalid forward coverage",
        )
        _integer(row["events_required"], minimum=1, maximum=10_000)
        _integer(row["events_observed"])
    for row in tables["research_forward_links"]:
        _require(
            row["forward_id"] in forwards
            and (row["job_id"], row["requirement_id"]) in requirements,
            "orphaned forward link",
        )
        _require(
            forwards[row["forward_id"]]["coverage_key"]
            == requirements[(row["job_id"], row["requirement_id"])].coverage_key,
            "forward coverage reference mismatch",
        )
    registered = {}
    for row in tables["research_features"]:
        manifest = _json(row["manifest"])
        _require(
            row["artifact_id"] in features
            and manifest == features[row["artifact_id"]]
            and all(
                row[k] == manifest[k]
                for k in ("artifact_id", "feature_id", "version", "definition_hash", "entity")
            ),
            "registered feature reference mismatch",
        )
        registered[row["artifact_id"]] = row
    for row in tables["research_feature_links"]:
        ids = _json(row["hypothesis_ids"])
        _require(
            row["artifact_id"] in registered
            and isinstance(ids, list)
            and all((row["job_id"], h) in hypothesis_links for h in ids),
            "orphaned feature link",
        )
    boundaries = {}
    for row in tables["research_validation_boundaries"]:
        boundaries[_hash(row["scope"])] = _boundaries(_json(row["boundaries"]))
    for row in tables["research_experiments"]:
        _hash(row["id"])
        _require(
            row["status"] in {"queued", "running", "completed", "refused", "failed", "cancelled"},
            "invalid experiment status",
        )
        _integer(row["attempts"], maximum=1_000_000)
        config = _json(row["config"])
        spec = _identity(row["id"], config["identity"], features, datasets)
        _require(
            config["experiment_id"] == row["id"]
            and config["config"] == config["identity"]["config"]
            and config["boundaries"] == config["config"]["boundaries"]
            and spec.hypothesis_id == row["hypothesis_id"]
            and hypotheses.get((row["job_id"], spec.hypothesis_id, spec.version)) == spec,
            "experiment config/hypothesis reference mismatch",
        )
        frozen = boundaries.get(scientific_hash({"family": spec.family}))
        if config.get("freeze_ready"):
            _require(
                frozen is not None and frozen == config["boundaries"],
                "frozen shared boundary mismatch",
            )
        if row["result"] is not None:
            result = _json(row["result"])
            _require(
                result == experiments.get(row["id"])
                and result["provenance"]["identity"] == config["identity"],
                "persisted experiment report mismatch",
            )
        _require(
            row["status"] not in {"completed", "refused"} or row["result"] is not None,
            "completed experiment lacks immutable report",
        )
    for row in tables["research_events"]:
        _integer(row["sequence"], minimum=1)
    return {
        "jobs": len(jobs),
        "datasets": len(datasets),
        "features": len(features),
        "experiments": len(experiments),
    }


def validate_research(workspace: Path) -> dict[str, int]:
    """Validate all committed research without mutation, rescheduling or target parsing.

    The caller must hold the application lease and pass a checkpointed staged workspace.
    Legacy workspaces with no research directory remain valid. Existing incomplete trees
    refuse instead of being silently represented as empty research.
    """
    root = workspace / "research"
    if not root.exists() and not root.is_symlink():
        return {"jobs": 0, "datasets": 0, "features": 0, "experiments": 0}
    try:
        _require(root.is_dir(), "research root is not a directory")
        path = root / "research.sqlite"
        _require(path.is_file(), "research database is missing")
        for suffix in ("-wal", "-journal"):
            sidecar = path.with_name(path.name + suffix)
            _require(
                not sidecar.exists() or (sidecar.is_file() and sidecar.stat().st_size == 0),
                "research database is not checkpointed",
            )
        hashes = _inventory(root)
        datasets = _datasets(root, hashes)
        features = _features(root, hashes, datasets)
        experiments = _experiments(root, hashes, features, datasets)
        return _database(path, features, datasets, experiments)
    except (
        KeyError,
        TypeError,
        UnicodeError,
        OSError,
        sqlite3.Error,
        OverflowError,
        RecursionError,
    ) as exc:
        raise ValueError(
            "invalid or incomplete research recovery evidence: " + type(exc).__name__
        ) from exc
