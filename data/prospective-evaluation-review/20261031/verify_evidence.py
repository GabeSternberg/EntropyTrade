"""Verify retained evidence without Git changes, networking or credential access."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from entropytrade.data.sources import file_hash

repo = Path.cwd()
root = repo / "data/prospective-evaluation-review/20261031"
baseline = json.loads((repo / "data/label-partition-review/20261031/safety-receipt.json").read_text())
assert all(file_hash(repo / p) == row["expected"] for p, row in baseline["checks"].items())
focused = list(ET.parse(root / "focused-final.xml").getroot().iter("testsuite"))
counts = {k: sum(int(s.attrib[k]) for s in focused) for k in ("tests", "failures", "errors", "skipped")}
assert counts == {"tests": 28, "failures": 0, "errors": 0, "skipped": 0}
serial = list(ET.parse(root / "shadow-history-isolated.xml").getroot().iter("testsuite"))
assert sum(int(s.attrib["tests"]) for s in serial) == 14
assert all(int(s.attrib[k]) == 0 for s in serial for k in ("failures", "errors", "skipped"))
assert "All checks passed!" in (root / "ruff-lint.log").read_text()
assert "files already formatted" in (root / "ruff-format.log").read_text()
assert "Success: no issues found in 556 source files" in (root / "mypy.log").read_text()
assert "# tests 24" in (root / "frontend-final.log").read_text()
assert "# fail 0" in (root / "frontend-final.log").read_text()
assert "Total: 2 tests" in (root / "harness-final-discovery.log").read_text()
offline = json.loads((root / "offline/receipt.json").read_text())
for row in offline:
    assert row["restart_identical"] and row["offline_report_identical"] and row["offline_csv_identical"]
    assert file_hash(repo / row["archive"]) == row["archive_sha256"]
    for relative, check in json.loads((root / "offline" / (row["kind"] + "-source-hashes.json")).read_text()).items():
        assert file_hash(repo / row["restored_workspace"] / relative) == check["expected"]
    value = json.loads((root / "offline" / (row["kind"] + "-report.json")).read_text())
    from entropytrade.api.jobs import Jobs
    from entropytrade.tracking.prospective import report, csv_report
    assert report(Jobs(repo / row["restored_workspace"]), value["monitor_id"]) == value
    assert csv_report(value).encode() == (root / "offline" / (row["kind"] + "-observations.csv")).read_bytes()
    assert not value["submission_enabled"] and value["performance"] is None
browser = json.loads((root / "browser-attempt-1/playwright-results.json").read_text())
assert browser["stats"]["unexpected"] >= 1
assert "Operation not permitted" in (root / "browser-attempt-1.log").read_text()
suite = json.loads((root / "per-file-summary.json").read_text())
assert suite["all_files_attempted"]
assert suite["file_count"] == len(list((repo / "backend/tests").rglob("test_*.py")))
failed = [r for r in suite["results"] if r["exit_code"] != 0 and not r["deadline_exceeded"]]
deadlines = [r for r in suite["results"] if r["deadline_exceeded"]]
passed = [r for r in suite["results"] if r["exit_code"] == 0 and not r["deadline_exceeded"]]
sources = [
    "backend/src/entropytrade/tracking/prospective.py", "backend/src/entropytrade/tracking/worker.py",
    "backend/src/entropytrade/api/server.py", "backend/src/entropytrade/tracking/store.py",
    "backend/src/entropytrade/tracking/history.py", "backend/src/entropytrade/tracking/replay.py",
    "backend/src/entropytrade/tracking/models.py", "backend/src/entropytrade/tracking/accounting.py",
    "backend/src/entropytrade/risk/engine.py", "uv.lock", "pyproject.toml",
    "backend/tests/unit/test_prospective.py", "backend/tests/integration/prospective_fixture.py",
    "backend/tests/integration/test_prospective_offline.py", "backend/tests/integration/test_prospective_listener.py",
    "backend/tests/integration/test_shadow_tracking.py", "frontend/src/app.js", "frontend/tests/acquisition.test.cjs",
    "frontend/browser/prospective.spec.cjs", "frontend/browser/playwright.config.cjs",
    "frontend/browser/README.md", "STATUS.md", "docs/roadmap.md", "docs/prospective-evaluation.md",
    "docs/shadow-tracking.md", "docs/v1_acceptance.md",
]
(root / "source-hashes.json").write_text(json.dumps({p: file_hash(repo / p) for p in sources}, indent=2))
manifest = [{"path": str(p.relative_to(repo)), "sha256": file_hash(p), "bytes": p.stat().st_size}
            for p in sorted(root.rglob("*")) if p.is_file()
            and p.name not in {"retained-artifacts.json", "verification.json", "verification.log"}]
assert not any(r["bytes"] > 8_000_000 for r in manifest)
(root / "retained-artifacts.json").write_text(json.dumps(manifest, indent=2))
result = {
    "focused": counts, "serial_shadow_history_cases": 14, "frontend_passed": 24, "mypy_files": 556,
    "original_and_boundary_hashes_unchanged": len(baseline["checks"]),
    "offline": offline, "browser_passed": False, "browser_permission_denied": True,
    "all_test_files_attempted": suite["file_count"], "file_passes": len(passed),
    "file_failures": failed, "file_deadlines": deadlines, "bounded_seconds": suite["seconds"],
    "full_suite_pass": suite["complete_suite_pass"], "complete": False,
    "outstanding": ["Actual localhost listener test", "Both real Chromium procedures with downloads/screenshots",
                    "Complete suite in a socket-permitted runtime; investigate shutdown/native failures if repeated",
                    "Independent supervisor review"],
    "retained_files": len(manifest), "retained_bytes": sum(r["bytes"] for r in manifest),
}
(root / "verification.json").write_text(json.dumps(result, indent=2))
print(json.dumps({k: v for k, v in result.items() if k not in {"offline", "file_failures", "file_deadlines"}}, indent=2))
