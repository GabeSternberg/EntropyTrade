"""Inventory locally retained acceptance artifacts without staging or deleting evidence.

Use capture with a NEW --output and one or more --bundle paths relative to this repo.
Verify requires every original byte locally; a manifest alone cannot verify acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REVIEW_ROOT = Path("data/operating-acceptance-review")
PRUNED = {"installation", "uv-cache", "npm-cache"}
LIMITATIONS = [
    "These generated files remain at their original local paths and are excluded from new "
    "Git staging.",
    "A checkout contains reports and hashes, not the retained trace/archive bytes. Obtain those "
    "bytes "
    "separately before independently inspecting traces or replaying archived workspaces.",
    "Hashes establish byte identity only, not authenticity, successful execution or profitability.",
    "Missing, changed or additional local artifacts fail verification; missing bytes are never "
    "a pass.",
    "Installed environments and package/browser caches are excluded and are not preserved by this "
    "manifest. Historical source/install verification retains its original execution scope.",
]


def relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"Expected a normalized repository-relative path: {value}")
    return path


def confined(repo: Path, relative: Path) -> Path:
    relative_path(relative.as_posix())
    path = repo
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f"Evidence symlink is not permitted: {relative}")
    return path


def fingerprint(repo: Path, path: Path) -> dict[str, Any]:
    before = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Evidence changed during hashing: {path}")
    return {"path": path.relative_to(repo).as_posix(), "bytes": after.st_size, "sha256": digest}


def inventory(repo: Path, bundles: list[str]) -> dict[str, Any]:
    if not bundles or len(set(bundles)) != len(bundles):
        raise ValueError("Provide distinct evidence bundles")
    files = []
    receipts = []
    for name in sorted(bundles):
        relative = relative_path(name)
        if relative.parent != REVIEW_ROOT:
            raise ValueError(f"Bundle must be directly below {REVIEW_ROOT}")
        bundle = confined(repo, relative)
        if not bundle.is_dir():
            raise ValueError(f"Missing evidence bundle: {name}")
        receipt = confined(repo, relative / "acceptance.json")
        saved = json.loads(receipt.read_bytes())
        receipts.append(
            {
                **fingerprint(repo, receipt),
                "status": saved["status"],
                "acceptance_complete": saved["acceptance_complete"],
            }
        )
        for directory, dirs, names in os.walk(bundle, followlinks=False):
            for member in (*dirs, *names):
                if (Path(directory) / member).is_symlink():
                    raise ValueError(f"Evidence symlink is not permitted: {member}")
            dirs[:] = sorted(d for d in dirs if d not in PRUNED)
            for member in sorted(names):
                path = Path(directory) / member
                if (
                    "playwright-artifacts" in path.relative_to(bundle).parts
                    or path.suffix == ".zip"
                ):
                    if not path.is_file():
                        raise ValueError(f"Evidence is not a regular file: {path}")
                    files.append(fingerprint(repo, path))
    if not files:
        raise ValueError("No retained trace/archive evidence found")
    return {
        "bundles": sorted(bundles),
        "ignore_policy": fingerprint(repo, confined(repo, REVIEW_ROOT / ".gitignore")),
        "acceptance_receipts": receipts,
        "files": sorted(files, key=lambda item: item["path"]),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
    }


def capture(repo: Path, output: Path, bundles: list[str]) -> dict[str, Any]:
    target = confined(repo, output)
    if output.parent != REVIEW_ROOT or output.suffix != ".json":
        raise ValueError(f"JSON manifest must be directly below {REVIEW_ROOT}")
    manifest = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "limitations": LIMITATIONS,
        "inventory": inventory(repo, bundles),
    }
    with target.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    return manifest


def verify(repo: Path, manifest_path: Path) -> dict[str, Any]:
    saved = json.loads(confined(repo, manifest_path).read_bytes())
    if saved["schema_version"] != 1 or saved["limitations"] != LIMITATIONS:
        raise ValueError("Unsupported retention manifest")
    current = inventory(repo, saved["inventory"]["bundles"])
    if current != saved["inventory"]:
        raise ValueError(
            "Retained evidence inventory differs; preserve and investigate both versions"
        )
    return {
        "status": "verified_local_bytes",
        "file_count": current["file_count"],
        "total_bytes": current["total_bytes"],
        "acceptance_reexecuted": False,
        "v1_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("capture")
    create.add_argument("--output", required=True, type=relative_path)
    create.add_argument("--bundle", required=True, action="append")
    check = commands.add_parser("verify")
    check.add_argument("manifest", type=relative_path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.command == "capture":
        result = capture(repo, args.output, args.bundle)
        print(  # noqa: T201
            json.dumps({"manifest": str(args.output), "files": result["inventory"]["file_count"]})
        )
    else:
        print(json.dumps(verify(repo, args.manifest)))  # noqa: T201


if __name__ == "__main__":
    main()
