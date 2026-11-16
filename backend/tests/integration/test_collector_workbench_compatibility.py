"""Legacy collector staging may serve without activating guarded research workflows."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from entropytrade.api.server import WorkbenchServer
from entropytrade.research.readiness import ResearchReadinessService
from entropytrade.tracking.readiness_store import READINESS_TABLES
from tests.integration.test_workbench_listener import listening
from tests.integration.test_workbench_process import REPO


@pytest.mark.parametrize("layout", ["named_chain", "head_and_links"])
def test_collector_staging_keeps_legacy_api_without_research_writes(layout: str) -> None:
    with TemporaryDirectory(prefix="collector-workbench-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        chain = parent / ("chain" if layout == "named_chain" else "retained-collector")
        chain.mkdir()
        if layout == "head_and_links":
            (chain / "HEAD").write_bytes(b"CONTROLLED collector head: never opened for research")
            (chain / "links").mkdir()
        workspace = chain / ".work-controlled"
        with listening(workspace, workers=False) as (server, client):
            assert server._readiness is None
            assert server.shadow.health_check is None
            catalog = client.get("/api/catalog")
            assert catalog.status_code == 200
            headers = {"X-EntropyTrade-CSRF": catalog.json()["csrf_token"]}
            for route in ("/api/monitors", "/api/weather/schedules", "/api/jobs"):
                assert client.get(route).status_code == 200
            created = client.post(
                "/api/jobs",
                json={
                    "idea": "CONTROLLED collector compatibility",
                    "family": "weather",
                    "mode": "recorded",
                },
                headers=headers,
            )
            assert created.status_code == 202
            assert server.jobs.get(created.json()["id"]) is not None
            for route in (
                "/api/controls",
                "/api/monitors/11111111-1111-4111-8111-111111111111/readiness",
                "/api/readiness/sha256:" + "a" * 64,
            ):
                assert client.get(route).status_code == 409
            halted = client.post(
                "/api/controls/halt", json={"reason": "CONTROLLED refusal"}, headers=headers
            )
            assert halted.status_code == 400
            assert "canonical collector" in halted.json()["error"]
            assert server._readiness is None
            with server.jobs.connect() as db:
                tables = {
                    row[0]
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
            assert not READINESS_TABLES.keys() & tables
            assert not (workspace / "research").exists()
        if layout == "head_and_links":
            assert (
                chain / "HEAD"
            ).read_bytes() == b"CONTROLLED collector head: never opened for research"
            assert not list((chain / "links").iterdir())


def test_workspace_symlink_still_refuses_before_creating_a_writer() -> None:
    with TemporaryDirectory(prefix="collector-workbench-alias-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        target = parent / "target"
        target.mkdir()
        alias = parent / "alias"
        alias.symlink_to(target, target_is_directory=True)
        with pytest.raises(ValueError, match="symlinks"):
            WorkbenchServer(REPO, alias, port=0)
        assert not list(target.iterdir())


def test_normal_workbench_keeps_eager_monitoring_and_fixture_service_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        TemporaryDirectory(prefix="research-workbench-", dir=REPO / "data/cache") as name,
        listening(Path(name), workers=False) as (server, _),
    ):
        assert server._readiness is server.readiness
        assert server.shadow.health_check is not None
        replacement = ResearchReadinessService(server.jobs.root, server.tracking)
        calls = []
        monkeypatch.setattr(replacement, "refresh_monitoring", lambda: calls.append(True))
        server.readiness = replacement
        server.shadow.health_check()
        assert server.readiness is replacement
        assert calls == [True]
