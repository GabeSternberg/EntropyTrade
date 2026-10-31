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


@pytest.mark.parametrize("mode", ["blocked", "prepare", "browser_failure", "passed"])
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
        + (["--prepare-only"] if mode == "prepare" else []),
    )
    if mode in {"blocked", "browser_failure"}:
        with pytest.raises(RuntimeError):
            driver.main()
    else:
        driver.main()
    receipt = json.loads((output / "acceptance.json").read_text())
    assert receipt["acceptance_complete"] is (mode == "passed")
    assert receipt["provisioning"]["reused_virtualenv"] is False
    assert receipt["browser_selection"] == driver.DEFAULT_BROWSER_GREP
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
    if mode in {"blocked", "prepare"}:
        assert not browser_commands
        assert not suite_commands
        assert {"browser", "pytest"}.issubset(receipt["unexecuted_checks"])
        assert receipt["status"] == (
            "blocked" if mode == "blocked" else "prepared; browser and full suite unverified"
        )
    else:
        assert len(browser_commands) == len(suite_commands) == 1
        assert receipt["status"] == ("passed" if mode == "passed" else "failed")
    if mode == "blocked":
        assert receipt["steps"][-1]["status"] == "blocked"
    if mode == "prepare":
        assert not any("--check-environment" in command for command in commands)
