"""Recovery checks dormant synthetic research without training or opening protected values."""

import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from entropytrade.api import recovery
from entropytrade.data.sources import file_hash
from entropytrade.research.recovery import validate_research
from entropytrade.research.store import ResearchStore
from tests.research_modeling_support import MODEL_NOW
from tests.research_paper_support import paper_fixture


@pytest.fixture(scope="module")
def frozen(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo = tmp_path_factory.mktemp("frozen-research")
    for name in ("pyproject.toml", "uv.lock"):
        (repo / name).write_text("CONTROLLED application identity\n")
    paper_fixture(repo / "data/cache/source")
    return repo


@pytest.fixture
def specimen(frozen: Path, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(frozen, repo)
    return repo


def _hashes(path: Path) -> dict[str, str]:
    return {str(p.relative_to(path)): file_hash(p) for p in path.rglob("*") if p.is_file()}


def _experiment(workspace: Path) -> Path:
    return next((workspace / "research/experiments").glob("sha256-*"))


def test_dormant_models_and_protected_values_are_hash_only_and_read_only(
    specimen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = specimen / "data/cache/source"
    before = _hashes(workspace)
    original = Path.open

    def guarded(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if path.name in {"records.jsonl", "values.jsonl"} or path.suffix == ".joblib":
            assert "b" in mode, "protected content must only be hashed"
            assert "r" in mode
        return original(path, mode, *args, **kwargs)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("recovery must never deserialize a model")

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr("joblib.load", forbidden)
    counts = validate_research(workspace)
    assert counts == {"jobs": 1, "datasets": 2, "features": 3, "experiments": 1}
    assert _hashes(workspace) == before


@pytest.mark.parametrize(
    "artifact",
    ["model", "portable", "report", "feature", "raw", "job-request", "experiment-ref", "schema"],
)
def test_corrupt_unpromoted_evidence_refuses_before_snapshot_publication(
    specimen: Path, artifact: str
) -> None:
    workspace = specimen / "data/cache/source"
    root = workspace / "research"
    if artifact in {"model", "portable", "report"}:
        pattern = {"model": "*.joblib", "portable": "*.paper.json", "report": "report.md"}[artifact]
        path = next(_experiment(workspace).glob(pattern))
        path.write_bytes(path.read_bytes() + b"CORRUPTION")
    elif artifact == "feature":
        path = next((root / "features").glob("sha256-*/values.jsonl"))
        path.write_bytes(path.read_bytes() + b"CORRUPTION")
    elif artifact == "raw":
        path = next(p for p in (root / "raw").rglob("*") if p.is_file())
        path.write_bytes(b"CORRUPTION")
    elif artifact == "schema":
        path = next((root / "datasets").glob("sha256-*/manifest.json"))
        manifest = json.loads(path.read_text())
        manifest["schema"] = "unsupported"
        path.write_text(json.dumps(manifest))
    else:
        with closing(sqlite3.connect(root / "research.sqlite")) as db, db:
            if artifact == "job-request":
                db.execute("UPDATE research_jobs SET fingerprint = 'wrong'")
            else:
                db.execute("UPDATE research_experiments SET id = 'sha256:' || ?", ("0" * 64,))
    archive = specimen / "data/recovery/refused.zip"
    with pytest.raises(ValueError, match=r"research|dataset|checksum"):
        recovery.snapshot(specimen, workspace, archive)
    assert not archive.exists()
    assert not list(archive.parent.glob(".snapshot-*"))


@pytest.mark.parametrize("pattern", ["*.joblib", "*.paper.json"])
def test_rewritten_artifact_checksum_cannot_disagree_with_frozen_model_reference(
    specimen: Path, pattern: str
) -> None:
    workspace = specimen / "data/cache/source"
    experiment = _experiment(workspace)
    path = next(experiment.glob(pattern))
    path.write_bytes(b"rewritten opaque artifact")
    checksums = json.loads((experiment / "checksums.json").read_text())
    checksums[path.name] = file_hash(path)
    (experiment / "checksums.json").write_text(json.dumps(checksums))
    with pytest.raises(ValueError, match="model reference checksum mismatch"):
        validate_research(workspace)


def test_unfinished_bytes_and_historical_identities_survive_restore_without_resume(
    specimen: Path,
) -> None:
    workspace = specimen / "data/cache/source"
    root = workspace / "research"
    unfinished = root / "experiments/.building-interrupted/opaque"
    unfinished.parent.mkdir()
    unfinished.write_bytes(b"never deserialize or resume\x00")
    with closing(sqlite3.connect(root / "research.sqlite")) as db, db:
        db.execute(
            "UPDATE research_jobs SET status='awaiting_observations', "
            "detail='historical waiting job'"
        )
    before = _hashes(root)
    archive = specimen / "data/recovery/valid.zip"
    recovery.snapshot(specimen, workspace, archive)
    destination = specimen / "data/cache/restored"
    result = recovery.restore(specimen, archive, destination)
    assert result["submission_enabled"] is False
    # SQLite backup may change database bytes; compare its logical history separately.
    for name, digest in before.items():
        if name != "research.sqlite" and not name.startswith("research.sqlite-"):
            assert file_hash(destination / "research" / name) == digest
    with closing(sqlite3.connect(destination / "research/research.sqlite")) as db:
        assert db.execute("SELECT status, detail FROM research_jobs").fetchone() == (
            "awaiting_observations",
            "historical waiting job",
        )


def test_restore_revalidates_staged_evidence_before_atomic_publication(
    specimen: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = specimen / "data/cache/source"
    archive = specimen / "data/recovery/valid.zip"
    recovery.snapshot(specimen, workspace, archive)
    original = recovery.validate_database

    def corrupt(stage: Path) -> dict[str, int]:
        next(_experiment(stage).glob("*.joblib")).write_bytes(b"staged corruption")
        return original(stage)

    monkeypatch.setattr(recovery, "validate_database", corrupt)
    destination = specimen / "data/cache/refused"
    with pytest.raises(ValueError, match="checksum"):
        recovery.restore(specimen, archive, destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".restore-*"))


def test_multi_source_policy_change_cannot_reuse_an_old_requirement_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_research_jobs import service, submit

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("inventory-only recovery test must remain offline")

    monkeypatch.setattr("httpx.HTTPTransport.handle_request", forbidden)
    svc = service(tmp_path)
    job_id = submit(svc)
    svc.run_until_idle()
    validate_research(svc.workspace)
    requirement = next(r for r in svc.store.requirements(job_id) if r.min_sources == 2)
    changed = requirement.revalidated(min_sources=3)
    with svc.store.connect() as db:
        db.execute(
            "UPDATE research_requirements SET spec=? WHERE job_id=? AND requirement_id=?",
            (changed.model_dump_json(), job_id, requirement.requirement_id),
        )
    with pytest.raises(ValueError, match="requirement identity/reference"):
        validate_research(svc.workspace)


def test_registered_feature_metadata_must_equal_its_frozen_manifest(specimen: Path) -> None:
    workspace = specimen / "data/cache/source"
    store = ResearchStore(workspace / "research")
    with store.connect() as db:
        job_id, hypothesis_id = db.execute(
            "SELECT job_id,hypothesis_id FROM research_hypotheses"
        ).fetchone()
    path = next((store.root / "features").glob("sha256-*/manifest.json"))
    manifest = json.loads(path.read_text())
    store.register_feature(job_id, manifest, [hypothesis_id], now=MODEL_NOW)
    validate_research(workspace)
    manifest["version"] = "forged"
    with store.connect() as db:
        db.execute("UPDATE research_features SET manifest=?", (json.dumps(manifest),))
    with pytest.raises(ValueError, match="registered feature reference"):
        validate_research(workspace)
