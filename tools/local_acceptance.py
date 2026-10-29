"""Reproduce locked local installation, complete gates and actual Chromium recovery checks.

Run with standard-library Python: python3 tools/local_acceptance.py --output data/local-review/NAME
The output must be new. No Git operations, credentials, personal browser or source rewrites.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def now():
    return datetime.now(UTC).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", default=43134, type=int)
    parser.add_argument("--uv-cache-seed", type=Path)
    parser.add_argument("--npm-cache-seed", type=Path)
    parser.add_argument("--chromium-seed", type=Path)
    parser.add_argument("--test-seconds", default=600, type=int)
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Provision only; browser and full suite remain unverified",
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = args.output.absolute()
    if not output.is_relative_to(repo / "data") or ".." in output.parts:
        parser.error("output must be a new directory under repository data/")
    output.mkdir(parents=True, exist_ok=False)
    clean = output / "installation"
    clean.mkdir()
    receipt = {
        "started_at": now(),
        "status": "running",
        "source": str(repo),
        "installation": str(clean),
        "steps": [],
        "source_files": [],
        "limitations": [
            "Source export of the working tree; supervisor owns Git sign-off.",
            "No empirical performance, provider or V1 completion implied.",
        ],
    }

    def save():
        (output / "acceptance.json").write_text(json.dumps(receipt, indent=2) + "\n")

    # Explicit product/test/data roots exclude supervisor controls, credentials, old
    # evidence/workspaces, environments, caches and browser installations.
    roots = [
        "backend",
        "frontend/src",
        "frontend/tests",
        "frontend/browser",
        "configs",
        "tools",
        "vendor",
        "data/r1-demo",
        "data/r1-source",
        "data/r2-demo",
        "data/r3-demo",
        "data/r4-demo",
    ]
    names = [
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "Makefile",
        ".gitignore",
        "THIRD_PARTY_NOTICES.md",
    ]
    for directory in roots:
        names.extend(
            str(p.relative_to(repo))
            for p in (repo / directory).rglob("*")
            if p.is_file()
            and not any(
                part
                in {
                    "node_modules",
                    ".browsers",
                    "__pycache__",
                    ".pytest_cache",
                    ".ruff_cache",
                    ".mypy_cache",
                }
                for part in p.relative_to(repo).parts
            )
        )
    for name in sorted(names):
        source = repo / name
        if source.is_symlink() or source.suffix in {".key", ".pem"} or source.name == ".env":
            raise ValueError("unsafe source export member: " + name)
        target = clean / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        receipt["source_files"].append(
            {
                "path": name,
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    # Clean environment: no inherited provider/exchange credentials, HOME or Python path.
    env = {
        "PATH": os.defpath,
        "TZ": "UTC",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_CACHE_DIR": str(output / "uv-cache"),
        "npm_config_cache": str(output / "npm-cache"),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "LOKY_MAX_CPU_COUNT": "1",
        "TMPDIR": str(output / "tmp"),
    }
    Path(env["TMPDIR"]).mkdir()
    receipt["provisioning"] = {
        "uv_cache_seed": str(args.uv_cache_seed) if args.uv_cache_seed else None,
        "npm_cache_seed": str(args.npm_cache_seed) if args.npm_cache_seed else None,
        "chromium_seed": str(args.chromium_seed) if args.chromium_seed else None,
        "reused_virtualenv": False,
    }
    save()
    # Only package artifacts are copied. Never copy config/auth files or an environment.
    if args.uv_cache_seed:
        seed = args.uv_cache_seed.resolve()
        cache = Path(env["UV_CACHE_DIR"])
        cache.mkdir()
        for name in ("archive-v0", "sdists-v10", "wheels-v7", "CACHEDIR.TAG"):
            source = seed / name
            if source.is_dir():
                shutil.copytree(source, cache / name, symlinks=True)
            elif source.is_file():
                shutil.copyfile(source, cache / name)
        for link in cache.rglob("*"):
            if link.is_symlink():
                target = link.resolve()
                if target.is_relative_to(cache):
                    continue
                if not target.is_relative_to(seed):
                    raise ValueError("package cache link escapes artifact cache")
                link.unlink()
                link.symlink_to(
                    cache / target.relative_to(seed), target_is_directory=target.is_dir()
                )
    if args.npm_cache_seed:
        shutil.copytree(
            args.npm_cache_seed / "_cacache", Path(env["npm_config_cache"]) / "_cacache"
        )
    if args.chromium_seed:
        shutil.copytree(args.chromium_seed, clean / "frontend/browser/.browsers")
    python = str(clean / ".venv/bin/python")
    uv = shutil.which("uv")
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not all((uv, npm, node)):
        raise RuntimeError("uv, npm and node must be installed")
    browser_env = {
        **env,
        "PLAYWRIGHT_BROWSERS_PATH": str(clean / "frontend/browser/.browsers"),
        "ENTROPYTRADE_BROWSER_EVIDENCE": str(output / "browser"),
        "ENTROPYTRADE_BROWSER_WORKSPACE": str(clean / "data/cache/acceptance"),
        "ENTROPYTRADE_BROWSER_PYTHON": python,
        "ENTROPYTRADE_BROWSER_PORT": str(args.port),
    }
    steps = [
        (
            "lock-check",
            [uv, "lock", "--check", *(["--offline"] if args.uv_cache_seed else [])],
            env,
            180,
        ),
        (
            "locked-sync",
            [
                uv,
                "sync",
                "--locked",
                "--python",
                sys.executable,
                *(["--offline"] if args.uv_cache_seed else []),
            ],
            env,
            600,
        ),
        (
            "installed-packages",
            [uv, "pip", "list", "--python", python, "--format", "json"],
            env,
            60,
        ),
        (
            "ruff",
            [str(clean / ".venv/bin/ruff"), "check", "--no-respect-gitignore", "backend"],
            env,
            60,
        ),
        (
            "format",
            [
                str(clean / ".venv/bin/ruff"),
                "format",
                "--check",
                "--no-respect-gitignore",
                "backend",
            ],
            env,
            60,
        ),
        ("mypy", [str(clean / ".venv/bin/mypy")], env, 180),
        ("frontend", [node, "frontend/tests/acquisition.test.cjs"], env, 60),
        (
            "npm-ci",
            [
                npm,
                "ci",
                "--prefix",
                "frontend/browser",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                *(["--offline"] if args.npm_cache_seed else []),
            ],
            env,
            180,
        ),
        (
            "chromium-install",
            [npm, "--prefix", "frontend/browser", "run", "install:chromium"],
            browser_env,
            300,
        ),
        (
            "browser",
            [
                node,
                "frontend/browser/node_modules/@playwright/test/cli.js",
                "test",
                "-c",
                "frontend/browser/playwright.config.cjs",
                "--grep",
                "local operation and recovery",
            ],
            browser_env,
            660,
        ),
        (
            "pytest",
            [
                str(clean / ".venv/bin/pytest"),
                "-q",
                "-o",
                "faulthandler_timeout=45",
                "--junitxml=" + str(output / "pytest.xml"),
            ],
            env,
            args.test_seconds,
        ),
    ]
    save()
    if args.prepare_only:
        steps = [s for s in steps if s[0] not in {"browser", "pytest"}]
        receipt["unexecuted_checks"] = ["browser", "pytest"]
    try:
        for name, command, environment, timeout in steps:
            step = {"name": name, "command": command, "started_at": now(), "status": "running"}
            receipt["steps"].append(step)
            save()
            print(f"{name}: started", flush=True)  # noqa: T201 - local CLI progress
            with (
                (output / (name + ".log")).open("w") as log,
                subprocess.Popen(  # noqa: S603 - fixed tool commands, no shell
                    command,
                    cwd=clean,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                ) as process,
            ):
                try:
                    code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    code = 124
                    step["failure"] = f"External deadline {timeout}s; incomplete, never a pass"
            step.update(
                finished_at=now(), exit_code=code, status="passed" if code == 0 else "failed"
            )
            save()
            print(f"{name}: {step['status']}", flush=True)  # noqa: T201 - local CLI progress
            if code != 0 and name in {"lock-check", "locked-sync", "npm-ci", "chromium-install"}:
                raise RuntimeError(f"{name} failed; inspect {output / (name + '.log')}")
        receipt["status"] = (
            "passed" if all(s["status"] == "passed" for s in receipt["steps"]) else "failed"
        )
        if receipt["status"] != "passed":
            raise RuntimeError("Acceptance incomplete: inspect failed step logs; no release pass")
        if args.prepare_only:
            receipt["status"] = "prepared; browser and full suite unverified"
    except Exception as exc:
        receipt.update(status="failed", failure=str(exc))
        if receipt["steps"][-1]["status"] == "running":
            receipt["steps"][-1].update(status="failed", failure=str(exc), finished_at=now())
        raise
    finally:
        receipt["finished_at"] = now()
        save()


if __name__ == "__main__":
    main()
