"""Chain selection in forward-collection.yml, executed against a stubbed ``gh`` CLI.

The step script is read from the workflow file itself, so these cases exercise exactly the
shell that runs on GitHub. ``gh`` is replaced by a stub that answers each API path with
canned (already ``--jq``-filtered) output, or fails for paths it does not know.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

yaml: Any = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "forward-collection.yml"
REPOSITORY = "GabeSternberg/EntropyTrade"
STEP_NAME = "Locate previous workspace snapshot"

STUB = """#!{python}
import json, os, sys
path = sys.argv[2].split("?")[0] if len(sys.argv) > 2 else ""
answers = json.loads(os.environ["GH_STUB_ANSWERS"])
with open(os.environ["GH_STUB_LOG"], "a") as log:
    log.write(path + "\\n")
if path not in answers:
    sys.stderr.write("HTTP 404: " + path + "\\n")
    sys.exit(1)
sys.stdout.write(answers[path])
"""


def _step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["collect"]["steps"]:
        if step.get("name") == STEP_NAME:
            script = step["run"]
            assert "${{" not in script, "expressions must be passed through env"
            return str(script)
    raise AssertionError(f"step {STEP_NAME!r} not found")


def _runs(path: str) -> str:
    return f"repos/{REPOSITORY}/actions/runs/{path}"


def _run(
    tmp_path: Path,
    answers: dict[str, str],
    *,
    continue_from: str = "",
    fresh: str = "false",
) -> tuple[subprocess.CompletedProcess[str], dict[str, str], list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "gh"
    stub.write_text(STUB.format(python=sys.executable), encoding="utf-8")
    stub.chmod(0o755)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    log = tmp_path / "gh.log"
    log.write_text("", encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_STUB_ANSWERS": json.dumps(answers),
        "GH_STUB_LOG": str(log),
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF_NAME": "main",
        "GITHUB_RUN_ID": "900",
        "GITHUB_OUTPUT": str(output),
        "CONTINUE_FROM": continue_from,
        "FRESH": fresh,
    }
    # Same invocation GitHub-hosted runners use for `run:` steps.
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - the script is this repository's workflow step
        [bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", _step_script()],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    outputs = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    calls = [line for line in log.read_text(encoding="utf-8").splitlines() if line]
    return result, outputs, calls


BRANCH_RUNS = f"repos/{REPOSITORY}/actions/workflows/forward-collection.yml/runs"


def _meta(
    branch: str = "claude/chain",
    path: str = ".github/workflows/forward-collection.yml",
    repo: str = REPOSITORY,
    status: str = "completed",
) -> str:
    return f"{path}\t{branch}\t{repo}\t{status}\n"


def test_same_branch_selects_newest_run_with_unexpired_snapshot(tmp_path: Path) -> None:
    answers = {
        BRANCH_RUNS: "803\n802\n801\n",
        _runs("803/artifacts"): "",
        _runs("802/artifacts"): "5555\n",
    }
    result, outputs, calls = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs == {"run_id": "802", "source_branch": "main"}
    assert _runs("801/artifacts") not in calls


def test_same_branch_without_snapshot_starts_new_chain(tmp_path: Path) -> None:
    result, outputs, _ = _run(tmp_path, {BRANCH_RUNS: ""})
    assert result.returncode == 0, result.stderr
    assert outputs == {"run_id": "", "source_branch": "main"}


def test_artifact_listing_error_fails_instead_of_using_older_snapshot(tmp_path: Path) -> None:
    answers = {BRANCH_RUNS: "803\n802\n", _runs("802/artifacts"): "5555\n"}
    result, outputs, _ = _run(tmp_path, answers)
    assert result.returncode != 0
    assert "could not list artifacts of run 803" in result.stdout
    assert "run_id" not in outputs


def test_explicit_continuation_from_another_branch(tmp_path: Path) -> None:
    answers = {_runs("42156641720"): _meta(), _runs("42156641720/artifacts"): "77\n"}
    result, outputs, calls = _run(tmp_path, answers, continue_from="42156641720")
    assert result.returncode == 0, result.stderr
    assert outputs == {"run_id": "42156641720", "source_branch": "claude/chain"}
    assert BRANCH_RUNS not in calls  # never falls back to this branch's own chain


@pytest.mark.parametrize(
    ("continue_from", "fresh", "answers", "message"),
    [
        ("12; echo injected", "false", {}, "must be a numeric run ID"),
        ("41", "true", {}, "mutually exclusive"),
        (
            "41",
            "false",
            {_runs("41"): _meta(path=".github/workflows/egress-probe.yml")},
            "is not a forward-collection run",
        ),
        (
            "41",
            "false",
            {_runs("41"): _meta(repo="someone/fork")},
            "is not a forward-collection run",
        ),
        (
            "41",
            "false",
            {_runs("41"): _meta(status="in_progress")},
            "has not completed",
        ),
        (
            "41",
            "false",
            {_runs("41"): _meta(), _runs("41/artifacts"): ""},
            "no unexpired forward-workspace snapshot",
        ),
        ("41", "false", {}, ""),  # unknown run: gh fails, step fails
    ],
)
def test_explicit_continuation_fails_closed(
    tmp_path: Path,
    continue_from: str,
    fresh: str,
    answers: dict[str, str],
    message: str,
) -> None:
    answers = {**answers, BRANCH_RUNS: "803\n", _runs("803/artifacts"): "5555\n"}
    result, outputs, calls = _run(tmp_path, answers, continue_from=continue_from, fresh=fresh)
    assert result.returncode != 0
    assert message in result.stdout
    assert "run_id" not in outputs
    assert BRANCH_RUNS not in calls


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"]["collect"]["steps"]
    return steps


def _step(name: str) -> dict[str, Any]:
    return next(step for step in _steps() if step.get("name") == name)


def test_no_step_condition_hashes_files() -> None:
    # hashFiles() reads whole files and is cut off after 120 s on hosted runners; with a
    # 243 MB archive that skipped the snapshot upload (run 42162688233) and broke the chain.
    conditions = [str(step.get("if", "")) for step in _steps()]
    assert not [condition for condition in conditions if "hashFiles" in condition]


def test_snapshot_upload_depends_on_completed_archive() -> None:
    snapshot = _step("Snapshot workspace")
    upload = _step("Upload workspace snapshot")
    assert snapshot["id"] == "snapshot"
    assert upload["if"] == "always() && steps.snapshot.outputs.archive == 'true'"
    lines = [line.strip() for line in str(snapshot["run"]).splitlines() if line.strip()]
    # The output is the last command, so a failed snapshot, checksum or lineage never uploads.
    assert lines[-1] == 'echo "archive=true" >> "$GITHUB_OUTPUT"'
    for name in (
        "Capture official fee documents (unreviewed, at most daily)",
        "Snapshot workspace",
    ):
        assert _step(name)["if"] == "always() && steps.workspace.outputs.exists == 'true'"


@pytest.mark.parametrize("present", [True, False])
def test_workspace_check_step(tmp_path: Path, present: bool) -> None:
    step = _step("Check for a workspace")
    assert step["id"] == "workspace"
    assert step["if"] == "always()"
    workspace = tmp_path / "forward"
    workspace.mkdir()
    if present:
        (workspace / "jobs.sqlite").write_bytes(b"")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - the script is this repository's workflow step
        [bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", str(step["run"])],
        env={"PATH": os.environ["PATH"], "WORKSPACE": str(workspace), "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert output.read_text(encoding="utf-8") == f"exists={'true' if present else 'false'}\n"
