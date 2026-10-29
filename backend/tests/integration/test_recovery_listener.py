"""Actual HTTP, research/shadow subprocesses and restored downloads; no browser or doubles.

Recorded research reuses original real receipts. New public polls may fail honestly in
an offline environment; this proves recovery/inspection, never empirical performance.
"""

import json
import os
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from typing import Any
from zipfile import ZipFile

import httpx
import pytest

from entropytrade.api.jobs import TERMINAL, timestamp
from entropytrade.api.recovery import restore, snapshot_lease
from entropytrade.api.workspace import workspace_lease
from entropytrade.data.sources import file_hash
from entropytrade.tracking.replay import verify
from tests.integration.test_workbench_listener import listening
from tests.integration.test_workbench_process import REPO


@pytest.fixture
def root() -> Iterator[Path]:
    cache = REPO / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="recovery-listener-", dir=cache) as name:
        yield Path(name)


def until(read: Callable[[], Any], ready: Callable[[Any], bool], *, seconds: int = 120) -> Any:
    deadline = monotonic() + seconds
    while True:
        value = read()
        if ready(value):
            return value
        assert monotonic() < deadline, value
        sleep(0.05)


def post(client: httpx.Client, path: str, value: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        path,
        json=value,
        headers={"X-EntropyTrade-CSRF": client.get("/api/catalog").json()["csrf_token"]},
    )
    assert response.status_code in {200, 202}, response.text
    return dict(response.json())


def downloaded(client: httpx.Client, path: str) -> bytes:
    response = client.get(path)
    assert response.status_code == 200
    return response.content


def await_cycle(client: httpx.Client, monitor_id: str, sequence: int) -> dict[str, Any]:
    value = until(
        lambda: client.get(f"/api/monitors/{monitor_id}/export").json(),
        lambda m: any(c["sequence"] == sequence and c["status"] != "running" for c in m["cycles"]),
        seconds=260,
    )
    return dict(value)


def test_real_listener_workers_restore_downloads_shadow_recovery_and_cancellation(
    root: Path,
) -> None:
    original, restored = root / "original", root / "restored"
    evidence = root / "evidence"
    evidence.mkdir()
    receipt: dict[str, Any] = {
        "started_at": timestamp(),
        "browser_interaction": False,
        "worker": "unmodified research and shadow subprocesses",
        "listener": "actual ephemeral loopback HTTP",
        "empirical_performance": False,
        "submission_enabled": False,
    }
    with listening(original, shadow_workers=True) as (_, client):
        catalog = client.get("/api/catalog").json()
        assert catalog["submission_enabled"] is catalog["provider_enabled"] is False
        job_id = post(
            client,
            "/api/jobs",
            {
                "idea": "Test forecast_high_f > 70",
                "family": "weather",
                "mode": "recorded",
            },
        )["id"]
        job = until(
            lambda: client.get(f"/api/jobs/{job_id}").json(),
            lambda j: j["status"] in TERMINAL,
        )
        assert job["status"] == "completed", job
        review = downloaded(client, f"/api/jobs/{job_id}/review")
        report = downloaded(client, f"/api/jobs/{job_id}/report")
        result = json.loads(review)
        assert result["data_kind"] == "real"
        assert result["probability_count"] == 0
        assert not result["final_holdout_evaluated"]
        candidate = next(p for p in result["proposals"] if p.get("spec"))
        request = {
            "job_id": job_id,
            "candidate_id": candidate["candidate_id"],
            "interval_seconds": 60,
        }
        paused_id = post(client, "/api/monitors", request)["id"]
        await_cycle(client, paused_id, 1)
        post(client, f"/api/monitors/{paused_id}/pause", {})
        paused = downloaded(client, f"/api/monitors/{paused_id}/export")
        frozen = json.loads(paused)
        first = frozen["cycles"][0]
        assert first["result"].get("capture"), first
        assert first["result"].get("execution"), first
        assert first["result"]["artifacts"]
        assert all(d["prediction"] is d["intent"] is None for d in first["result"]["decisions"])
        active_id = post(client, "/api/monitors", request)["id"]
        # Observe a directory created by the real shadow subprocess before stopping.
        active = until(
            lambda: client.get(f"/api/monitors/{active_id}/export").json(),
            lambda m: (
                bool(m["cycles"])
                and (original / "shadow" / active_id / m["cycles"][0]["id"]).is_dir()
            ),
        )
        receipt["observed_active_cycle"] = active["cycles"][0]["id"]

    archive = evidence / "workspace.zip"
    with snapshot_lease(REPO, original, archive) as captured:
        receipt["snapshot"] = captured
        with ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
        receipt["restore"] = restore(REPO, archive, restored)
        # Compare before startup recovery or application stores can alter layout/state.
        with workspace_lease(restored):
            for item in manifest["files"]:
                assert file_hash(restored / item["path"]) == item["sha256"]
                if item["path"] not in {"jobs.sqlite", "registry.sqlite"}:
                    assert file_hash(original / item["path"]) == item["sha256"]
        (evidence / "snapshot-manifest.json").write_text(json.dumps(manifest, indent=2))

    with listening(restored) as (server, client):
        review_restored = downloaded(client, f"/api/jobs/{job_id}/review")
        report_restored = downloaded(client, f"/api/jobs/{job_id}/report")
        paused_restored = downloaded(client, f"/api/monitors/{paused_id}/export")
        assert review_restored == review
        assert report_restored == report
        assert paused_restored == paused
        recovered = client.get(f"/api/monitors/{active_id}/export").json()
        assert recovered["status"] == "active"
        prior = recovered["cycles"][0]
        assert prior["id"] == receipt["observed_active_cycle"]
        assert prior["status"] in {"interrupted", "completed", "failed"}
        assert prior["started_at"] == active["cycles"][0]["started_at"]
        assert recovered["model_binding"] == active["model_binding"]
        # Real controls make even a cycle completed during shutdown due now, with no
        # injected clock or database schedule changes. Start the unmodified runner.
        post(client, f"/api/monitors/{active_id}/pause", {})
        post(client, f"/api/monitors/{active_id}/resume", {})
        resumed_at = timestamp()
        server.shadow.start()
        fresh = await_cycle(client, active_id, 2)
        post(client, f"/api/monitors/{active_id}/pause", {})
        active_bytes = downloaded(client, f"/api/monitors/{active_id}/export")
        current, previous = fresh["cycles"]
        assert previous == prior
        assert current["id"] != prior["id"]
        assert current["result"].get("capture"), current
        assert current["result"]["capture"]["started_at"] >= resumed_at
        assert fresh["fills"] == []
        assert fresh["performance"] is None
        assert not fresh["submission_enabled"]
        for monitor in (frozen, fresh):
            for cycle in monitor["cycles"]:
                if cycle["result"] and "decisions" in cycle["result"]:
                    assert verify(restored / "shadow" / monitor["id"] / cycle["id"])["verified"]
        # Wait until the real research subprocess creates its run directory, then
        # cancel while the synthetic model workflow is in progress.
        cancelled = post(
            client,
            "/api/jobs",
            {
                "idea": "CONTROLLED cancellation software check",
                "family": "weather",
                "mode": "synthetic",
            },
        )["id"]
        until(
            lambda: client.get(f"/api/jobs/{cancelled}").json(),
            lambda j: j["status"] == "running" and (restored / "runs" / cancelled).is_dir(),
        )
        assert post(client, f"/api/jobs/{cancelled}/cancel", {}) == {"cancelled": True}
        until(
            lambda: client.get(f"/api/jobs/{cancelled}").json(),
            lambda j: j["status"] == "cancelled",
        )
        # Leave a durable running request for normal restart recovery as well.
        pending = post(
            client,
            "/api/jobs",
            {
                "idea": "CONTROLLED interrupted software check",
                "family": "weather",
                "mode": "synthetic",
            },
        )["id"]
        until(
            lambda: client.get(f"/api/jobs/{pending}").json(),
            lambda j: j["status"] == "running",
        )
    with listening(restored, shadow_workers=True) as (_, client):
        assert client.get(f"/api/jobs/{cancelled}").json()["status"] == "cancelled"
        assert client.get(f"/api/jobs/{pending}").json()["status"] == "interrupted"
        assert downloaded(client, f"/api/jobs/{job_id}/review") == review
        assert downloaded(client, f"/api/jobs/{job_id}/report") == report
        paused_restarted = downloaded(client, f"/api/monitors/{paused_id}/export")
        assert paused_restarted == paused
        assert downloaded(client, f"/api/monitors/{active_id}/export") == active_bytes
    for name, content in {
        "review.json": review,
        "report.txt": report,
        "review-restored.json": review_restored,
        "report-restored.txt": report_restored,
        "paused-original.json": paused,
        "paused-restored.json": paused_restored,
        "paused-restarted.json": paused_restarted,
        "active-recovered.json": active_bytes,
    }.items():
        (evidence / name).write_bytes(content)
    receipt.update(
        status="passed",
        finished_at=timestamp(),
        restarts=2,
        fresh_capture=current["result"]["capture"],
        prior_cycle_status=prior["status"],
    )
    (evidence / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if destination := os.environ.get("ENTROPYTRADE_RECOVERY_EVIDENCE"):
        target = Path(destination).absolute()
        assert target.is_relative_to(REPO / "data/local-operation-review")
        assert ".." not in target.parts
        target.mkdir(parents=True, exist_ok=False)
        shutil.copytree(evidence, target / "evidence")
        shutil.copytree(restored, target / "workspace")
