"""Local hash-linked snapshot chain. Controlled workspaces; no network, no empirical claim."""

from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
LATER = datetime(2026, 11, 8, 16, 0, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name in ("pyproject.toml", "uv.lock"):
        (tmp_path / name).write_text("CONTROLLED application identity")
    return tmp_path


def seed_actions_artifact(
    repo: Path, name: str = "artifact", run_id: str = "1", extra: str = "event=schedule\n"
) -> Path:
    source = Jobs(repo / "data/cache/seed-source")
    store = TrackingStore(source)
    monitor(store)
    out = repo / name
    out.mkdir()
    snapshot(repo, source.root, out / "workspace.zip")
    (out / "workspace.sha256").write_text(lc.sha256_file(out / "workspace.zip") + "\n")
    (out / "lineage.txt").write_text(
        f"commit=abc\nrun_id={run_id}\nbranch=main\nchain=head\n{extra}"
    )
    return out


IMPORTED = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def imp(repo: Path, chain: Path, artifact: Path, run: str, **kwargs: Any) -> dict[str, Any]:
    return lc.import_actions(repo, chain, artifact, run, clock=lambda: IMPORTED, **kwargs)


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
    artifact = seed_actions_artifact(repo, run_id="42288775503")
    (artifact / "previous-lineage.txt").write_text("run_id=42288000000\n")
    chain = repo / "data/cache/chain"
    imported = imp(repo, chain, artifact, "42288775503")
    assert imported["seq"] == 1
    lineage = lc.read_lineage(chain / "links/000001/lineage.txt")
    assert lineage["imported_from_run"] == "42288775503"
    assert lineage["imported_from_branch"] == "main"
    # The artifact's own lineage files are retained byte-for-byte.
    for source, kept in (("lineage.txt", "source-lineage.txt"), ("previous-lineage.txt",) * 2):
        assert (chain / "links/000001" / kept).read_bytes() == (artifact / source).read_bytes()
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
    assert second["previous_run_id"] == "42288775503"
    assert second["previous_manifest_sha256"] == lc.sha256_file(
        chain / "links/000001/manifest.json"
    )
    # The controlled repository is not a git checkout, so provenance says so explicitly.
    assert second["commit"] == "unknown"
    assert second["worktree_dirty"] == "unknown"
    assert second["pyproject"].startswith("sha256:")
    assert (chain / "links/000002/snapshot.json").is_file()
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
    lc.run(repo, chain, 540, collector=collector(calls), clock=lambda: LATER)
    assert calls[1][2] == chain / "links/000002/runway-ledger.jsonl"


def test_failed_collection_still_publishes_a_verified_link(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    result = lc.run(repo, chain, 540, collector=collector([], exit_code=1))
    assert result["collector_exit_code"] == 1
    assert lc.verify(chain)["links"] == 2


def test_import_fails_closed_on_checksum_mismatch_and_nonempty_chain(repo: Path) -> None:
    artifact = seed_actions_artifact(repo)
    chain = repo / "data/cache/chain"
    (artifact / "workspace.sha256").write_text("sha256:" + "0" * 64 + "\n")
    with pytest.raises(lc.ChainError, match="checksum mismatch"):
        imp(repo, chain, artifact, "1")
    assert not (chain / "links").exists()
    (artifact / "workspace.sha256").write_text(lc.sha256_file(artifact / "workspace.zip"))
    imp(repo, chain, artifact, "1")
    with pytest.raises(lc.ChainError, match="only seeds an empty chain"):
        imp(repo, chain, artifact, "1")
    with pytest.raises(lc.ChainError, match="numeric"):
        imp(repo, repo / "data/cache/other", artifact, "abc")


def test_run_refuses_empty_chain_without_fresh_and_fresh_on_populated(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    with pytest.raises(lc.ChainError, match="empty chain"):
        lc.run(repo, chain, 540, collector=collector([]))
    imp(repo, chain, seed_actions_artifact(repo), "1")
    with pytest.raises(lc.ChainError, match="--fresh is refused"):
        lc.run(repo, chain, 540, fresh=True, collector=collector([]))


def test_tampered_link_is_detected_and_blocks_extension(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
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
    imp(repo, chain, seed_actions_artifact(repo), "1")
    lc.run(repo, chain, 540, collector=collector([]))
    head = (chain / "HEAD").read_text()
    (chain / "HEAD").write_text("1 sha256:" + "0" * 64 + "\n")
    with pytest.raises(lc.ChainError, match="HEAD"):
        lc.verify(chain)
    (chain / "HEAD").write_text(head)
    lineage = chain / "links/000002/lineage.txt"
    lineage.write_text(lineage.read_text().replace("previous_sha256=", "previous_sha256=x"))
    with pytest.raises(lc.ChainError, match=r"lineage.txt checksum mismatch"):
        lc.verify(chain)
    lc._write_manifest(chain / "links/000002")  # a consistent rewrite still breaks the chain
    with pytest.raises(lc.ChainError, match="previous hashes do not match"):
        lc.verify(chain)


def test_gap_in_sequence_and_concurrent_lock_are_refused(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
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
    imp(repo, chain, seed_actions_artifact(repo), "1")
    before = (chain / "HEAD").read_text()

    def boom(*_: object) -> int:
        raise RuntimeError("collector crashed")

    with pytest.raises(RuntimeError):
        lc.run(repo, chain, 540, collector=boom)
    assert (chain / "HEAD").read_text() == before
    assert not list(chain.glob(".work-*"))
    assert not list(chain.glob(".stage-*"))
    # The work copy (possibly holding new evidence) is kept for inspection, never deleted.
    (kept,) = chain.glob(".failed-*")
    assert monitors_in(kept / "workspace") == 1
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


def test_import_refuses_trial_mismatched_or_unlabelled_artifacts(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    trial = seed_actions_artifact(repo, "trial", extra="event=push\n")
    with pytest.raises(lc.ChainError, match="chain head"):
        imp(repo, chain, trial, "1")
    head = seed_actions_artifact(repo, "head", run_id="42288775503")
    with pytest.raises(lc.ChainError, match="!= --source-run"):
        imp(repo, chain, head, "1")
    with pytest.raises(lc.ChainError, match="--source-branch"):
        imp(repo, chain, head, "42288775503", source_branch="claude/x")
    (head / "lineage.txt").unlink()
    with pytest.raises(lc.ChainError, match=r"missing lineage.txt"):
        imp(repo, chain, head, "42288775503")
    assert not (chain / "links").exists()


def test_tampering_with_any_link_file_is_detected(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    lc.run(repo, chain, 540, collector=collector([], exit_code=1))
    lineage = chain / "links/000002/lineage.txt"
    original = lineage.read_text()
    lineage.write_text(original.replace("collector_exit_code=1", "collector_exit_code=0"))
    with pytest.raises(lc.ChainError, match=r"lineage.txt checksum mismatch"):
        lc.verify(chain)
    lineage.write_text(original)
    (chain / "links/000002/runway-ledger.jsonl").write_text("{}\n")
    with pytest.raises(lc.ChainError, match=r"runway-ledger.jsonl checksum mismatch"):
        lc.run(repo, chain, 540, collector=collector([]))
    (chain / "links/000002/runway-ledger.jsonl").unlink()
    with pytest.raises(lc.ChainError, match="differ from the manifest"):
        lc.verify(chain)


def test_interrupted_head_update_is_rolled_forward_by_the_next_run(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    lagging = (chain / "HEAD").read_text()
    second = lc.run(repo, chain, 540, collector=collector([]), clock=lambda: FIXED)
    (chain / "HEAD").write_text(lagging)  # crash between the link rename and HEAD
    with pytest.raises(lc.ChainError, match="HEAD"):
        lc.verify(chain)
    third = lc.run(repo, chain, 540, collector=collector([]), clock=lambda: LATER)
    assert third["seq"] == 3
    assert (
        lc.read_lineage(chain / "links/000003/lineage.txt")["previous_sha256"] == (second["sha256"])
    )
    assert lc.verify(chain)["links"] == 3


def test_chain_outside_data_cache_is_refused_before_collection(repo: Path) -> None:
    calls: list[tuple[Path, int, Path | None]] = []
    with pytest.raises(lc.ChainError, match="chain directory refused"):
        lc.run(repo, repo / "elsewhere", 540, fresh=True, collector=collector(calls))
    assert calls == []
    with pytest.raises(lc.ChainError, match="seconds"):
        lc.run(repo, repo / "data/cache/chain", 30, fresh=True, collector=collector(calls))


def test_clock_regression_and_duplicate_run_id_are_refused(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    lc.run(repo, chain, 540, collector=collector([]), clock=lambda: LATER)
    with pytest.raises(lc.ChainError, match="already exists"):
        lc.run(repo, chain, 540, collector=collector([]), clock=lambda: LATER)
    with pytest.raises(lc.ChainError, match="not later"):
        lc.run(repo, chain, 540, collector=collector([]), clock=lambda: FIXED)
    assert lc.verify(chain)["links"] == 2


def test_stale_work_from_a_killed_run_blocks_until_inspected(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    (chain / ".work-999999").mkdir()
    calls: list[tuple[Path, int, Path | None]] = []
    with pytest.raises(lc.ChainError, match="stale"):
        lc.run(repo, chain, 540, collector=collector(calls))
    assert calls == []


def test_consistent_rewrite_of_the_newest_link_is_detected_by_head(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    lc.run(repo, chain, 540, collector=collector([], exit_code=1))
    link = chain / "links/000002"
    lineage = link / "lineage.txt"
    lineage.write_text(
        lineage.read_text().replace("collector_exit_code=1", "collector_exit_code=0")
    )
    lc._write_manifest(link)
    with pytest.raises(lc.ChainError, match="HEAD"):
        lc.verify(chain)
    with pytest.raises(lc.ChainError, match="HEAD"):
        lc.run(repo, chain, 540, collector=collector([]))


def test_run_clock_must_follow_the_import_clock(repo: Path) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")
    before = datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(lc.ChainError, match="imported_at"):
        lc.run(repo, chain, 540, collector=collector([]), clock=lambda: before)


def test_verify_refuses_a_missing_chain(repo: Path) -> None:
    with pytest.raises(lc.ChainError, match="no chain"):
        lc.verify(repo / "data/cache/typo")


def test_failure_after_collection_keeps_workspace_and_outputs(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = repo / "data/cache/chain"
    imp(repo, chain, seed_actions_artifact(repo), "1")

    def refuse(*_: object) -> None:
        raise ValueError("snapshot budget exceeded")

    monkeypatch.setattr(lc, "snapshot", refuse)
    with pytest.raises(ValueError, match="budget"):
        lc.run(repo, chain, 540, collector=collector([]))
    (kept,) = chain.glob(".failed-*")
    assert monitors_in(kept / "workspace") == 2
    assert (kept / "out/runway-ledger.jsonl").is_file()
    assert (kept / "out/summary.json").is_file()
    assert not list(chain.glob(".stage-*")) + list(chain.glob(".work-*"))
    assert lc.verify(chain)["links"] == 1


CHILD = """
import pathlib, sys, time
try:
    pathlib.Path(sys.argv[2]).write_text("ready")
    time.sleep(60)
except KeyboardInterrupt:
    pathlib.Path(sys.argv[1]).write_text("stopped normally")
"""

PARENT = """
import pathlib, signal, sys
from entropytrade.operations import local_chain as lc
signal.signal(signal.SIGTERM, lc._terminate)
lc._run_child([sys.executable, "-c", *sys.argv[1:]], pathlib.Path.cwd())
"""


def test_sigterm_asks_the_collector_to_stop_normally(tmp_path: Path) -> None:
    marker, ready = tmp_path / "marker", tmp_path / "ready"
    parent = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", PARENT, CHILD, str(marker), str(ready)]
    )
    deadline = time.monotonic() + 30
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    parent.send_signal(signal.SIGTERM)
    assert parent.wait(timeout=60) == 128 + signal.SIGTERM
    assert marker.read_text() == "stopped normally"
