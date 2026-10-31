"""Offline projection/restore with actual artifact bytes; no localhost or browser claims."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.data.sources import file_hash
from entropytrade.tracking.prospective import csv_report, report
from tests.integration.prospective_fixture import seed
from tests.unit.test_tracking import REPO


@pytest.mark.parametrize("authentic", [False, True])
def test_offline_recovery_preserves_report_and_original_evidence(authentic: bool) -> None:
    with TemporaryDirectory(prefix="prospective-offline-", dir=REPO / "data/cache") as name:
        parent = Path(name)
        root = parent / "workspace"
        receipt = seed(root, authentic=authentic)
        mid = receipt["monitor_id"]
        original = {
            p.relative_to(root).as_posix(): file_hash(p)
            for p in (root / "shadow").rglob("*")
            if p.is_file()
        }
        value = report(Jobs(root), mid)
        csv = csv_report(value)
        archive = parent / "snapshot.zip"
        snapshot(REPO, root, archive)
        restored = parent / "restored"
        restore(REPO, archive, restored)
        assert report(Jobs(restored), mid) == value
        assert csv_report(report(Jobs(restored), mid)) == csv
        assert all(file_hash(restored / p) == digest for p, digest in original.items())
