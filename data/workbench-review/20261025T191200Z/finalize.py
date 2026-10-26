"""Finalize precise acceptance evidence; no Git mutation or historical receipt rewrite."""

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

bundle = Path(__file__).resolve().parent
repo = bundle.parents[2]
candidate = json.loads((bundle / "candidate-checks.json").read_text())
baseline = json.loads((bundle / "clean-root/checks.json").read_text())
assert candidate["commands"] and all(c["exit_code"] == 0 for c in candidate["commands"])
assert candidate["modified_exported_files"] == []
for command in candidate["commands"]:
    assert hashlib.sha256((bundle / command["log"]).read_bytes()).hexdigest() == command["sha256"]
text = (bundle / "candidate-make-check.log").read_text()
assert "477 files already formatted" in text and "Success: no issues found in 477 source files" in text
assert re.search(r"734 passed in 155\.88s", text)
assert "skipped" not in text and "xfailed" not in text
assert "pass 9" in (bundle / "candidate-frontend.log").read_text()
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip() == candidate["base_commit"]
assert subprocess.check_output(["git", "rev-parse", "main"], cwd=repo).decode().strip() == "30bed8e30cf07201124deee609a21f7f01e47735"
assert subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo).returncode == 0
assert subprocess.run(["git", "diff", "--quiet", "--", "AGENTS.md", ".agents", ".codex"], cwd=repo).returncode == 0
patch = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--", *candidate["overlay"]], cwd=repo)
assert patch == (bundle / "candidate.patch").read_bytes()
manifest = json.loads((bundle / "candidate-manifest.json").read_text())
for name, expected in manifest.items():
    if name.startswith(("backend/", "frontend/", "configs/")) or name in {"uv.lock", "pyproject.toml", "Makefile"}:
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == expected, name

acceptance = {
    "recorded_at": datetime.now(UTC).isoformat(), "reviewed_commit": candidate["base_commit"],
    "reviewed_commit_full_gate": "not_passed: ordinary sandbox socket denials, approved baseline native SQLite close stall",
    "candidate": "uncommitted two-file acceptance deadlock fix; code patch and manifest retained",
    "candidate_full_make_check_exit_code": 0, "pytest_passed": 734, "pytest_elapsed_seconds": 155.88,
    "strict_mypy_files": 477, "ruff_formatted_files_checked": 477, "frontend_passed": 9,
    "javascript_syntax_exit_code": 0, "locked_dependencies_verified": True,
    "no_tests_skipped_or_weakened": True,
    "browser_gate": "blocked", "browser_job_ids": [], "screenshots": [], "browser_downloads": [],
    "browser_steps": [{"step": number, "status": "not_executed", "requirement": requirement}
                      for number, requirement in enumerate([
                          "Recorded insufficiency, exact spec, empty probabilities, protected holdout and downloads",
                          "Synthetic banners on every tab, scenarios, probabilities, negative control and downloads",
                          "Both public families, visible acquisition counts/failures on every tab, rules/clocks and text downloads",
                          "Active cancellation, worker reuse, restart/history, reopened runs and checksummed browser downloads",
                      ], start=1)],
    "retained_evidence": {"reviews": 5, "workflow_artifacts": 51,
                          "initial_checksum_entries_passed": 197, "http_lifecycle_rechecked": True,
                          "browser_verified": False},
    "supervisor_clean_checkout_signoff": "pending final reviewed commit, locked setup and full checks",
    "v1_complete": False, "next_action": "Return for review with browser blocker; no new milestone",
    "production_submission_enabled": False, "no_credential_access": True,
    "no_git_mutations": True, "no_supervisor_control_changes": True,
}
(bundle / "acceptance.json").write_text(json.dumps(acceptance, indent=2) + "\n")
checkout = repo / baseline["checkout"]
assert checkout == repo / ".acceptance-20261025T191200Z" and checkout.is_dir() and not checkout.is_symlink()
retained = repo / "data/cache/acceptance-20261025T191200Z/tested-candidate"
assert not retained.exists()
shutil.move(checkout, retained)
scope = sorted({*repo.glob("backend/**/*.py"), *repo.glob("frontend/**/*"), *repo.glob("configs/**/*.json"),
                *(repo / name for name in ["README.md", "STATUS.md", "PROJECT_CONTEXT.md", "AGENTS.md",
                                          "Makefile", "pyproject.toml", "uv.lock", "docs/roadmap.md",
                                          "docs/workbench.md", "data/workbench-review/README.md"])})
hashes = {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in scope if p.is_file()}
(bundle / "handoff.json").write_text(json.dumps({
    "recorded_at": datetime.now(UTC).isoformat(), "reviewed_commit": candidate["base_commit"],
    "branch": "supervisor/20261025-014400", "candidate_patch_sha256": candidate["code_patch_sha256"],
    "new_commit": None, "no_git_mutations": True, "index_unchanged": True,
    "source_files": hashes, "temporary_export_removed_from_root": not checkout.exists(),
    "retained_tested_snapshot": retained.relative_to(repo).as_posix(),
    "current_docs_are_uncommitted_and_not_part_of_reviewed_commit": True,
    "supervisor_action": "Review/commit the acceptance fix and docs, verify a clean checkout; browser gate pending approved access",
}, indent=2) + "\n")

# Preserve every historical artifact's hash. Only the current index README and new bundle
# are added/refreshed; old attempt directories remain byte-for-byte immutable.
index = bundle.parent / "SHA256SUMS"
entries = {}
for line in index.read_text().splitlines():
    expected, name = line.split("  ", 1)
    path = bundle.parent / name
    if name != "README.md":
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    entries[name] = hashlib.sha256(path.read_bytes()).hexdigest()
for path in bundle.rglob("*"):
    if path.is_file():
        entries[path.relative_to(bundle.parent).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
index.write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(entries.items())))
print(f"Finalized candidate acceptance; {len(entries)} checksummed receipt files; browser gate blocked")
