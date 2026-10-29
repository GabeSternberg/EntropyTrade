"""Isolated recovery gate, including actual listeners/workers; no browser or full-suite retry.

python3 tools/recovery_gate.py --output data/local-operation-review/NEW-NAME
Each pytest file has its own process/deadline. A failure or timeout is never a pass.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path

TESTS = [
    "unit/test_workspace_recovery.py",
    "unit/test_recovery_proof.py",
    "unit/test_tracking.py",
    "unit/test_tracking_models.py",
    "unit/test_workbench_http.py",
    "integration/test_shadow_tracking.py",
    "unit/test_experiments_r4.py",
    "unit/test_execution_r4.py",
    "unit/test_submit_gate.py",
    "integration/test_workbench_process.py",
    "integration/test_workbench_listener.py",
    "integration/test_bitcoin_history_listener.py",
    "integration/test_recovery_listener.py",
]
DESELECTED = [
    "test_real_workflow_has_only_insufficient_or_unsupported_results",
    "test_synthetic_end_to_end_has_models_fills_rejections_and_artifacts",
    "test_same_research_replays_reproducibly",
]


def now():
    return datetime.now(UTC).isoformat()


def sources(repo):
    names = {"pyproject.toml", "uv.lock", "Makefile"}
    for directory in (
        "backend",
        "frontend",
        "tools",
        "configs",
        "vendor",
        "data/r1-demo",
        "data/r1-source",
        "data/r2-demo",
        "data/r3-demo",
        "data/r4-demo",
    ):
        names.update(
            str(path.relative_to(repo))
            for path in (repo / directory).rglob("*")
            if path.is_file()
            and not set(path.parts)
            & {
                "node_modules",
                ".browsers",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                "test-results",
                "playwright-report",
            }
        )
    result = []
    for name in sorted(names):
        path = repo / name
        if path.is_symlink() or path.name == ".env" or path.suffix in {".key", ".pem"}:
            raise ValueError("unsafe source fingerprint member: " + name)
        result.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = args.output.absolute()
    if not output.is_relative_to(repo / "data/local-operation-review") or ".." in output.parts:
        parser.error("output must be new and under repository data/local-operation-review")
    if any(p.is_symlink() for p in (output, *output.parents)):
        parser.error("output must not contain symlinks")
    output.mkdir(parents=True, exist_ok=False)
    (output / "tmp").mkdir()
    env = {
        "PATH": os.defpath,
        "TZ": "UTC",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(output / "tmp"),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "LOKY_MAX_CPU_COUNT": "1",
        "ENTROPYTRADE_RECOVERY_EVIDENCE": str(output / "listener-recovery"),
    }
    receipt = {
        "started_at": now(),
        "status": "running",
        "complete": False,
        "source_files": sources(repo),
        "steps": [],
        "limitations": [
            "Existing virtualenv; no new clean-install claim.",
            "Browser/full suite unverified; prior denied/stalled attempts not repeated.",
            "Three existing asynchronous R4 workflows explicitly deselected.",
            "Controlled/synthetic software checks are not empirical performance.",
            "Public shadow polls may record honest acquisition failures; no source substitution.",
        ],
        "deselected": DESELECTED,
    }

    def save():
        (output / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")

    python = str(repo / ".venv/bin/python")
    steps = [
        (
            "ruff",
            [
                str(repo / ".venv/bin/ruff"),
                "check",
                "backend",
                "tools/verify_recovery.py",
                "tools/local_acceptance.py",
                "tools/recovery_gate.py",
            ],
            60,
        ),
        (
            "format",
            [
                str(repo / ".venv/bin/ruff"),
                "format",
                "--check",
                "backend",
                "tools/verify_recovery.py",
                "tools/local_acceptance.py",
                "tools/recovery_gate.py",
            ],
            60,
        ),
        ("mypy", [str(repo / ".venv/bin/mypy")], 180),
        ("frontend", [shutil.which("node"), "frontend/tests/acquisition.test.cjs"], 60),
    ]
    for test in TESTS:
        path = "backend/tests/" + test
        name = test.removesuffix(".py").replace("/", "__")
        command = [
            python,
            "-m",
            "pytest",
            path,
            "-q",
            "-o",
            "faulthandler_timeout=45",
            "--junitxml=" + str(output / (name + ".xml")),
        ]
        if test == "unit/test_experiments_r4.py":
            command.extend("--deselect=" + path + "::" + name for name in DESELECTED)
        steps.append((name, command, 600 if test.endswith("test_recovery_listener.py") else 180))
    save()
    try:
        for name, command, deadline in steps:
            step = {"name": name, "command": command, "started_at": now(), "status": "running"}
            receipt["steps"].append(step)
            save()
            print(name + ": started", flush=True)  # noqa: T201 - CLI progress
            with (
                (output / (name + ".log")).open("w") as log,
                subprocess.Popen(  # noqa: S603
                    command,
                    cwd=repo,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                ) as process,
            ):
                try:
                    code = process.wait(timeout=deadline)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    code = 124
                    step["failure"] = f"External deadline {deadline}s; incomplete"
            step.update(
                exit_code=code, status="passed" if code == 0 else "failed", finished_at=now()
            )
            save()
            print(name + ": " + step["status"], flush=True)  # noqa: T201 - CLI progress
        receipt["unchanged_source"] = sources(repo) == receipt["source_files"]
        receipt["status"] = (
            "passed"
            if receipt["unchanged_source"]
            and all(step["status"] == "passed" for step in receipt["steps"])
            else "failed"
        )
    finally:
        receipt["finished_at"] = now()
        save()
    if receipt["status"] != "passed":
        raise SystemExit("Isolated recovery acceptance incomplete; inspect retained logs")


if __name__ == "__main__":
    main()
