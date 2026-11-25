"""Research deployment stays separate and only maintains the fixed user service."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from entropytrade.api.owner import initialize
from entropytrade.operations import research_server as runtime


@pytest.fixture
def deployment(tmp_path: Path) -> runtime.Deployment:
    checkout = tmp_path / "EntropyTrade-research"
    checkout.mkdir()
    (checkout / "uv.lock").write_text("pinned lock\n")
    interpreter = checkout / ".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\nexit 0\n")
    interpreter.chmod(0o700)
    (checkout / ".venv/pyvenv.cfg").write_text("include-system-site-packages = false\n")
    source = Path(__file__).resolve().parents[3] / "deploy/research"
    shutil.copytree(source, checkout / "deploy/research")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    owner = private / "owner.json"
    initialize(owner, checkout, "research-owner", "test-only-owner-passphrase")
    provider = private / "providers.env"
    provider.write_text("ENTROPYTRADE_RESEARCH_OPENAI_API_KEY=test-only-key\n")
    provider.chmod(0o600)
    key = private / "public.asc"
    key.write_text("dummy public key; crypto validation belongs to backup tests\n")
    key.chmod(0o600)
    config_file = private / "deployment.json"
    config = runtime.Deployment(
        config_file=config_file,
        checkout=checkout,
        collector_checkout=tmp_path / "EntropyTrade-collector",
        owner_file=owner,
        provider_env=provider,
        recipient_file=key,
        recipient_fingerprint="A" * 40,
        private_origin="https://research.example.ts.net",
        tailscale_owner="owner@example.com",
        commit="a" * 40,
        uv_lock_sha256=hashlib.sha256((checkout / "uv.lock").read_bytes()).hexdigest(),
        uv=Path("/usr/bin/true"),
        python_version="3.13.14",
    )
    values = {
        name: str(getattr(config, name))
        for name in config.__dataclass_fields__
        if name != "config_file"
    }
    config_file.write_text(json.dumps(values))
    config_file.chmod(0o600)
    return config


@pytest.mark.parametrize("unsafe", ["collector", "overlap", "chain", "symlink", "outside"])
def test_layout_refuses_before_writes(tmp_path: Path, unsafe: str) -> None:
    checkout = tmp_path / "EntropyTrade-research"
    checkout.mkdir()
    collector = tmp_path / "EntropyTrade-collector"
    collector.mkdir()
    workspace = checkout / "data/cache/research"
    if unsafe == "collector":
        checkout = collector
        workspace = collector / "data/cache/research"
    elif unsafe == "overlap":
        collector = checkout / "nested-collector"
    elif unsafe == "chain":
        (checkout / ".chain").mkdir()
    elif unsafe == "symlink":
        (checkout / "data").symlink_to(collector, target_is_directory=True)
    else:
        workspace = tmp_path / "outside"
    before = sorted(str(path) for path in tmp_path.rglob("*"))
    with pytest.raises(ValueError, match=r"research|workspace|collector|symlink"):
        runtime.validate_research_layout(checkout, workspace, collector)
    assert sorted(str(path) for path in tmp_path.rglob("*")) == before
    assert not workspace.exists()


def test_load_and_render_private_research_units(
    deployment: runtime.Deployment, tmp_path: Path
) -> None:
    config = runtime.Deployment.load(deployment.config_file)
    output = tmp_path / "rendered"
    paths = runtime.render(config, output)
    server = paths[0].read_text()
    backup = paths[1].read_text()
    timer = paths[2].read_text()
    assert "KillSignal=SIGINT" in server
    assert "KillMode=mixed" in server
    assert "TimeoutStopSec=330" in server
    assert "SendSIGKILL=yes" in server
    assert "UMask=0077" in server
    assert "PrivateUsers=yes" in server
    assert "ProtectSystem=strict" in server
    assert f'InaccessiblePaths="-{config.collector_checkout}"' in server
    assert "User=" not in server
    assert f'ExecStart="{config.python}"' in server
    assert "research_server backup" in backup
    assert "TimeoutStartSec=20min" in backup
    assert "SendSIGKILL=yes" in backup
    assert "Persistent=true" in timer
    assert "03:15:00 America/New_York" in timer
    assert not any("@" in path.read_text() for path in paths)
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in paths)
    with pytest.raises(FileExistsError):
        runtime.render(config, output)
    executable = shutil.which("systemd-analyze")
    if executable is not None:
        # Verification reads files only; it neither installs nor starts the units.
        user_runtime = tmp_path / "user-runtime"
        user_runtime.mkdir(mode=0o700)
        result = subprocess.run(  # noqa: S603 - generated static unit paths
            [executable, "--user", "verify", *map(str, paths)],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"XDG_RUNTIME_DIR": str(user_runtime)},
        )
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("bad", ["mode", "exchange", "symlink", "inside", "origin"])
def test_invalid_configuration_has_zero_render_writes(
    deployment: runtime.Deployment, tmp_path: Path, bad: str
) -> None:
    config = deployment
    if bad == "mode":
        config.provider_env.chmod(0o644)
    elif bad == "exchange":
        config.provider_env.write_text("KALSHI_PRIVATE_KEY_PATH=/secret\n")
    elif bad == "symlink":
        copy = tmp_path / "linked-owner"
        copy.symlink_to(config.owner_file)
        config = replace(config, owner_file=copy)
    elif bad == "inside":
        config = replace(config, config_file=config.checkout / "config.json")
    else:
        config = replace(config, private_origin="https://research.example.ts.net:443")
    output = tmp_path / "must-not-exist"
    with pytest.raises((ValueError, OSError)):
        runtime.render(config, output)
    assert not output.exists()
    assert not (config.checkout / "data").exists()


def stub_runner(
    config: runtime.Deployment,
    calls: list[list[str]],
    *,
    state: str = "active",
    fail: str = "",
) -> runtime.CommandRunner:
    def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[0] == "/usr/bin/git":
            output = config.commit if "rev-parse" in argv else ""
            return subprocess.CompletedProcess(argv, 0, output, "")
        if "-I" in argv:
            return subprocess.CompletedProcess(argv, 0, config.python_version, "")
        if argv[0] == str(config.uv):
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "is-active" in argv:
            code = 0 if state == "active" else 3
            return subprocess.CompletedProcess(argv, code, state, "")
        operation = "backup" if "workspace-backup" in argv else argv[2]
        return subprocess.CompletedProcess(argv, int(operation == fail), "verified receipt", "")

    return run


@pytest.mark.parametrize("state", ["active", "inactive", "failed"])
@pytest.mark.parametrize("failure", ["", "backup", "stop"])
def test_backup_coordinator_restores_only_previously_active_unit(
    deployment: runtime.Deployment,
    state: str,
    failure: str,
) -> None:
    calls: list[list[str]] = []
    runner = stub_runner(deployment, calls, state=state, fail=failure)
    backup_calls: list[Path] = []
    receipt = {"ciphertext_sha256": "c" * 64, "submission_enabled": False}

    def operation(config: runtime.Deployment, output: Path) -> dict[str, Any]:
        assert config == deployment
        assert output.parent == deployment.checkout / "data/backups"
        backup_calls.append(output)
        if state == "active":
            assert calls[-1][2] == "stop"
        if failure == "backup":
            raise ValueError("CONTROLLED backup failure")
        return receipt

    if failure == "backup" or (failure == "stop" and state == "active"):
        with pytest.raises(ValueError, match=r"backup|deployment check failed"):
            runtime.maintenance_backup(deployment, runner, backup_operation=operation)
    else:
        assert runtime.maintenance_backup(deployment, runner, backup_operation=operation) == receipt
    actions = [argv[2] for argv in calls if argv[0] == "/usr/bin/systemctl"]
    assert actions == (["is-active", "stop", "start"] if state == "active" else ["is-active"])
    assert all(
        argv[-1] == runtime.UNIT and argv[1] == "--user"
        for argv in calls
        if argv[0] == "/usr/bin/systemctl"
    )
    assert len(backup_calls) == int(not (failure == "stop" and state == "active"))


@pytest.mark.parametrize("state", ["active", "inactive", "failed"])
def test_backup_interruption_cleans_plaintext_before_restoring_previous_service_state(
    deployment: runtime.Deployment, state: str
) -> None:
    from entropytrade.operations import backup

    calls: list[list[str]] = []
    runner = stub_runner(deployment, calls, state=state)

    def operation(config: runtime.Deployment, _output: Path) -> dict[str, Any]:
        with backup._stage(config.checkout / "data/recovery") as stage:
            (stage / "private-plaintext.zip").write_bytes(b"CONTROLLED archive")
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        runtime.maintenance_backup(deployment, runner, backup_operation=operation)
    actions = [argv[2] for argv in calls if argv[0] == "/usr/bin/systemctl"]
    assert actions == (["is-active", "stop", "start"] if state == "active" else ["is-active"])
    assert not list((deployment.checkout / "data/recovery").glob(".encrypted-*"))


def test_untracked_application_code_refuses_before_maintenance_writes(
    deployment: runtime.Deployment,
) -> None:
    calls: list[list[str]] = []
    original = stub_runner(deployment, calls)

    def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if "ls-files" in argv:
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "backend/src/untracked.py\n", "")
        return original(argv)

    with pytest.raises(ValueError, match="untracked application"):
        runtime.maintenance_backup(deployment, runner)
    assert not (deployment.checkout / "data").exists()
    assert not any(argv[0] == "/usr/bin/systemctl" for argv in calls)


def test_virtualenv_directory_is_private_but_uv_interpreter_symlink_is_supported(
    deployment: runtime.Deployment, tmp_path: Path
) -> None:
    base = tmp_path / "base-python"
    base.write_text("#!/bin/sh\nexit 0\n")
    base.chmod(0o700)
    deployment.python.unlink()
    deployment.python.symlink_to(base)
    deployment.validate()
    shutil.rmtree(deployment.checkout / ".venv")
    other = tmp_path / "shared-environment"
    other.mkdir()
    (deployment.checkout / ".venv").symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        deployment.validate()


def test_backup_refuses_changing_unit_state(deployment: runtime.Deployment) -> None:
    calls: list[list[str]] = []
    with pytest.raises(ValueError, match="unknown or changing"):
        runtime.maintenance_backup(deployment, stub_runner(deployment, calls, state="activating"))
    assert not any(
        "workspace-backup" in argv or "stop" in argv or "start" in argv for argv in calls
    )


def test_pin_failure_precedes_maintenance_writes(deployment: runtime.Deployment) -> None:
    config = replace(deployment, uv_lock_sha256="b" * 64)
    calls: list[list[str]] = []
    with pytest.raises(ValueError, match="lock differs"):
        runtime.maintenance_backup(config, stub_runner(config, calls))
    assert not (config.checkout / "data").exists()
    assert not any(argv[0] == "/usr/bin/systemctl" for argv in calls)


def test_serve_environment_discards_inherited_exchange_keys(
    deployment: runtime.Deployment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KALSHI_KEY_ID", "must-never-be-inherited")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-provider-must-not-be-inherited")
    monkeypatch.setattr(runtime, "verify_pins", lambda config: None)
    captured: dict[str, Any] = {}

    def fake_exec(path: Path, argv: list[str], env: dict[str, str]) -> None:
        captured.update(path=path, argv=argv, env=env)

    monkeypatch.setattr(os, "execve", fake_exec)
    runtime.serve(deployment)
    assert "KALSHI_KEY_ID" not in captured["env"]
    assert "OPENAI_API_KEY" not in captured["env"]
    assert captured["env"]["ENTROPYTRADE_RESEARCH_OPENAI_API_KEY"] == "test-only-key"
    assert captured["env"]["ENTROPYTRADE_TRADING_MODE"] == "read_only"
    assert captured["env"]["ENTROPYTRADE_LIVE_TRADING_ENABLED"] == "false"
    assert captured["argv"][-4:] == [
        "--private-origin",
        deployment.private_origin,
        "--tailscale-owner",
        deployment.tailscale_owner,
    ]
    port = captured["argv"].index("--port")
    assert captured["argv"][port + 1] == str(runtime.RESEARCH_PORT) == "43138"


def test_research_port_differs_from_collector_window_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A collection window's own workbench must never collide with the research service."""
    from entropytrade.operations import forward

    parsers: list[argparse.ArgumentParser] = []

    def capture(self: argparse.ArgumentParser, *args: object, **kwargs: object) -> None:
        parsers.append(self)
        raise SystemExit(0)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    with pytest.raises(SystemExit):
        forward.main()
    collector_port = parsers[0].get_default("port")
    assert collector_port == 43128
    assert collector_port != runtime.RESEARCH_PORT
