"""Controlled audit fixtures; no Git mutations or browser/full-suite execution evidence."""

import hashlib
import importlib.util
import json
import runpy
import shutil
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

from tests.unit.test_local_acceptance import browser_report

REPO = Path(__file__).resolve().parents[3]
VERIFIER = REPO / "data/operating-acceptance-review/20261031-checkpoint-repair/verify_checkpoint.py"


@pytest.fixture
def checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ModuleType, dict[tuple[str, ...], bytes]]:
    """Model clean-checkout Git visibility without needing ignored historical local bytes."""
    spec = importlib.util.spec_from_file_location("verify_checkpoint", VERIFIER)
    assert spec is not None
    assert spec.loader is not None
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    tools = tmp_path / "tools"
    tools.mkdir()
    for name in ("review_artifacts.py", "local_acceptance.py"):
        shutil.copyfile(REPO / "tools" / name, tools / name)
    review = tmp_path / "data/operating-acceptance-review"
    serial = review / "20261031-permitted-serial"
    browser = serial / "browser"
    browser.mkdir(parents=True)
    (review / ".gitignore").write_text("**/*.zip\n")
    source = tmp_path / "source.txt"
    source.write_bytes(b"controlled source bytes")
    installation = tmp_path / "installation"
    installation.mkdir()
    shutil.copyfile(source, installation / source.name)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (serial / "acceptance.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "acceptance_complete": True,
                "installation": str(installation),
                "source_files": [{"path": source.name, "sha256": digest}],
                "steps": [{"status": "passed", "exit_code": 0}],
            }
        )
    )
    (serial / "safety-receipt.json").write_text(
        json.dumps({"checks": {source.name: {"expected": "sha256:" + digest}}})
    )
    trace = browser / "trace.zip"
    with zipfile.ZipFile(trace, "w") as archive:
        archive.writestr("trace.txt", "controlled trace bytes")
    (serial / "verification.json").write_text(
        json.dumps(
            {
                "procedures": [
                    {
                        "artifacts": [
                            {
                                "path": "browser/trace.zip",
                                "bytes": trace.stat().st_size,
                                "sha256": audit.sha(trace),
                            }
                        ]
                    }
                ],
                "traces": [{"path": "browser/trace.zip", "sha256": audit.sha(trace)}],
                "downloads_verified": 0,
                "screenshots_verified": 0,
            }
        )
    )
    driver = runpy.run_path(str(tools / "local_acceptance.py"))
    (browser / "playwright-results.json").write_text(
        json.dumps(browser_report(list(driver["REQUIRED_BROWSER_PROCEDURES"]), execution=True))
    )
    (serial / "pytest.xml").write_text(
        '<testsuite tests="1210" failures="0" errors="0" skipped="0">'
        + '<testcase name="controlled"/>' * 1210
        + "</testsuite>"
    )
    retention = runpy.run_path(str(tools / "review_artifacts.py"))
    retention["capture"](
        tmp_path,
        Path("data/operating-acceptance-review/local-artifacts-20261031.json"),
        [serial.relative_to(tmp_path).as_posix()],
    )
    monkeypatch.setattr(audit, "REPO", tmp_path)
    monkeypatch.setattr(audit, "SERIAL", serial)
    ignored = trace.relative_to(tmp_path).as_posix().encode() + b"\0"
    responses = {
        ("ls-files", "-z"): source.name.encode() + b"\0",
        ("check-ignore", "--stdin", "-z"): ignored,
        ("diff", "HEAD", "--name-only", "-z"): b"",
        ("ls-files", "--others", "--exclude-standard", "-z"): b"",
        ("diff", "--cached", "--name-only"): b"",
    }

    def git(command: list[str], *, cwd: Path, input: bytes | None) -> bytes:
        assert cwd == tmp_path
        assert command[0] == "git"
        if command[1] == "check-ignore":
            assert input == ignored
        else:
            assert input is None
        return responses[tuple(command[1:])]

    monkeypatch.setattr(audit.subprocess, "check_output", git)
    return audit, responses


@pytest.mark.parametrize("dirty", [False, True])
def test_candidate_sizes_in_clean_and_dirty_checkouts(
    checkout: tuple[ModuleType, dict[tuple[str, ...], bytes]],
    capsys: pytest.CaptureFixture[str],
    dirty: bool,
) -> None:
    audit, responses = checkout
    if dirty:
        (audit.REPO / "modified.txt").write_bytes(b"123")
        (audit.REPO / "new.txt").write_bytes(b"1234567")
        responses[("diff", "HEAD", "--name-only", "-z")] = b"modified.txt\0deleted.txt\0"
        responses[("ls-files", "--others", "--exclude-standard", "-z")] = b"new.txt\0"
    before = {path: path.read_bytes() for path in audit.REPO.rglob("*") if path.is_file()}
    audit.main()
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert result["prospective_checkpoint_candidates"] == (2 if dirty else 0)
    assert result["largest_candidate_bytes"] == (7 if dirty else 0)
    assert result["candidate_files_over_8000000_bytes"] == []
    assert result["staging_index_empty"] is True
    assert result["git_mutations_performed"] is False
    assert result["browser_and_full_suite_reexecuted"] is False
    assert result["v1_complete"] is False
    assert {path: path.read_bytes() for path in audit.REPO.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("failure", ["oversized", "staged"])
def test_candidate_checks_still_fail_closed(
    checkout: tuple[ModuleType, dict[tuple[str, ...], bytes]],
    failure: str,
) -> None:
    audit, responses = checkout
    if failure == "oversized":
        (audit.REPO / "large.bin").write_bytes(b"x" * 8_000_001)
        responses[("ls-files", "--others", "--exclude-standard", "-z")] = b"large.bin\0"
        message = "Oversized checkpoint candidates"
    else:
        responses[("diff", "--cached", "--name-only")] = b"staged.txt\n"
        message = "Expected untouched empty staging index"
    with pytest.raises(ValueError, match=message):
        audit.main()
