"""Local hash-linked snapshot chain. Controlled workspaces; no network, no empirical claim."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot, validate_database
from entropytrade.operations import local_chain as lc
from entropytrade.tracking.store import TrackingStore
from tests.unit.test_tracking import monitor

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FIXED = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED application identity")
    return tmp_path


def seed_actions_artifact(repo: Path, name: str = "artifact") -> Path:
    source = Jobs(repo / "data/cache/seed-source")
    store = TrackingStore(source)
    monitor(store)
    out = repo / name
    out.mkdir()
    snapshot(repo, source.root, out / "workspace.zip")
    (out / "workspace.sha256").write_text(lc.sha256_file(out / "workspace.zip") + "\n")
    (out / "lineage.txt").write_text("run_id=42288775503\nchain=head\n")
    return out


def monitors_in(workspace: Path) -> int:
    return int(validate_database(workspace)["monitors"])


def collector(calls: list[tuple[Path, int, Path | None]], exit_code: int = 0) -> Callable[..., int]:
    def collect(
        workspace: Path, out: Path, seconds: int, ledger_in: Path | None, run_id: str
    ) -> int:
        calls.append((workspace, seconds, ledger_in))
        monitor(TrackingStore(Jobs(workspace)))  # adds evidence on top of the restored head
        (out / "summary.json").write_text("{}")
        (out / "runway-ledger.jsonl").write_text(f'{{"run": "{run_id}"}}\n')
        return exit_code

    return collect


def test_import_then_run_extends_and_links_the_chain(repo: Path) -> None:
    artifact = seed_actions_artifact(repo)
    chain = repo / "data/cache/chain"
    imported = lc.import_actions(repo, chain, artifact, "42288775503")
    assert imported["seq"] == 1
    lineage = lc.read_lineage(chain / "links/000001/lineage.txt")
    assert lineage["imported_from_run"] == "42288775503"
    assert (chain / "links/000001/workspace.zip").read_bytes() == (
        artifact / "workspace.zip"
    ).read_bytes()
    calls: list[tuple[Path, int, Path | None]] = []
    result = lc.run(repo, chain, 540, collector=collector(calls), clock=lambda: FIXED)
    assert result["seq"] == 2
    assert result["submission_enabled"] is False
    assert calls[0][1] == 540
    second = lc.read_lineage(chain / "links/000002/lineage.txt")
    assert second["previous_sha256"] == imported["sha256"]
    assert second["run_id"] == "local-20261108T120000Z"
    assert lc.verify(chain) == {
        "schema": lc.SCHEMA,
        "links": 2,
        "head_sha256": result["sha256"],
    }
    # The work copy is removed; the restored head carried the earlier evidence forward.
    assert not list(chain.glob(".work-*"))
    assert not list(chain.glob(".stage-*"))
    check = repo / "data/cache/check"
    restore(repo, chain / "links/000002/workspace.zip", check)
    assert monitors_in(check) == 2
    # The next run passes the previous link's ledger to the collector.
    lc.run(repo, chain, 540, collector=collector(calls), clock=lambda: FIXED)
    assert calls[1][2] == chain / "links/000002/runway-ledger.jsonl"


def test_failed_collection_still_publishes_a_verified_link(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    lc.import_actions(repo, chain, seed_actions_artifact(repo), "1")
    result = lc.run(repo, chain, 540, collector=collector([], exit_code=1))
    assert result["collector_exit_code"] == 1
    assert lc.verify(chain)["links"] == 2


def test_import_fails_closed_on_checksum_mismatch_and_nonempty_chain(repo: Path) -> None:
    artifact = seed_actions_artifact(repo)
    chain = repo / "data/cache/chain"
    (artifact / "workspace.sha256").write_text("sha256:" + "0" * 64 + "\n")
    with pytest.raises(lc.ChainError, match="checksum mismatch"):
        lc.import_actions(repo, chain, artifact, "1")
    assert not (chain / "links").exists()
    (artifact / "workspace.sha256").write_text(lc.sha256_file(artifact / "workspace.zip"))
    lc.import_actions(repo, chain, artifact, "1")
    with pytest.raises(lc.ChainError, match="only seeds an empty chain"):
        lc.import_actions(repo, chain, artifact, "1")
    with pytest.raises(lc.ChainError, match="numeric"):
        lc.import_actions(repo, repo / "data/cache/other", artifact, "abc")


def test_run_refuses_empty_chain_without_fresh_and_fresh_on_populated(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    with pytest.raises(lc.ChainError, match="empty chain"):
        lc.run(repo, chain, 540, collector=collector([]))
    lc.import_actions(repo, chain, seed_actions_artifact(repo), "1")
    with pytest.raises(lc.ChainError, match="--fresh is refused"):
        lc.run(repo, chain, 540, fresh=True, collector=collector([]))


def test_tampered_link_is_detected_and_blocks_extension(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    lc.import_actions(repo, chain, seed_actions_artifact(repo), "1")
    lc.run(repo, chain, 540, collector=collector([]))
    zip_path = chain / "links/000001/workspace.zip"
    zip_path.write_bytes(zip_path.read_bytes() + b"x")
    with pytest.raises(lc.ChainError, match="checksum mismatch"):
        lc.verify(chain)
    with pytest.raises(lc.ChainError, match="checksum mismatch"):
        lc.run(repo, chain, 540, collector=collector([]))
    assert len(list((chain / "links").iterdir())) == 2


def test_broken_hash_link_and_stale_head_are_detected(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    lc.import_actions(repo, chain, seed_actions_artifact(repo), "1")
    lc.run(repo, chain, 540, collector=collector([]))
    head = (chain / "HEAD").read_text()
    (chain / "HEAD").write_text("1 sha256:" + "0" * 64 + "\n")
    with pytest.raises(lc.ChainError, match="HEAD"):
        lc.verify(chain)
    (chain / "HEAD").write_text(head)
    lineage = chain / "links/000002/lineage.txt"
    lineage.write_text(lineage.read_text().replace("previous_sha256=", "previous_sha256=x"))
    with pytest.raises(lc.ChainError, match="previous_sha256"):
        lc.verify(chain)


def test_gap_in_sequence_and_concurrent_lock_are_refused(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    lc.import_actions(repo, chain, seed_actions_artifact(repo), "1")
    held = lc._lock(chain)
    try:
        with pytest.raises(lc.ChainError, match="lock"):
            lc.run(repo, chain, 540, collector=collector([]))
    finally:
        held.close()
    shutil.copytree(chain / "links/000001", chain / "links/000003")
    with pytest.raises(lc.ChainError, match="contiguous"):
        lc.verify(chain)


def test_collector_crash_leaves_chain_unchanged(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    lc.import_actions(repo, chain, seed_actions_artifact(repo), "1")
    before = (chain / "HEAD").read_text()

    def boom(*_: object) -> int:
        raise RuntimeError("collector crashed")

    with pytest.raises(RuntimeError):
        lc.run(repo, chain, 540, collector=boom)
    assert (chain / "HEAD").read_text() == before
    assert not list(chain.glob(".work-*"))
    assert not list(chain.glob(".stage-*"))
    assert lc.verify(chain)["links"] == 1


def test_fresh_starts_a_new_chain_only_when_requested(repo: Path) -> None:
    chain = repo / "data/cache/chain"

    def seed(workspace: Path, out: Path, seconds: int, ledger_in: Path | None, run_id: str) -> int:
        Jobs(workspace)
        monitor(TrackingStore(Jobs(workspace)))
        return 0

    result = lc.run(repo, chain, 540, fresh=True, collector=seed)
    assert result["seq"] == 1
    assert lc.read_lineage(chain / "links/000001/lineage.txt")["previous_sha256"] == ""
