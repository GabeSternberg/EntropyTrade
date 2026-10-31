"""Driver contract checks; fake tools never count as executed operating acceptance."""

import errno
import importlib.util
import json
import re
import socket
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def driver() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "local_acceptance", Path("tools/local_acceptance.py")
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_browser_coverage_includes_paper_alerts_and_research(driver: ModuleType) -> None:
    assert len(set(driver.REQUIRED_BROWSER_PROCEDURES)) == 6
    assert all(
        re.search(driver.DEFAULT_BROWSER_GREP, title)
        for _, title in driver.REQUIRED_BROWSER_PROCEDURES
    )
    for title in (
        "local operation and recovery",
        "provider-backed website",
        "authentic retained weather",
        "durable paper account: CONTROLLED synthetic fills",
        "durable paper account: authentic refusal",
        "operator alerts: acknowledgement, listener restart, recovery, recurrence "
        "and offline restore",
    ):
        assert re.search(driver.DEFAULT_BROWSER_GREP, title)


def browser_report(procedures: list[tuple[str, str]], *, execution: bool) -> dict[str, Any]:
    """Controlled JSON reporter contract; never evidence of an actual browser run."""
    return {
        "suites": [
            {
                "title": "nested suite",
                "suites": [
                    {
                        "specs": [
                            {
                                "file": file,
                                "title": title,
                                "ok": True,
                                "tests": [
                                    {
                                        "expectedStatus": "passed",
                                        "status": "expected" if execution else "skipped",
                                        "results": [{"status": "passed", "errors": []}]
                                        if execution
                                        else [],
                                    }
                                ],
                            }
                            for file, title in procedures
                        ]
                    }
                ],
            }
        ],
        "errors": [],
        "stats": {
            "expected": len(procedures) if execution else 0,
            "skipped": 0 if execution else len(procedures),
            "unexpected": 0,
            "flaky": 0,
        },
    }


@pytest.mark.parametrize("execution", [False, True])
def test_reports_require_exact_procedures_and_separate_discovery_from_execution(
    driver: ModuleType, tmp_path: Path, execution: bool
) -> None:
    procedures = list(driver.REQUIRED_BROWSER_PROCEDURES)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(browser_report(procedures, execution=execution)))
    result = driver.inspect_browser_report(path, execution=execution, require_all=True)
    assert result["status"] == "passed"
    assert not result["missing_required"]
    assert len(result["procedures"]) == 6
    assert len(result["sha256"]) == 64
    if not execution:
        result = driver.inspect_browser_report(path, execution=True, expected=procedures)
        assert result["status"] == "failed"


@pytest.mark.parametrize(
    "case",
    [
        "absent",
        "invalid_json",
        "empty",
        "missing_procedure",
        "wrong_file",
        "wrong_title",
        "duplicate",
        "no_tests",
        "missing_tests",
        "expected_failure",
        "static_skip",
        "skipped",
        "failed",
        "interrupted",
        "timedOut",
        "flaky",
        "unexpected",
        "no_results",
        "missing_results",
        "failed_attempt",
        "retry_failure",
        "attempt_error",
        "global_error",
        "spec_not_ok",
        "missing_stats",
        "bad_stats",
        "malformed_suite",
        "malformed_test",
        "malformed_attempt",
    ],
)
def test_incomplete_execution_reports_fail_closed(
    driver: ModuleType, tmp_path: Path, case: str
) -> None:
    procedures = list(driver.REQUIRED_BROWSER_PROCEDURES)
    report = browser_report(procedures, execution=True)
    specs = report["suites"][0]["suites"][0]["specs"]
    test = specs[0]["tests"][0]
    if case == "empty":
        report["suites"] = []
    elif case == "missing_procedure":
        specs.pop()
        report["stats"]["expected"] -= 1
    elif case in {"wrong_file", "wrong_title"}:
        specs[0][case.removeprefix("wrong_")] = "unrelated"
    elif case == "duplicate":
        specs.append(specs[0])
        report["stats"]["expected"] += 1
    elif case == "no_tests":
        specs[0]["tests"] = []
    elif case == "missing_tests":
        del specs[0]["tests"]
    elif case in {"expected_failure", "static_skip"}:
        test["expectedStatus"] = "failed" if case == "expected_failure" else "skipped"
    elif case in {"skipped", "failed", "interrupted", "timedOut"}:
        test["results"][0]["status"] = case
    elif case in {"flaky", "unexpected"}:
        test["status"] = case
    elif case == "no_results":
        test["results"] = []
    elif case == "missing_results":
        del test["results"]
    elif case == "failed_attempt":
        test["results"][0]["errors"] = [{"message": "failed assertion"}]
    elif case == "retry_failure":
        test["results"].insert(0, {"status": "failed"})
    elif case == "attempt_error":
        test["results"][0]["error"] = {"message": "failed assertion"}
    elif case == "global_error":
        report["errors"] = [{"message": "worker crashed"}]
    elif case == "spec_not_ok":
        specs[0]["ok"] = False
    elif case == "missing_stats":
        del report["stats"]
    elif case == "bad_stats":
        report["stats"]["skipped"] = 1
    elif case == "malformed_suite":
        report["suites"] = [None]
    elif case == "malformed_test":
        specs[0]["tests"] = [None]
    elif case == "malformed_attempt":
        test["results"] = [None]
    path = tmp_path / "report.json"
    if case != "absent":
        path.write_text("{truncated" if case == "invalid_json" else json.dumps(report))
    result = driver.inspect_browser_report(
        path, execution=True, expected=procedures, require_all=True
    )
    assert result["status"] == "failed"
    assert result["errors"]


def test_discovery_requires_full_inventory_even_when_report_counts_agree(
    driver: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(browser_report(list(driver.REQUIRED_BROWSER_PROCEDURES)[:1], execution=False))
    )
    result = driver.inspect_browser_report(path, execution=False, require_all=True)
    assert result["status"] == "failed"
    assert len(result["missing_required"]) == 5


def test_socket_creation_denial_retains_errno_and_operation(
    driver: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*args: object) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "socketpair", denied)
    result = driver.check_environment(43134)
    assert result["status"] == "blocked"
    assert {check["name"] for check in result["checks"]} == {
        "localhost_listener",
        "asyncio_socketpair",
    }
    for check in result["checks"]:
        assert check["status"] == "blocked"
        assert check["errno"] == errno.EPERM
        assert check["operation"] == "socket creation"
        assert "Operation not permitted" in check["failure"]


@pytest.mark.parametrize("deny_send", [False, True])
def test_socketpair_send_is_required_and_descriptors_close(
    driver: ModuleType, monkeypatch: pytest.MonkeyPatch, deny_send: bool
) -> None:
    class ProbeSocket:
        def __init__(self) -> None:
            self.closed = False

        def __enter__(self) -> "ProbeSocket":
            return self

        def __exit__(self, *args: object) -> None:
            self.closed = True

        def bind(self, address: tuple[str, int]) -> None:
            assert address == ("127.0.0.1", 43134)

        def listen(self, backlog: int) -> None:
            assert backlog == 1

        def sendall(self, data: bytes) -> None:
            assert data == b"x"
            if deny_send:
                raise PermissionError(errno.EPERM, "Operation not permitted")

        def recv(self, size: int) -> bytes:
            assert size == 1
            return b"x"

    listener, left, right = ProbeSocket(), ProbeSocket(), ProbeSocket()
    monkeypatch.setattr(socket, "socket", lambda *args: listener)
    monkeypatch.setattr(socket, "socketpair", lambda: (left, right))
    result = driver.check_environment(43134)
    assert result["status"] == ("blocked" if deny_send else "passed")
    assert all(probe.closed for probe in (listener, left, right))
    if deny_send:
        assert result["checks"][1]["operation"] == "socketpair send"
        assert result["checks"][1]["errno"] == errno.EPERM


@pytest.mark.parametrize(
    "mode",
    [
        "blocked",
        "prepare",
        "browser_failure",
        "passed",
        "partial",
        "prepare_partial",
        "custom_complete",
        "absent_discovery",
        "missing_discovery",
        "absent_selection",
        "empty_selection",
        "absent_execution",
        "missing_execution",
        "skipped_execution",
        "failed_execution",
        "empty_results",
        "partial_missing_execution",
    ],
)
def test_driver_outcomes_never_promote_missing_checks(
    driver: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    # Minimal disposable export plus fake processes exercise orchestration/receipts only.
    repo = tmp_path / "repo"
    repo.mkdir()
    cycle = "data/shadow-review/20261029-model-integration/completion/real-cycles/monitor/cycle/"
    for name in (
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "Makefile",
        ".gitignore",
        "THIRD_PARTY_NOTICES.md",
        "docs/project-spec.md",
        ".agents/skills/kalshi-docs/api-reference/market/get-series.md",
        ".agents/skills/kalshi-docs/getting_started/fee_rounding.md",
        "data/paper-accounting-review/20261031/final/controlled-export.json",
        cycle + "decision-inputs.json",
        cycle + "result.json",
        cycle + "public/manifest.json",
    ):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("controlled driver fixture\n")
    monkeypatch.setattr(driver, "__file__", str(repo / "tools/local_acceptance.py"))
    monkeypatch.setattr(driver.shutil, "which", lambda name: "/fixture/" + name)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-child-environment")
    commands: list[list[str]] = []
    partial = mode in {"partial", "prepare_partial", "partial_missing_execution"}
    prepare = mode in {"prepare", "prepare_partial"}

    class Process:
        def __init__(self, command: list[str], **kwargs: Any) -> None:
            commands.append(command)
            self.command = command
            self.pid = 1
            assert "OPENAI_API_KEY" not in kwargs["env"]
            assert "HOME" not in kwargs["env"]
            if "--check-environment" in command:
                kwargs["stdout"].write(
                    json.dumps({"status": "blocked" if mode == "blocked" else "passed"})
                )
            if "--list" in command or "--max-failures=1" in command:
                evidence = Path(kwargs["env"]["ENTROPYTRADE_BROWSER_EVIDENCE"])
                execution = "--list" not in command
                kind = "execution" if execution else evidence.name.removeprefix("browser-")
                if mode == "absent_" + kind:
                    return
                procedures = list(driver.REQUIRED_BROWSER_PROCEDURES)
                if partial and kind != "discovery":
                    procedures = [procedures[-1]]
                if mode == "missing_" + kind:
                    procedures.pop()
                if mode in {"empty_selection", "partial_missing_execution"} and (
                    kind == "selection" if mode == "empty_selection" else execution
                ):
                    procedures = []
                report = browser_report(procedures, execution=execution)
                if execution and mode in {
                    "skipped_execution",
                    "failed_execution",
                    "empty_results",
                    "browser_failure",
                }:
                    test = report["suites"][0]["suites"][0]["specs"][0]["tests"][0]
                    if mode == "empty_results":
                        test["results"] = []
                    else:
                        test["results"][0]["status"] = (
                            "skipped" if mode == "skipped_execution" else "failed"
                        )
                evidence.mkdir(parents=True)
                (evidence / "playwright-results.json").write_text(json.dumps(report))

        def __enter__(self) -> "Process":
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def wait(self, timeout: int) -> int:
            assert timeout > 0
            if "--check-environment" in self.command and mode == "blocked":
                return 1
            if "--max-failures=1" in self.command and mode == "browser_failure":
                return 1
            return 0

    monkeypatch.setattr(driver.subprocess, "Popen", Process)
    output = repo / "data/evidence"
    monkeypatch.setattr(
        sys,
        "argv",
        ["local_acceptance.py", "--output", str(output)]
        + (["--prepare-only"] if prepare else [])
        + (["--browser-grep", "operator alerts"] if partial else [])
        + (["--browser-grep", "."] if mode == "custom_complete" else []),
    )
    succeeds = mode in {"passed", "custom_complete", "prepare", "partial", "prepare_partial"}
    if not succeeds:
        with pytest.raises(RuntimeError):
            driver.main()
    else:
        driver.main()
    receipt = json.loads((output / "acceptance.json").read_text())
    assert receipt["acceptance_complete"] is (mode in {"passed", "custom_complete"})
    assert receipt["provisioning"]["reused_virtualenv"] is False
    assert receipt["browser_selection"] == (
        "operator alerts"
        if partial
        else "."
        if mode == "custom_complete"
        else driver.DEFAULT_BROWSER_GREP
    )
    legacy = "data/paper-accounting-review/20261031/final/controlled-export.json"
    assert (output / "installation" / legacy).read_bytes() == (repo / legacy).read_bytes()
    assert legacy in {entry["path"] for entry in receipt["source_files"]}
    for member in ("decision-inputs.json", "result.json", "public/manifest.json"):
        assert (output / "installation" / cycle / member).read_bytes() == (
            repo / cycle / member
        ).read_bytes()
    assert any("--list" in command for command in commands)
    browser_commands = [command for command in commands if "--max-failures=1" in command]
    suite_commands = [command for command in commands if command[0].endswith("/pytest")]
    early_failure = mode in {
        "absent_discovery",
        "missing_discovery",
        "absent_selection",
        "empty_selection",
    }
    if mode == "blocked" or prepare or early_failure:
        assert not browser_commands
        assert not suite_commands
        if not early_failure:
            assert {"browser", "pytest"}.issubset(receipt["unexecuted_checks"])
        assert receipt["status"] == (
            "failed"
            if early_failure
            else "blocked"
            if mode == "blocked"
            else "prepared; browser and full suite unverified"
        )
    else:
        assert len(browser_commands) == len(suite_commands) == 1
        assert receipt["status"] == (
            "partial; required browser procedures unexecuted"
            if partial and succeeds
            else "passed"
            if succeeds
            else "failed"
        )
    if mode == "partial":
        assert len(receipt["unexecuted_browser_procedures"]) == 5
        assert receipt["browser_reports"]["browser-discovery"]["missing_required"] == []
        assert len(receipt["browser_reports"]["browser"]["procedures"]) == 1
    for step in receipt["steps"]:
        if step["name"] in {"browser-discovery", "browser-selection", "browser"}:
            assert "result" in step
    if not succeeds and mode != "blocked":
        assert any(step["status"] == "failed" for step in receipt["steps"])
    if mode == "blocked":
        assert receipt["steps"][-1]["status"] == "blocked"
    if prepare:
        assert not any("--check-environment" in command for command in commands)
