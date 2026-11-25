"""Fail-closed research-only deployment rendering and user-service maintenance.

Nothing here installs a service, changes WSL, configures Tailscale or accesses a collector.
The layout guard is deliberately pure and is also used before private API startup.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import pwd
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from entropytrade.api.owner import OwnerAuth
from entropytrade.api.workspace import workspace_path
from entropytrade.research.store import reject_collector_chain

UNIT = "entropytrade-research.service"
# Each canonical forward-collection window starts its own bounded workbench on the server
# default 127.0.0.1:43128 (operations.forward). The long-running research service therefore
# listens on a distinct loopback port so both can run on the same host without one refusing
# to start or the collector's client reaching the private research API.
RESEARCH_PORT = 43138
PROVIDER_KEYS = frozenset(
    {
        "GEMINI_API_KEY",
        "ENTROPYTRADE_RESEARCH_ANTHROPIC_API_KEY",
        "ENTROPYTRADE_RESEARCH_OPENAI_API_KEY",
        "ENTROPYTRADE_RESEARCH_API_KEY",
        "ENTROPYTRADE_LOCAL_LLM_URL",
        "ENTROPYTRADE_LOCAL_LLM_KEY",
    }
)
CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _absolute(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("deployment paths must be absolute without parent traversal")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("deployment paths cannot traverse symlinks")
    return path


def _overlap(left: Path, right: Path) -> bool:
    return left.is_relative_to(right) or right.is_relative_to(left)


def validate_research_layout(
    checkout: Path, workspace: Path, collector_checkout: Path | None = None
) -> None:
    """Reject canonical/collector paths before creating a directory or opening a lock."""
    checkout, workspace = _absolute(checkout), _absolute(workspace)
    collector = _absolute(collector_checkout or Path.home() / "Projects/EntropyTrade-collector")
    for path in (checkout, workspace):
        if any(part.name.casefold() == "entropytrade-collector" for part in (path, *path.parents)):
            raise ValueError("research cannot use the collector checkout")
        if _overlap(path, collector):
            raise ValueError("research and collector paths overlap")
        reject_collector_chain(path)
    if workspace_path(checkout, workspace) != workspace:
        raise ValueError("research workspace must be inside the separate checkout data/cache")


def _private_file(path: Path, checkout: Path, *, limit: int = 65536) -> bytes:
    _absolute(path)
    if _overlap(path, checkout):
        raise ValueError("deployment credentials/configuration must be outside the checkout")
    directory = path.parent.stat()
    if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) != 0o700:
        raise ValueError("private configuration directory must be owned by this user and 0700")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > limit
        ):
            raise ValueError("private configuration files must be owned by this user and 0600")
        return source.read(limit + 1)


def provider_environment(path: Path, checkout: Path) -> dict[str, str]:
    """Read only explicit research variables; never import an ambient exchange credential."""
    values: dict[str, str] = {}
    for line in _private_file(path, checkout).decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if (
            not separator
            or name not in PROVIDER_KEYS
            or name in values
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise ValueError("provider environment permits only distinct research KEY=value lines")
        values[name] = value
    return values


@dataclass(frozen=True)
class Deployment:
    config_file: Path
    checkout: Path
    collector_checkout: Path
    owner_file: Path
    provider_env: Path
    recipient_file: Path
    recipient_fingerprint: str
    private_origin: str
    tailscale_owner: str
    commit: str
    uv_lock_sha256: str
    uv: Path
    python_version: str

    @property
    def workspace(self) -> Path:
        return self.checkout / "data/cache/research"

    @property
    def python(self) -> Path:
        return self.checkout / ".venv/bin/python"

    @classmethod
    def load(cls, path: Path) -> Deployment:
        # The outer file is checked before interpreting any caller-controlled layout.
        _absolute(path)
        raw = _private_file(path, Path("/__entropytrade_configuration_placeholder__"))
        value = json.loads(raw)
        fields = set(cls.__dataclass_fields__) - {"config_file"}
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("deployment configuration fields differ from the documented schema")
        if any(not isinstance(item, str) or not item for item in value.values()):
            raise ValueError("deployment configuration values must be nonempty strings")
        config = cls(
            config_file=path,
            checkout=Path(value["checkout"]),
            collector_checkout=Path(value["collector_checkout"]),
            owner_file=Path(value["owner_file"]),
            provider_env=Path(value["provider_env"]),
            recipient_file=Path(value["recipient_file"]),
            recipient_fingerprint=value["recipient_fingerprint"],
            private_origin=value["private_origin"],
            tailscale_owner=value["tailscale_owner"],
            commit=value["commit"],
            uv_lock_sha256=value["uv_lock_sha256"],
            uv=Path(value["uv"]),
            python_version=value["python_version"],
        )
        config.validate()
        return config

    def validate(self) -> None:
        validate_research_layout(self.checkout, self.workspace, self.collector_checkout)
        # uv's interpreter leaf is normally a symlink; its environment directories must
        # still belong to this checkout rather than a shared collector environment.
        _absolute(self.checkout / ".venv")
        _absolute(self.checkout / ".venv/bin")
        _absolute(self.checkout / ".venv/pyvenv.cfg")
        if self.checkout.name != "EntropyTrade-research" or not self.checkout.is_dir():
            raise ValueError("deployment needs a separate existing EntropyTrade-research checkout")
        if self.collector_checkout.name != "EntropyTrade-collector":
            raise ValueError(
                "collector exclusion must name the entire EntropyTrade-collector checkout"
            )
        for path in (self.config_file, self.owner_file, self.provider_env, self.recipient_file):
            _private_file(path, self.checkout)
            if _overlap(path, self.collector_checkout):
                raise ValueError("deployment configuration cannot be inside the collector")
        if len({self.config_file, self.owner_file, self.provider_env, self.recipient_file}) != 4:
            raise ValueError(
                "deployment configuration, owner, provider and public key files must differ"
            )
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError("pin the complete checkout commit")
        if not re.fullmatch(r"[0-9a-f]{64}", self.uv_lock_sha256):
            raise ValueError("pin the uv.lock SHA-256")
        if not re.fullmatch(r"(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})", self.recipient_fingerprint):
            raise ValueError("pin a full primary recipient fingerprint")
        if not re.fullmatch(r"3\.(?:1[2-9]|[2-9][0-9])\.[0-9]+", self.python_version):
            raise ValueError("pin an exact supported Python version")
        _absolute(self.uv)
        if not self.uv.is_file() or not os.access(self.uv, os.X_OK):
            raise ValueError("pin an existing absolute uv executable")
        # Import lazily: the pure layout guard has no API-server import dependency.
        from entropytrade.api.private_access import PrivateAccess

        PrivateAccess.configure(self.private_origin, self.tailscale_owner, self.owner_file)
        OwnerAuth(self.checkout, self.owner_file)
        provider_environment(self.provider_env, self.checkout)


def command_environment() -> dict[str, str]:
    account = pwd.getpwuid(os.getuid())
    runtime = f"/run/user/{os.getuid()}"
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": account.pw_dir,
        "LANG": "C.UTF-8",
        "XDG_RUNTIME_DIR": runtime,
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "UV_NO_CACHE": "1",
        "UV_OFFLINE": "1",
        "UV_PYTHON_DOWNLOADS": "never",
    }


def run_command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argv is fixed, never a shell
        argv, capture_output=True, text=True, timeout=600, check=False, env=command_environment()
    )


def _checked(argv: list[str], runner: CommandRunner = run_command) -> str:
    result = runner(argv)
    if result.returncode:
        raise ValueError(f"deployment check failed: {Path(argv[0]).name} {argv[1]}")
    return result.stdout.strip()


def verify_pins(config: Deployment, runner: CommandRunner = run_command) -> None:
    if (
        _checked(["/usr/bin/git", "-C", str(config.checkout), "rev-parse", "HEAD"], runner)
        != config.commit
    ):
        raise ValueError("checkout differs from pinned commit")
    _checked(["/usr/bin/git", "-C", str(config.checkout), "diff", "--quiet", "HEAD", "--"], runner)
    untracked = _checked(
        [
            "/usr/bin/git",
            "-C",
            str(config.checkout),
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "backend/src",
            "frontend/src",
            "configs",
            "deploy",
        ],
        runner,
    )
    if untracked:
        raise ValueError("checkout contains untracked application or deployment source")
    lock = config.checkout / "uv.lock"
    _absolute(lock)
    if hashlib.sha256(lock.read_bytes()).hexdigest() != config.uv_lock_sha256:
        raise ValueError("dependency lock differs from pinned SHA-256")
    version = _checked(
        [str(config.python), "-I", "-c", "import platform; print(platform.python_version())"],
        runner,
    )
    if version != config.python_version:
        raise ValueError("virtual environment Python differs from pinned version")
    _checked(
        [
            str(config.uv),
            "sync",
            "--frozen",
            "--no-dev",
            "--check",
            "--project",
            str(config.checkout),
        ],
        runner,
    )


def doctor(config: Deployment, runner: CommandRunner = run_command) -> dict[str, Any]:
    """Read-only preflight. Physical Windows/Tailscale/offsite tests remain explicit gates."""
    config.validate()
    if os.getuid() == 0:
        raise ValueError("research services must run as the ordinary research user")
    if (
        "microsoft" not in platform.release().lower()
        or Path("/proc/1/comm").read_text().strip() != "systemd"
    ):
        raise ValueError(
            "physical WSL2 with systemd PID 1 is required; no global WSL changes are made"
        )
    verify_pins(config, runner)
    version = _checked(["/usr/bin/systemctl", "--version"], runner)
    if not re.match(r"systemd (?:249|2[5-9][0-9]|[3-9][0-9]{2})\b", version):
        raise ValueError("systemd 249 or newer is required")
    _checked(["/usr/bin/systemctl", "--user", "show-environment"], runner)
    linger = _checked(
        ["/usr/bin/loginctl", "show-user", str(os.getuid()), "--property=Linger", "--value"], runner
    )
    if linger != "yes":
        raise ValueError("physical setup must enable linger for this research user only")
    _checked(["/usr/bin/unshare", "--user", "--map-root-user", "--mount", "/usr/bin/true"], runner)
    if runner(["/usr/bin/pgrep", "-x", "tailscaled"]).returncode != 1:
        raise ValueError("WSL tailscaled must be absent; use the Windows Tailscale client only")
    from entropytrade.operations.backup import preflight_gpg

    gpg = preflight_gpg()
    size = 0
    if config.workspace.exists():
        for directory, dirs, files in os.walk(config.workspace, followlinks=False):
            for name in (*dirs, *files):
                member = Path(directory) / name
                info = member.lstat()
                if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    raise ValueError("research workspace contains a symlink or special file")
                if stat.S_ISREG(info.st_mode):
                    size += info.st_size
    needed = max(1 << 30, size * 5 + (128 << 20))
    available = shutil.disk_usage(config.checkout).free
    if available < needed:
        raise ValueError("insufficient free space for snapshot/encryption/restore staging")
    memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    if memory < 2 << 30 or (os.cpu_count() or 0) < 2:
        raise ValueError("research deployment needs at least 2 GiB RAM and two logical CPUs")
    return {
        "schema": "entropytrade-research-doctor-v1",
        "local_checks": "passed",
        "python": config.python_version,
        "gpg": gpg,
        "free_bytes": available,
        "preliminary_required_bytes": needed,
        "workspace_bytes": size,
        "memory_bytes": memory,
        "physical_acceptance": (
            "pending: Windows Serve, localhost, ACL, phone, Mac, reboot, offsite drill"
        ),
    }


def _unit_quote(path: str | Path, *, command_argument: bool = False) -> str:
    text = str(path)
    if any(char in text for char in ("\n", "\r", "\x00")):
        raise ValueError("invalid systemd argument")
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    if command_argument:
        escaped = escaped.replace("$", "$$")
    return '"' + escaped + '"'


def _working_directory(path: Path) -> str:
    # WorkingDirectory is one path, not an ExecStart-style word list. Quoting it
    # leaves a literal leading quote and systemd rejects it as non-absolute.
    text = str(path)
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError("invalid systemd working directory")
    return text.replace("%", "%%")


def render(config: Deployment, output: Path) -> list[Path]:
    config.validate()  # all collector and credential checks precede mkdir
    _absolute(output)
    if _overlap(output, config.checkout) or _overlap(output, config.collector_checkout):
        raise ValueError("render outside research and collector checkouts")
    templates = config.checkout / "deploy/research"
    replacements = {
        "@CHECKOUT@": _working_directory(config.checkout),
        "@PYTHON@": _unit_quote(config.python, command_argument=True),
        "@CONFIG@": _unit_quote(config.config_file, command_argument=True),
        "@WORKSPACE@": _unit_quote(config.workspace),
        "@BACKUPS@": _unit_quote(config.checkout / "data/backups"),
        "@RECOVERY@": _unit_quote(config.checkout / "data/recovery"),
        "@COLLECTOR@": _unit_quote("-" + str(config.collector_checkout)),
        "@UID@": str(os.getuid()),
    }
    rendered: dict[str, str] = {}
    for name in (
        UNIT,
        "entropytrade-research-backup.service",
        "entropytrade-research-backup.timer",
    ):
        template = templates / (name + ".in")
        _absolute(template)
        text = template.read_text()
        for key, value in replacements.items():
            text = text.replace(key, value)
        if re.search(r"@[A-Z_]+@", text):
            raise ValueError("unresolved deployment template value")
        rendered[name] = text
    output.mkdir(mode=0o700)  # new directory only; no overwrite or service installation
    for name, text in rendered.items():
        target = output / name
        with target.open("x", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(text)
    return [output / name for name in rendered]


BackupOperation = Callable[[Deployment, Path], dict[str, Any]]


def _workspace_backup(config: Deployment, output: Path) -> dict[str, Any]:
    from entropytrade.operations.backup import workspace_backup

    return workspace_backup(
        config.checkout,
        config.workspace,
        output,
        config.recipient_file,
        config.recipient_fingerprint,
    )


def maintenance_backup(
    config: Deployment,
    runner: CommandRunner = run_command,
    *,
    backup_operation: BackupOperation | None = None,
) -> dict[str, Any]:
    """Stop/restart only the fixed user research unit; snapshot itself owns the writer lease."""
    config.validate()
    verify_pins(config, runner)
    directory = config.checkout / "data/recovery"
    _absolute(directory)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    lock_path = directory / ".research-maintenance.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "w") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError("maintenance lock must be a regular file")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = runner(["/usr/bin/systemctl", "--user", "is-active", UNIT])
        state = status.stdout.strip()
        if (status.returncode, state) not in {(0, "active"), (3, "inactive"), (3, "failed")}:
            raise ValueError("research unit state is unknown or changing; maintenance refused")
        active = state == "active"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        output = config.checkout / "data/backups" / f"research-{timestamp}.gpg"
        try:
            if active:
                _checked(["/usr/bin/systemctl", "--user", "stop", UNIT], runner)
            # Keep crypto/staging/lease context managers in this process. A killed
            # backup child could otherwise leave private plaintext and an orphan GPG
            # process behind before the coordinator restarts the server.
            operation = backup_operation or _workspace_backup
            return operation(config, output)
        finally:
            if active:
                _checked(["/usr/bin/systemctl", "--user", "start", UNIT], runner)


def serve(config: Deployment) -> None:
    config.validate()
    verify_pins(config)
    env = command_environment() | provider_environment(config.provider_env, config.checkout)
    env.update(
        {"ENTROPYTRADE_TRADING_MODE": "read_only", "ENTROPYTRADE_LIVE_TRADING_ENABLED": "false"}
    )
    argv = [
        str(config.python),
        "-m",
        "entropytrade.api.server",
        "--port",
        str(RESEARCH_PORT),
        "--workspace",
        str(config.workspace),
        "--owner-file",
        str(config.owner_file),
        "--private-origin",
        config.private_origin,
        "--tailscale-owner",
        config.tailscale_owner,
    ]
    os.execve(config.python, argv, env)  # noqa: S606 - fixed interpreter, isolated environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "render", "serve", "backup"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "render":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = Deployment.load(args.config)
        if args.command == "doctor":
            result: Any = doctor(config)
        elif args.command == "render":
            result = {"rendered": [str(path) for path in render(config, args.output)]}
        elif args.command == "backup":
            result = {"backup_receipt": maintenance_backup(config)}
        else:
            serve(config)
            return
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Research deployment refused: {exc}\n")
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
