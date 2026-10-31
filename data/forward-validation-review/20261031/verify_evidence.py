"""Read-only checks; hashes do not substitute for acceptance execution or provenance."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((BUNDLE / name).read_text())


for name, digest in read("source-hashes.json").items():
    assert sha(ROOT / name) == digest, name
for name, digest in read("documentation-hashes.json").items():
    assert sha(ROOT / name) == digest, name
for name, item in read("safety-receipt.json")["checks"].items():
    assert sha(ROOT / name) == item["expected"], name
for item in read("retained-artifacts.json")["files"]:
    path = ROOT / item["path"]
    assert path.is_file() and not path.is_symlink(), str(path)
    assert path.stat().st_size == item["bytes"], str(path)
    assert sha(path) == item["sha256"], str(path)
for kind in ("controlled", "authentic"):
    directory = BUNDLE / "browser-verified" / kind
    receipt = json.loads((directory / "browser-receipt.json").read_text())
    assert receipt["status"] == "passed", kind
    assert receipt["page_errors"] == [], kind
    for item in receipt["screenshots"] + receipt["downloads"]:
        assert sha(directory / item["file"]) == "sha256:" + item["sha256"]
    original = (directory / "paused-state.json").read_bytes()
    assert (directory / "restart-state.json").read_bytes() == original
    assert (directory / "restored-state.json").read_bytes() == original
print("Verified implementation sources, 73 safety files, browser artifacts/equality and retained local evidence.")
