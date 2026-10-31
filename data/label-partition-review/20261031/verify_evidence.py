"""Read-only verification of scoped software/operating evidence. V1 remains incomplete."""

# ruff: noqa: S101 - assertions are this executable evidence verifier's checks.

import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent


def read(name):
    return json.loads((BUNDLE / name).read_bytes())


def sha(path):
    assert path.is_file(), str(path)
    assert not path.is_symlink(), str(path)
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


for manifest in ("source-hashes.json", "documentation-hashes.json", "browser-hashes.json"):
    for name, digest in read(manifest).items():
        assert sha(ROOT / name) == digest, name
safety = read("safety-receipt.json")
assert safety["all_unchanged"]
assert len(safety["checks"]) == 73
for name, item in safety["checks"].items():
    assert sha(ROOT / name) == item["expected"], name
for item in read("retained-artifacts.json")["files"]:
    path = ROOT / item["path"]
    assert path.stat().st_size == item["bytes"], str(path)
    assert sha(path) == item["sha256"], str(path)
for name, count in (("focused.xml", 64), ("integrity.xml", 12), ("pytest-final.xml", 1292)):
    suites = ET.parse(BUNDLE / name).getroot().findall("testsuite")  # noqa: S314 - local JUnit
    assert sum(int(s.attrib["tests"]) for s in suites) == count, name
    for key in ("failures", "errors", "skipped"):
        assert sum(int(s.attrib[key]) for s in suites) == 0, (name, key)

report = read("browser-final/playwright-results.json")
assert report["errors"] == []
assert report["stats"]["expected"] == 2
assert all(report["stats"][key] == 0 for key in ("unexpected", "skipped", "flaky"))
shots = downloads = 0
for kind in ("authentic", "partition-controlled"):
    directory = BUNDLE / "browser-final" / kind
    receipt = json.loads((directory / "browser-receipt.json").read_bytes())
    assert receipt["status"] == "passed"
    assert receipt["page_errors"] == []
    assert "/frontend/browser/.browsers/" in receipt["executable"]
    shots += len(receipt["screenshots"])
    downloads += len(receipt["downloads"])
    for item in receipt["screenshots"] + receipt["downloads"]:
        assert sha(directory / item["file"]) == "sha256:" + item["sha256"]
    if kind == "authentic":
        original = (directory / "paused-state.json").read_bytes()
        assert (directory / "restart-state.json").read_bytes() == original
        assert (directory / "restored-state.json").read_bytes() == original
        acquisitions = next(
            op["acquisitions"]
            for op in receipt["operations"]
            if op["action"] == "authentic-new-acquisition"
        )
        assert sum(r["result"]["verified_events"] for r in acquisitions) == 3
        assert sum(r["result"]["refused_events"] for r in acquisitions) == 1
        for request in acquisitions:
            for row in request["result"]["records"]:
                observation = row["observation"]
                if observation:
                    assert observation["available_at"] == observation["received_at"]
            for source in request["receipts"]:
                assert source["status"] == 200
                assert source["received_at"]
                assert source["url"].startswith("https://weather.com/kalshi/api/climate/primary")
                assert base64.b64decode(source["body_base64"], validate=True)
    else:
        rows = json.loads((directory / "controlled-requests.json").read_bytes())
        assert len(rows) == len({r["id"] for r in rows}) == 130
        assert sum(r["status"] == "interrupted" for r in rows) == 1
        assert sum(r["status"] == "completed" for r in rows) == 129
        assert sum(any(s["status"] == 503 for s in r["receipts"]) for r in rows) == 1
        calls = [
            json.loads(line)
            for line in (directory / "controlled-calls.jsonl").read_text().splitlines()
        ]
        assert len(calls) == len({c["request_id"] for c in calls}) == 130
        assert {c["request_id"] for c in calls} == {r["id"] for r in rows}
        seal = json.loads((directory / "sealed-partition.json").read_bytes())
        assert len(seal["requests"]) == 128
        assert seal["partition_id"] == "00000000"
        for name, initial in (
            ("schedule", "paused-schedule.json"),
            ("seal", "sealed-partition.json"),
            ("labels", "archived-labels.json"),
        ):
            original = (directory / initial).read_bytes()
            for stage in ("restart", "restore"):
                assert (directory / (stage + "-" + name + ".json")).read_bytes() == original
        inventory = json.loads((directory / "original-label-files.json").read_bytes())
        assert len(inventory) == 262
        workspaces = {op["workspace"] for op in receipt["operations"] if op["action"] == "start"}
        for workspace in workspaces:
            for name, digest in inventory.items():
                assert sha(Path(workspace) / "runs/weather-labels" / name) == "sha256:" + digest
assert shots == 14
assert downloads == 12
failed = read("browser-attempt-1/partition-controlled/browser-receipt.json")
assert failed["status"] == "failed"
assert "label replay audit mismatch" in failed["failure"]
acceptance = read("acceptance.json")
assert acceptance["complete"] is False
assert acceptance["status"] == "scoped_checks_passed"
assert acceptance["git_mutations"] is False
assert acceptance["credential_access"] is False
assert acceptance["submission_enabled"] is False
print(  # noqa: T201 - evidence CLI output
    "Verified 1,292 tests, two Chromium procedures, original safety hashes "
    "and retained artifacts; V1 incomplete."
)
