"""Read-only checks of executed scoped acceptance; no empirical performance claim."""

# ruff: noqa: S101 - executable acceptance verification consists of assertions.

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent


def read(name):
    return json.loads((BUNDLE / name).read_text())


def sha(path):
    assert path.is_file() and not path.is_symlink(), str(path)
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


for manifest in ("source-hashes.json", "documentation-hashes.json", "browser-hashes.json"):
    for name, digest in read(manifest).items():
        assert sha(ROOT / name) == digest, name

safety = read("safety-receipt.json")
assert safety["all_unchanged"] and len(safety["checks"]) == 73
for name, item in safety["checks"].items():
    assert sha(ROOT / name) == item["expected"], name
for item in read("retained-artifacts.json")["files"]:
    path = ROOT / item["path"]
    assert path.stat().st_size == item["bytes"], str(path)
    assert sha(path) == item["sha256"], str(path)

for name, count, failures in (
    ("reproduction.xml", 2, 2),
    ("regressions.xml", 5, 0),
    ("focused.xml", 55, 0),
    ("pytest.xml", 1282, 0),
):
    suites = ET.parse(BUNDLE / name).getroot().findall("testsuite")  # noqa: S314 - local JUnit
    for key, expected in (("tests", count), ("failures", failures), ("errors", 0), ("skipped", 0)):
        assert sum(int(s.attrib[key]) for s in suites) == expected, (name, key)

report = read("browser/playwright-results.json")
assert report["errors"] == []
assert report["stats"]["expected"] == 2
assert all(report["stats"][key] == 0 for key in ("unexpected", "skipped", "flaky"))
specs = [spec for suite in report["suites"] for spec in suite["specs"]]
assert {s["title"] for s in specs} == {
    "continuous forward validation: controlled twelve-date transitions and recovery",
    "continuous forward validation: authentic shadow receipts and new label acquisition",
}
assert all(t["results"][-1]["status"] == "passed" for s in specs for t in s["tests"])

screenshots = downloads = 0
for kind in ("controlled", "authentic"):
    directory = BUNDLE / "browser" / kind
    receipt = json.loads((directory / "browser-receipt.json").read_text())
    assert receipt["status"] == "passed" and receipt["page_errors"] == []
    assert "/frontend/browser/.browsers/" in receipt["executable"]
    screenshots += len(receipt["screenshots"])
    downloads += len(receipt["downloads"])
    for item in receipt["screenshots"] + receipt["downloads"]:
        assert sha(directory / item["file"]) == "sha256:" + item["sha256"]
    original = (directory / "paused-state.json").read_bytes()
    assert (directory / "restart-state.json").read_bytes() == original
    assert (directory / "restored-state.json").read_bytes() == original
    if kind == "controlled":
        operations = {op["action"]: op for op in receipt["operations"]}
        failed = []
        for action in ("acquisition-error", "second-receipt-save-error"):
            op = operations[action]
            assert op["schedule"]["counts"] == {"verified": 2, "retry": 10}
            assert len(op["evidence"]) == 2
            for item in op["evidence"]:
                before, after = item["before"], item["request"]
                assert before["status"] == "running" and after["status"] == "failed"
                assert len(before["receipts"]) == 1
                assert after["receipts"] == before["receipts"]
                assert after["created_at"] == before["created_at"]
                assert after["result"]["verified_events"] == 1
                assert after["result"]["refused_events"] == len(after["selection"]["targets"]) - 1
                assert len(item["files"]) == 2
                failed.append(after["id"])
        for action in ("restart-preserves-failed-receipts", "restore-preserves-failed-receipts"):
            assert operations[action]["requests"] == failed
        cancellation = operations["pause-at-acquisition-startup-barrier"]
        assert cancellation["before"]["status"] == "running"
        assert cancellation["after"]["status"] == "interrupted"
        assert cancellation["after"]["receipts"] == []
        for action in (
            "restart-preserves-interrupted-request",
            "restore-preserves-interrupted-request",
        ):
            assert operations[action]["id"] == cancellation["after"]["id"]

assert screenshots == 13 and downloads == 6
acceptance = read("acceptance.json")
assert acceptance["complete"] is False and acceptance["status"] == "scoped_checks_passed"
assert acceptance["git_mutations"] is False and acceptance["credential_access"] is False
assert acceptance["submission_enabled"] is False
print(  # noqa: T201 - local evidence CLI
    "Verified receipt-loss reproduction, 1,282 passing tests, browser recovery, sources and safety."
)
