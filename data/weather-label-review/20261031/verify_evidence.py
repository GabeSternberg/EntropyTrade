"""Read-only verification of source, browser, safety and locally retained evidence."""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((BUNDLE / name).read_text())


for name, digest in read("source-hashes.json").items():
    assert sha(REPO / name) == digest, name
for name, row in read("safety-receipt.json")["checks"].items():
    assert sha(REPO / name) == row["expected"], name
for item in read("retained-artifacts.json")["files"]:
    path = REPO / item["path"]
    assert path.is_file() and not path.is_symlink(), item["path"]
    assert path.stat().st_size == item["bytes"], item["path"]
    assert sha(path) == item["sha256"], item["path"]
receipt = json.loads((BUNDLE / "browser-verified/weather-label-browser-receipt.json").read_text())
assert receipt["status"] == "passed" and receipt["page_errors"] == []
for item in receipt["screenshots"] + receipt["downloads"]:
    assert sha(BUNDLE / "browser-verified" / item["file"]) == "sha256:" + item["sha256"]
for name in ("labels.json", "review.json", "report.txt"):
    root = BUNDLE / "browser-verified"
    assert (root / ("weather-" + name)).read_bytes() == (root / ("weather-restart-" + name)).read_bytes()
print("Verified source, original receipts/Bitcoin boundaries, browser downloads/screenshots and local trace/archive bytes.")
