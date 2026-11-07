import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from entropytrade.operations.v1_gates import GATES, v1_gate_report
from tests.unit.test_workbench_http import exchange

if TYPE_CHECKING:
    from entropytrade.api.server import WorkbenchServer


def _status(report: dict[str, Any], gate: str) -> str:
    return str(next(g["status"] for g in report["gates"] if g["gate_id"] == gate))


def _write(root: Path, gate: str, **over: object) -> None:
    (root / "ev.txt").write_text("evidence")
    doc: dict[str, object] = {
        "gate_id": gate,
        "attested_by": "operator",
        "attested_at": "2026-11-07T00:00:00Z",
        "statement": "reviewed",
        "evidence": [{"path": "ev.txt", "sha256": hashlib.sha256(b"evidence").hexdigest()}],
    }
    doc.update(over)
    (root / f"{gate}.json").write_text(json.dumps(doc))


def test_empty_root_is_all_open(tmp_path: Path) -> None:
    report = v1_gate_report(tmp_path)
    assert not report["v1_complete"]
    assert report["open"] == [g[0] for g in GATES]


def test_valid_attestation(tmp_path: Path) -> None:
    _write(tmp_path, "certified_fees")
    assert _status(v1_gate_report(tmp_path), "certified_fees") == "attested"


@pytest.mark.parametrize(
    "over",
    [
        {"gate_id": "other"},
        {"attested_by": " "},
        {"evidence": []},
        {"evidence": [{"path": "ev.txt", "sha256": "0" * 64}]},
        {"evidence": [{"path": "../ev.txt", "sha256": "0" * 64}]},
        {"evidence": [{"path": "missing.txt", "sha256": "0" * 64}]},
    ],
)
def test_invalid_attestations_fail_closed(tmp_path: Path, over: dict[str, object]) -> None:
    _write(tmp_path, "certified_fees", **over)
    report = v1_gate_report(tmp_path)
    assert _status(report, "certified_fees") == "invalid"
    assert "certified_fees" in report["open"]


def test_malformed_json_is_invalid(tmp_path: Path) -> None:
    (tmp_path / "second_family.json").write_text("{")
    assert _status(v1_gate_report(tmp_path), "second_family") == "invalid"


def test_complete_only_when_every_gate_attested(tmp_path: Path) -> None:
    for gate, _, _ in GATES:
        _write(tmp_path, gate)
    assert v1_gate_report(tmp_path)["v1_complete"] is True


def test_gates_http_route_is_read_only_and_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "data" / "acceptance"
    root.mkdir(parents=True)
    _write(root, "certified_fees")
    (root / "second_family.json").write_text("{not json")
    server = cast(
        "WorkbenchServer",
        SimpleNamespace(repo=tmp_path, server_port=43128, token=str(uuid4())),
    )
    assert exchange(server, "/api/v1-gates", headers={"Host": "evil"})[0] == 403
    status, _, body = exchange(server, "/api/v1-gates")
    assert status == 200
    report = json.loads(body)
    assert report["submission_enabled"] is False
    assert report["v1_complete"] is False
    states = {g["gate_id"]: g["status"] for g in report["gates"]}
    assert states["certified_fees"] == "attested"
    assert states["second_family"] == "invalid"
    assert states["final_acceptance"] == "open"
    assert exchange(server, "/api/v1-gates", method="POST")[0] in {404, 405, 403}
