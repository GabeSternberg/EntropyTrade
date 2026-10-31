"""Integrity failures for local-only generated evidence; never browser acceptance evidence."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def retention() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_artifacts", "tools/review_artifacts.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def evidence(tmp_path: Path) -> tuple[Path, str, Path]:
    root = tmp_path / "data/operating-acceptance-review"
    bundle = root / "attempt"
    artifact = bundle / "browser/playwright-artifacts/.playwright-artifacts-0/action.trace"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"controlled trace bytes")
    (bundle / "workspace.zip").write_bytes(b"controlled archive bytes")
    (bundle / "acceptance.json").write_text(
        json.dumps({"status": "failed", "acceptance_complete": False})
    )
    (bundle / "browser/report.json").write_text("{}")
    (root / ".gitignore").write_text("**/playwright-artifacts/\n**/*.zip\n")
    cache = bundle / "installation"
    cache.mkdir()
    (cache / "not-evidence.zip").write_bytes(b"package cache")
    return tmp_path, str(bundle.relative_to(tmp_path)), artifact


def test_retains_bytes_and_failed_status_with_exclusive_manifest(
    retention: ModuleType, evidence: tuple[Path, str, Path]
) -> None:
    repo, bundle, artifact = evidence
    output = Path("data/operating-acceptance-review/local-artifacts.json")
    original = artifact.read_bytes()
    result = retention.capture(repo, output, [bundle])
    assert artifact.read_bytes() == original
    assert result["inventory"]["file_count"] == 2
    assert result["inventory"]["acceptance_receipts"][0]["status"] == "failed"
    assert result["inventory"]["acceptance_receipts"][0]["acceptance_complete"] is False
    verified = retention.verify(repo, output)
    assert verified["status"] == "verified_local_bytes"
    assert verified["acceptance_reexecuted"] is False
    assert verified["v1_complete"] is False
    with pytest.raises(FileExistsError):
        retention.capture(repo, output, [bundle])


@pytest.mark.parametrize("failure", ["changed", "missing", "added", "receipt", "policy"])
def test_verification_refuses_changed_missing_or_added_evidence(
    retention: ModuleType, evidence: tuple[Path, str, Path], failure: str
) -> None:
    repo, bundle, artifact = evidence
    output = Path("data/operating-acceptance-review/local-artifacts.json")
    retention.capture(repo, output, [bundle])
    if failure == "changed":
        artifact.write_bytes(b"different trace bytes")
    elif failure == "missing":
        artifact.unlink()
    elif failure == "added":
        (artifact.parent / "new.trace").write_bytes(b"additional bytes")
    elif failure == "receipt":
        (repo / bundle / "acceptance.json").write_text(
            json.dumps({"status": "passed", "acceptance_complete": True})
        )
    else:
        (repo / output.parent / ".gitignore").write_text("changed policy")
    with pytest.raises(ValueError, match="inventory differs"):
        retention.verify(repo, output)


@pytest.mark.parametrize(
    "bundle",
    ["../outside", "/outside", "data/elsewhere", "data/operating-acceptance-review/attempt/child"],
)
def test_refuses_bundles_outside_direct_review_children(
    retention: ModuleType, evidence: tuple[Path, str, Path], bundle: str
) -> None:
    repo, _, _ = evidence
    with pytest.raises(ValueError, match=r"repository-relative|directly below"):
        retention.inventory(repo, [bundle])


@pytest.mark.parametrize("link_target", ["file", "directory", "bundle"])
def test_refuses_symlinks_in_evidence(
    retention: ModuleType, evidence: tuple[Path, str, Path], link_target: str
) -> None:
    repo, bundle, artifact = evidence
    outside = repo / "outside"
    outside.mkdir()
    if link_target == "file":
        artifact.unlink()
        artifact.symlink_to(outside / "missing.trace")
    elif link_target == "directory":
        (artifact.parent / "linked").symlink_to(outside, target_is_directory=True)
    else:
        link = repo / "data/operating-acceptance-review/linked-bundle"
        link.symlink_to(repo / bundle, target_is_directory=True)
        bundle = str(link.relative_to(repo))
    with pytest.raises(ValueError, match="symlink"):
        retention.inventory(repo, [bundle])
