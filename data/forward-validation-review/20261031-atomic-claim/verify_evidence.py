"""Read-only evidence verification; byte identity cannot establish empirical performance."""

# ruff: noqa: S101 - this executable acceptance check consists of assertions.

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent


def read(name):
    return json.loads((BUNDLE / name).read_text())


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

for name, count in (("focused.xml", 50), ("pytest.xml", 1277)):
    suites = ET.parse(BUNDLE / name).getroot().findall("testsuite")  # noqa: S314 - local JUnit
    assert sum(int(s.attrib["tests"]) for s in suites) == count, name
    for key in ("failures", "errors", "skipped"):
        assert sum(int(s.attrib[key]) for s in suites) == 0, (name, key)

report = read("browser-verified/playwright-results.json")
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
    directory = BUNDLE / "browser-verified" / kind
    receipt = json.loads((directory / "browser-receipt.json").read_text())
    assert receipt["status"] == "passed"
    assert receipt["page_errors"] == []
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
        cancellation = operations["pause-at-acquisition-startup-barrier"]
        assert cancellation["before"]["status"] == "running"
        assert cancellation["after"]["status"] == "interrupted"
        assert cancellation["after"]["receipts"] == []
        request_id = cancellation["after"]["id"]
        for action in (
            "restart-preserves-interrupted-request",
            "restore-preserves-interrupted-request",
        ):
            assert operations[action]["id"] == request_id
assert screenshots == 11
assert downloads == 6
assert read("acceptance.json")["complete"] is False
assert read("acceptance.json")["status"] == "scoped_checks_passed"
print(  # noqa: T201 - local acceptance CLI
    "Verified sources, 73 safety files, 1,277 tests, browser cancellation and local artifacts."
)
