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
import socket
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_BROWSER_GREP = (
    "local operation and recovery|provider-backed website|authentic retained weather|"
    "durable paper account|operator alerts"
)
REQUIRED_BROWSER_PROCEDURES = (
    (
        "recovery.spec.cjs",
        "local operation and recovery: installed research, snapshot, restore and shadow lifecycle",
    ),
    (
        "provider.spec.cjs",
        "provider-backed website: opt-in, typed candidates, failures, cancellation and recovery",
    ),
    (
        "weather-history.spec.cjs",
        "authentic retained weather: freeze, select, research, downloads and restart",
    ),
    (
        "paper.spec.cjs",
        "durable paper account: CONTROLLED synthetic fills, downloads, restart and offline replay",
    ),
    (
        "paper.spec.cjs",
        "durable paper account: authentic refusal, downloads, restart and offline replay",
    ),
    (
        "alerts.spec.cjs",
        "operator alerts: acknowledgement, listener restart, recovery, recurrence "
        "and offline restore",
    ),
)


def inspect_browser_report(path, *, execution, expected=None, require_all=False):
    """Validate JSON reporter evidence; --list's skipped/empty results prove discovery only."""
    result = {
        "report": str(path),
        "execution": execution,
        "status": "failed",
        "procedures": [],
        "missing_required": [],
        "errors": [],
    }
    errors = result["errors"]
    procedures = set()
    test_count = 0

    def walk(suites):
        nonlocal test_count
        if not isinstance(suites, list):
            raise ValueError("suites must be a list")
        for suite in suites:
            for spec in suite.get("specs", []):
                identity = (spec["file"], spec["title"])
                if not all(isinstance(part, str) and part for part in identity):
                    raise ValueError("procedure file/title must be nonempty strings")
                if identity in procedures:
                    errors.append(f"Duplicate procedure: {identity}")
                procedures.add(identity)
                tests = spec["tests"]
                if not isinstance(tests, list) or not tests:
                    raise ValueError(f"No test records for {identity}")
                for test in tests:
                    test_count += 1
                    if test.get("expectedStatus") != "passed":
                        errors.append(f"Procedure is skipped or expects failure: {identity}")
                    if execution:
                        attempts = test.get("results")
                        if (
                            spec.get("ok") is not True
                            or test.get("status") != "expected"
                            or not isinstance(attempts, list)
                            or not attempts
                            or any(
                                attempt.get("status") != "passed"
                                or attempt.get("error")
                                or attempt.get("errors")
                                for attempt in attempts
                            )
                        ):
                            errors.append(f"Missing or unsuccessful execution results: {identity}")
            walk(suite.get("suites", []))

    try:
        raw = path.read_bytes()
        result["sha256"] = hashlib.sha256(raw).hexdigest()
        report = json.loads(raw)
        if report["errors"] != []:
            errors.append("Playwright reported global errors")
        walk(report["suites"])
        if not procedures:
            errors.append("No browser procedures discovered")
        stats = report["stats"]
        expected_stats = {
            "expected": test_count if execution else 0,
            "skipped": 0 if execution else test_count,
            "unexpected": 0,
            "flaky": 0,
        }
        if any(stats.get(key) != value for key, value in expected_stats.items()):
            errors.append("Playwright statistics are incomplete or inconsistent with test records")
        if expected is not None and procedures != set(expected):
            errors.append(
                f"Execution/discovery mismatch: missing={sorted(set(expected) - procedures)}, "
                f"unexpected={sorted(procedures - set(expected))}"
            )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(f"Unreadable or malformed Playwright report: {exc}")
    result["procedures"] = [{"file": file, "title": title} for file, title in sorted(procedures)]
    result["missing_required"] = [
        {"file": file, "title": title}
        for file, title in sorted(set(REQUIRED_BROWSER_PROCEDURES) - procedures)
    ]
    if require_all and result["missing_required"]:
        errors.append("Required browser procedures missing from discovery")
    result["status"] = "failed" if errors else "passed"
    return result


def now():
    return datetime.now(UTC).isoformat()


def check_environment(port):
    """Check required OS capabilities without launching Chromium or changing permissions."""
    checks = []
    for name in ("localhost_listener", "asyncio_socketpair"):
        operation = "socket creation"
        try:
            if name == "localhost_listener":
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                    operation = "localhost bind"
                    listener.bind(("127.0.0.1", port))
                    operation = "listen"
                    listener.listen(1)
            else:
                left, right = socket.socketpair()
                with left, right:
                    operation = "socketpair send"
                    left.sendall(b"x")
                    operation = "socketpair receive"
                    if right.recv(1) != b"x":
                        raise OSError("socketpair did not reproduce its wakeup byte")
        except OSError as exc:
            checks.append(
                {
                    "name": name,
                    "status": "blocked",
                    "operation": operation,
                    "failure": repr(exc),
                    "errno": exc.errno,
                }
            )
        else:
            checks.append({"name": name, "status": "passed"})
    return {
        "checked_at": now(),
        "status": "passed" if all(c["status"] == "passed" for c in checks) else "blocked",
        "checks": checks,
        "limitation": "Socket capability only; browser workflows and pytest remain unverified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--port", default=43134, type=int)
    parser.add_argument(
        "--check-environment",
        action="store_true",
        help="Report socket capabilities only; no browser launch or test execution",
    )
    parser.add_argument("--uv-cache-seed", type=Path)
    parser.add_argument("--npm-cache-seed", type=Path)
    parser.add_argument("--chromium-seed", type=Path)
    parser.add_argument("--test-seconds", default=600, type=int)
    parser.add_argument(
        "--browser-grep",
        default=DEFAULT_BROWSER_GREP,
        help="Narrow browser execution; partial coverage can never complete acceptance",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Provision only; browser and full suite remain unverified",
    )
    args = parser.parse_args()
    if args.check_environment:
        result = check_environment(args.port)
        print(json.dumps(result, indent=2))  # noqa: T201 - machine-readable local CLI
        raise SystemExit(0 if result["status"] == "passed" else 1)
    if args.output is None:
        parser.error("--output is required unless --check-environment is selected")
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
        "browser_selection": args.browser_grep,
        "browser_reports": {},
        "required_browser_procedures": [
            {"file": file, "title": title} for file, title in REQUIRED_BROWSER_PROCEDURES
        ],
        "acceptance_complete": False,
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
        "docs/research",
        "data/public",
        "data/r1-demo",
        "data/r1-source",
        "data/r2-demo",
        "data/r3-demo",
        "data/r4-demo",
    ]
    # Exact original cycles used by weather history, paper and alert acceptance.
    # Keep saved decisions/results alongside public captures for original-cycle replay;
    # omit the surrounding operating evidence and workspaces.
    weather_receipts = repo / "data/shadow-review/20261029-model-integration/completion/real-cycles"
    roots.extend(
        str(p.parent.relative_to(repo)) for p in sorted(weather_receipts.glob("*/*/public"))
    )
    names = [
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "Makefile",
        ".gitignore",
        "THIRD_PARTY_NOTICES.md",
        "docs/project-spec.md",
        ".agents/skills/kalshi-docs/api-reference/market/get-series.md",
        ".agents/skills/kalshi-docs/getting_started/fee_rounding.md",
        # Original v1 account bytes used by the unchanged compatibility regression.
        "data/paper-accounting-review/20261031/final/controlled-export.json",
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
    # Chromium uses Unix sockets below TMPDIR. Deep evidence paths can exceed the
    # platform's 108-byte socket-address limit and crash before any page opens.
    acceptance_temp = tempfile.TemporaryDirectory(prefix="entropytrade-", dir="/tmp")
    receipt["temporary_directory"] = acceptance_temp.name
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
        "TMPDIR": acceptance_temp.name,
    }
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
    browser_command = [
        node,
        "frontend/browser/node_modules/@playwright/test/cli.js",
        "test",
        "-c",
        "frontend/browser/playwright.config.cjs",
    ]
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
            "browser-discovery",
            [*browser_command, "--grep", DEFAULT_BROWSER_GREP, "--list"],
            {
                **browser_env,
                "ENTROPYTRADE_BROWSER_EVIDENCE": str(output / "browser-discovery"),
            },
            60,
        ),
        (
            "browser-selection",
            [*browser_command, "--grep", args.browser_grep, "--list"],
            {
                **browser_env,
                "ENTROPYTRADE_BROWSER_EVIDENCE": str(output / "browser-selection"),
            },
            60,
        ),
        (
            "environment",
            [python, "tools/local_acceptance.py", "--check-environment", "--port", str(args.port)],
            env,
            15,
        ),
        (
            "browser",
            [*browser_command, "--grep", args.browser_grep, "--max-failures=1"],
            browser_env,
            660,
        ),
        (
            "pytest",
            [
                str(clean / ".venv/bin/pytest"),
                "-v",
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
        receipt["unexecuted_checks"] = ["environment", "browser", "pytest"]
        steps = [s for s in steps if s[0] not in receipt["unexecuted_checks"]]
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
            if name in {"browser-discovery", "browser-selection", "browser"}:
                expected = None
                if name == "browser":
                    expected = [
                        (p["file"], p["title"])
                        for p in receipt["browser_reports"]["browser-selection"]["procedures"]
                    ]
                report_directory = "browser" if name == "browser" else name
                result = inspect_browser_report(
                    output / report_directory / "playwright-results.json",
                    execution=name == "browser",
                    expected=expected,
                    require_all=name == "browser-discovery"
                    or (name == "browser-selection" and args.browser_grep == DEFAULT_BROWSER_GREP),
                )
                step["result"] = result
                receipt["browser_reports"][name] = result
                if result["status"] != "passed":
                    step.update(status="failed", failure="; ".join(result["errors"]))
            if name == "environment" and code != 124:
                step["result"] = json.loads((output / "environment.log").read_text())
                if code != 0 and step["result"]["status"] == "blocked":
                    step["status"] = "blocked"
                    receipt.update(
                        status="blocked",
                        unexecuted_checks=["browser", "pytest"],
                        failure="OS socket capabilities denied; no browser or suite retry.",
                    )
                    raise RuntimeError(receipt["failure"])
            save()
            print(f"{name}: {step['status']}", flush=True)  # noqa: T201 - local CLI progress
            if step["status"] != "passed" and name in {
                "lock-check",
                "locked-sync",
                "npm-ci",
                "chromium-install",
                "browser-discovery",
                "browser-selection",
                "environment",
            }:
                raise RuntimeError(f"{name} failed; inspect {output / (name + '.log')}")
        receipt["status"] = (
            "passed" if all(s["status"] == "passed" for s in receipt["steps"]) else "failed"
        )
        if receipt["status"] != "passed":
            raise RuntimeError("Acceptance incomplete: inspect failed step logs; no release pass")
        if args.prepare_only:
            receipt["status"] = "prepared; browser and full suite unverified"
        elif receipt["browser_reports"]["browser"]["missing_required"]:
            receipt.update(
                status="partial; required browser procedures unexecuted",
                unexecuted_browser_procedures=receipt["browser_reports"]["browser"][
                    "missing_required"
                ],
            )
        else:
            receipt["acceptance_complete"] = True
    except Exception as exc:
        if receipt["status"] != "blocked":
            receipt.update(status="failed", failure=str(exc))
        if receipt["steps"][-1]["status"] == "running":
            receipt["steps"][-1].update(status="failed", failure=str(exc), finished_at=now())
        raise
    finally:
        receipt["unexecuted_checks"] = sorted(
            set(receipt.get("unexecuted_checks", []))
            | {name for name, *_ in steps if name not in {s["name"] for s in receipt["steps"]}}
        )
        receipt["finished_at"] = now()
        save()
        acceptance_temp.cleanup()


if __name__ == "__main__":
    main()
