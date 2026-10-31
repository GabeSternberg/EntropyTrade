"""Actual localhost projection/downloads and offline restore, separate from browser evidence."""

from pathlib import Path
from tempfile import TemporaryDirectory

from entropytrade.api.recovery import restore, snapshot
from entropytrade.tracking.prospective import report
from tests.integration.prospective_fixture import seed
from tests.integration.test_workbench_listener import listening
from tests.unit.test_tracking import REPO


def test_prospective_reports_downloads_and_offline_restore() -> None:
    with TemporaryDirectory(prefix="prospective-http-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        workspace = parent / "workspace"
        receipt = seed(workspace)
        route = f"/api/monitors/{receipt['monitor_id']}/evaluation"
        with listening(workspace, workers=False) as (server, client):
            saved = {suffix: client.get(route + suffix).content for suffix in ("", ".csv")}
            assert client.get(route).json() == receipt["report"]
            assert client.get(route + ".csv").headers["content-type"].startswith("text/csv")
            assert client.get(route, headers={"Host": "external.invalid"}).status_code == 403
            assert client.post(route, json={}).status_code == 403
            assert report(server.jobs, receipt["monitor_id"]) == receipt["report"]
        archive = parent / "offline.zip"
        snapshot(REPO, workspace, archive)
        restored = parent / "restored"
        restore(REPO, archive, restored)
        with listening(restored, workers=False) as (_, client):
            for suffix, expected in saved.items():
                assert client.get(route + suffix).content == expected
