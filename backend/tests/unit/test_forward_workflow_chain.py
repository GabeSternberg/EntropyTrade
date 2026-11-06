"""Chain selection in forward-collection.yml, executed against a stubbed ``gh`` CLI.

The step scripts are read from the workflow file itself, so these cases exercise exactly the
shell that runs on GitHub. ``gh`` is replaced by a stub that answers each API path with raw
JSON, applies the step's own ``--jq`` filter with the real ``jq`` binary (as ``gh`` does),
and fails for paths it does not know.
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
import json, os, subprocess, sys
args = sys.argv[1:]
assert args[0] == "api" and args[2] == "--jq" and len(args) == 4, args
path, query = args[1].split("?")[0], args[3]
answers = json.loads(os.environ["GH_STUB_ANSWERS"])
with open(os.environ["GH_STUB_LOG"], "a") as log:
    log.write(args[1] + "\\n")
if path not in answers:
    sys.stderr.write("HTTP 404: " + path + "\\n")
    sys.exit(1)
done = subprocess.run(
    [os.environ["GH_STUB_JQ"], "-r", query], input=json.dumps(answers[path]),
    capture_output=True, text=True,
)
sys.stdout.write(done.stdout)
sys.stderr.write(done.stderr)
sys.exit(done.returncode)
"""

BRANCH_RUNS = f"repos/{REPOSITORY}/actions/workflows/forward-collection.yml/runs"


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


def _branch_runs(*runs: tuple[int, str, str] | tuple[int, str, str, str]) -> dict[str, Any]:
    """API listing in creation order (newest first): (id, status, updated_at[, event])."""
    return {
        "workflow_runs": [
            {
                "id": run[0],
                "status": run[1],
                "updated_at": run[2],
                "event": run[3] if len(run) > 3 else "workflow_dispatch",
            }
            for run in runs
        ]
    }


def _artifacts(*items: tuple[str, bool]) -> dict[str, Any]:
    return {
        "artifacts": [
            {"id": 1000 + index, "name": name, "expired": expired}
            for index, (name, expired) in enumerate(items)
        ]
    }


SNAPSHOT = _artifacts(("forward-summary", False), ("forward-workspace", False))
NO_SNAPSHOT = _artifacts(("forward-summary", False))


def _meta(
    branch: str = "claude/chain",
    path: str = ".github/workflows/forward-collection.yml",
    repo: str = REPOSITORY,
    status: str = "completed",
) -> dict[str, Any]:
    return {
        "path": path,
        "head_branch": branch,
        "repository": {"full_name": repo},
        "status": status,
    }


def _run(
    tmp_path: Path,
    answers: dict[str, Any],
    *,
    continue_from: str = "",
    fresh: str = "false",
) -> tuple[subprocess.CompletedProcess[str], dict[str, str], list[str]]:
    jq = shutil.which("jq")
    assert jq is not None, "jq is preinstalled on GitHub-hosted runners and required here"
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
        "GH_STUB_JQ": jq,
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
    calls = [line.split("?")[0] for line in log.read_text(encoding="utf-8").splitlines() if line]
    return result, outputs, calls


def test_same_branch_selects_latest_completed_run_with_unexpired_snapshot(
    tmp_path: Path,
) -> None:
    answers = {
        BRANCH_RUNS: _branch_runs(
            (900, "in_progress", "2026-11-06T06:00:00Z"),  # this run
            (803, "completed", "2026-11-06T05:30:00Z"),
            (802, "completed", "2026-11-06T05:00:00Z"),
            (801, "completed", "2026-11-06T04:00:00Z"),
        ),
        _runs("803/artifacts"): NO_SNAPSHOT,
        _runs("802/artifacts"): SNAPSHOT,
    }
    result, outputs, calls = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs == {"run_id": "802", "source_branch": "main"}
    assert _runs("801/artifacts") not in calls
    assert _runs("900/artifacts") not in calls


def test_expired_snapshot_is_not_selected(tmp_path: Path) -> None:
    answers = {
        BRANCH_RUNS: _branch_runs(
            (803, "completed", "2026-11-06T05:30:00Z"),
            (802, "completed", "2026-11-06T05:00:00Z"),
        ),
        _runs("803/artifacts"): _artifacts(("forward-workspace", True)),
        _runs("802/artifacts"): SNAPSHOT,
    }
    result, outputs, _ = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs["run_id"] == "802"


def test_completion_order_not_creation_order_defines_the_chain(tmp_path: Path) -> None:
    # Two chain runs on one branch: the one created first can finish last.
    answers = {
        BRANCH_RUNS: _branch_runs(
            (812, "completed", "2026-11-06T05:50:00Z", "schedule"),
            (811, "completed", "2026-11-06T06:20:00Z"),
            (810, "completed", "2026-11-06T04:44:00Z"),
        ),
        _runs("812/artifacts"): SNAPSHOT,
        _runs("811/artifacts"): SNAPSHOT,
        _runs("810/artifacts"): SNAPSHOT,
    }
    result, outputs, calls = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs["run_id"] == "811"
    assert calls[1] == _runs("811/artifacts")


def test_push_runs_are_never_chain_heads(tmp_path: Path) -> None:
    # Observed on 2026-11-06: push 42162670639 was the first run on its branch and started a
    # fresh chain; later push 42167132149 completed after it. Older workflow versions
    # uploaded both as forward-workspace. Neither may be continued as the chain.
    answers = {
        BRANCH_RUNS: _branch_runs(
            (42167132149, "completed", "2026-11-06T05:50:00Z", "push"),
            (42167131442, "completed", "2026-11-06T05:15:47Z"),
            (42162670639, "completed", "2026-11-06T04:44:00Z", "push"),
            (802, "completed", "2026-11-06T04:00:00Z"),
        ),
        _runs("42167132149/artifacts"): SNAPSHOT,
        _runs("42167131442/artifacts"): NO_SNAPSHOT,  # cancelled while pending
        _runs("42162670639/artifacts"): SNAPSHOT,
        _runs("802/artifacts"): SNAPSHOT,
    }
    result, outputs, calls = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs["run_id"] == "802"
    assert _runs("42167132149/artifacts") not in calls
    assert _runs("42162670639/artifacts") not in calls


def test_branch_with_only_push_runs_starts_new_chain(tmp_path: Path) -> None:
    answers = {
        BRANCH_RUNS: _branch_runs((42162670639, "completed", "2026-11-06T04:44:00Z", "push")),
        _runs("42162670639/artifacts"): SNAPSHOT,
    }
    result, outputs, calls = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs == {"run_id": "", "source_branch": "main"}
    assert _runs("42162670639/artifacts") not in calls


def test_incomplete_runs_are_never_selected(tmp_path: Path) -> None:
    answers = {
        BRANCH_RUNS: _branch_runs(
            (804, "queued", "2026-11-06T07:00:00Z"),
            (803, "in_progress", "2026-11-06T06:30:00Z"),
            (802, "completed", "2026-11-06T05:00:00Z"),
        ),
        _runs("802/artifacts"): SNAPSHOT,
    }
    result, outputs, _ = _run(tmp_path, answers)
    assert result.returncode == 0, result.stderr
    assert outputs["run_id"] == "802"


def test_same_branch_without_snapshot_starts_new_chain(tmp_path: Path) -> None:
    result, outputs, _ = _run(tmp_path, {BRANCH_RUNS: _branch_runs()})
    assert result.returncode == 0, result.stderr
    assert outputs == {"run_id": "", "source_branch": "main"}


def test_artifact_listing_error_fails_instead_of_using_older_snapshot(tmp_path: Path) -> None:
    answers = {
        BRANCH_RUNS: _branch_runs(
            (803, "completed", "2026-11-06T05:30:00Z"),
            (802, "completed", "2026-11-06T05:00:00Z"),
        ),
        _runs("802/artifacts"): SNAPSHOT,
    }
    result, outputs, _ = _run(tmp_path, answers)
    assert result.returncode != 0
    assert "could not list artifacts of run 803" in result.stdout
    assert "run_id" not in outputs


def test_explicit_continuation_from_another_branch(tmp_path: Path) -> None:
    answers = {_runs("42156641720"): _meta(), _runs("42156641720/artifacts"): SNAPSHOT}
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
            {_runs("41"): _meta(), _runs("41/artifacts"): NO_SNAPSHOT},
            "no unexpired forward-workspace snapshot",
        ),
        (
            "41",
            "false",
            {_runs("41"): _meta(), _runs("41/artifacts"): _artifacts(("forward-workspace", True))},
            "no unexpired forward-workspace snapshot",
        ),
        ("41", "false", {}, ""),  # unknown run: gh fails, step fails
    ],
)
def test_explicit_continuation_fails_closed(
    tmp_path: Path,
    continue_from: str,
    fresh: str,
    answers: dict[str, Any],
    message: str,
) -> None:
    answers = {
        **answers,
        BRANCH_RUNS: _branch_runs((803, "completed", "2026-11-06T05:00:00Z")),
        _runs("803/artifacts"): SNAPSHOT,
    }
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


def test_push_trials_cannot_displace_chain_runs_or_become_heads() -> None:
    # GitHub keeps one pending run per concurrency group; a pending push replaced queued
    # continuation dispatch 42167131442. Push runs therefore use their own group.
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    group = str(workflow["concurrency"]["group"])
    assert group == (
        "forward-collection-${{ github.event_name == 'push' && 'trial-' || '' }}${{ github.ref }}"
    )
    assert workflow["concurrency"]["cancel-in-progress"] is False
    upload = _step("Upload workspace snapshot")["with"]
    assert upload["name"] == (
        "${{ github.event_name == 'push' && 'forward-trial-workspace' || 'forward-workspace' }}"
    )
    # The lookup only ever continues the chain artifact name.
    script = _step_script()
    assert 'select(.name == "forward-workspace"' in script
    assert "forward-trial-workspace" not in script
    lineage = str(_step("Snapshot workspace")["run"])
    assert 'echo "event=$GITHUB_EVENT_NAME"' in lineage
    assert "chain=trial" in lineage
    assert "chain=head" in lineage


@pytest.mark.parametrize("previous", [True, False])
def test_runway_ledger_travels_with_the_chain(tmp_path: Path, previous: bool) -> None:
    """The collect step passes the previous ledger (when restored) and writes a new one."""
    step = _step("Collect (bounded window)")
    script = (
        str(step["run"])
        .replace("${{ inputs.seconds }}", "")
        .replace("${{ github.event_name }}", "schedule")
    )
    assert "${{" not in script
    out = tmp_path / "out"
    out.mkdir()
    if previous:
        (out / "previous-runway-ledger.jsonl").write_text("{}\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "argv.json"
    stub = bin_dir / "uv"
    stub.write_text(
        f"#!{sys.executable}\nimport json, sys\n"
        f"open({str(argv_log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - the script is this repository's workflow step
        [bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "WORKSPACE": "ws",
            "OUT": str(out),
            "GITHUB_RUN_ID": "123",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    argv = json.loads(argv_log.read_text(encoding="utf-8"))
    assert argv[argv.index("--seconds") + 1] == "540"  # one cycle per scheduled window
    assert argv[argv.index("--ledger-out") + 1] == f"{out}/runway-ledger.jsonl"
    assert argv[argv.index("--run-id") + 1] == "123"
    if previous:
        assert argv[argv.index("--ledger-in") + 1] == f"{out}/previous-runway-ledger.jsonl"
    else:
        assert "--ledger-in" not in argv
    upload = _step("Upload workspace snapshot")
    assert "data/cache/forward-out/runway-ledger.jsonl" in str(upload["with"]["path"])
    restore = str(_step("Restore previous workspace (fails closed)")["run"])
    assert 'runway-ledger.jsonl "$OUT/previous-runway-ledger.jsonl"' in restore
