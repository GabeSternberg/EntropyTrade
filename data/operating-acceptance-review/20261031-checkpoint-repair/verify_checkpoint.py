"""Read-only cross-check; print a NEW receipt, never rewrite prior execution evidence."""

import hashlib
import json
import runpy
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REVIEW = REPO / "data/operating-acceptance-review"
SERIAL = REVIEW / "20261031-permitted-serial"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args, input=None):
    return subprocess.check_output(["git", *args], cwd=REPO, input=input)


def main():
    retention = runpy.run_path(str(REPO / "tools/review_artifacts.py"))
    manifest_path = Path("data/operating-acceptance-review/local-artifacts-20261031.json")
    retention_result = retention["verify"](REPO, manifest_path)
    manifest = read(REPO / manifest_path)
    paths = [item["path"] for item in manifest["inventory"]["files"]]
    tracked = set(git("ls-files", "-z").decode().split("\0")) - {""}
    require(not tracked.intersection(paths), "Retained artifact was already tracked")
    ignored = set(
        git("check-ignore", "--stdin", "-z", input="\0".join(paths).encode() + b"\0")
        .decode().split("\0")
    ) - {""}
    require(ignored == set(paths), "Retained artifact remains eligible for new staging")
    # Read-only approximation of the supervisor's prospective normal staging set.
    # Never stage, unstage, commit or alter the supervisor's checkpoint implementation.
    modified = set(git("diff", "HEAD", "--name-only", "-z").decode().split("\0")) - {""}
    untracked = set(git("ls-files", "--others", "--exclude-standard", "-z")
                    .decode().split("\0")) - {""}
    candidates = sorted(name for name in modified | untracked if (REPO / name).is_file())
    oversized = [name for name in candidates if (REPO / name).stat().st_size > 8_000_000]
    require(not oversized, "Oversized checkpoint candidates: " + repr(oversized))
    require(not git("diff", "--cached", "--name-only"), "Expected untouched empty staging index")

    original = read(SERIAL / "verification.json")
    receipt = read(SERIAL / "acceptance.json")
    installation = Path(receipt["installation"])
    for item in receipt["source_files"]:
        require(sha(REPO / item["path"]) == sha(installation / item["path"]) == item["sha256"],
                "Original source/install fingerprint changed: " + item["path"])
    safety = read(SERIAL / "safety-receipt.json")
    for name, item in safety["checks"].items():
        require("sha256:" + sha(REPO / name) == item["expected"],
                "Protected evidence changed: " + name)
    for procedure in original["procedures"]:
        for item in procedure["artifacts"]:
            path = SERIAL / item["path"]
            require(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"],
                    "Browser download/screenshot changed: " + item["path"])
    for item in original["traces"]:
        trace = SERIAL / item["path"]
        require(sha(trace) == item["sha256"], "Final trace changed: " + item["path"])
        with zipfile.ZipFile(trace) as archive:
            require(archive.testzip() is None, "Corrupt trace: " + item["path"])
    driver = runpy.run_path(str(REPO / "tools/local_acceptance.py"))
    browser = driver["inspect_browser_report"](
        SERIAL / "browser/playwright-results.json", execution=True,
        expected=driver["REQUIRED_BROWSER_PROCEDURES"], require_all=True,
    )
    require(browser["status"] == "passed", "Original browser execution report failed validation")
    junit = ET.parse(SERIAL / "pytest.xml").getroot()
    suites = list(junit.iter("testsuite"))
    tests = sum(int(suite.get("tests", "0")) for suite in suites)
    require(suites and tests == len(list(junit.iter("testcase"))) == 1210,
            "Original full-suite JUnit counts differ")
    require(all(int(suite.get(key, "0")) == 0 for suite in suites
                for key in ("failures", "errors", "skipped")), "Original suite is incomplete")
    require(receipt["status"] == "passed" and receipt["acceptance_complete"] is True,
            "Original serial driver did not complete")
    require(all(step["status"] == "passed" and step["exit_code"] == 0
                for step in receipt["steps"]), "Original driver step failed")

    tracked_large = []
    for name in sorted(tracked):
        path = REPO / name
        if path.is_file() and path.stat().st_size > 8_000_000:
            require(name not in modified, "Tracked large artifact was modified: " + name)
            tracked_large.append({"path": name, "bytes": path.stat().st_size,
                                  "sha256": sha(path), "unchanged": True})
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "local_retention": retention_result,
        "manifest_bytes": (REPO / manifest_path).stat().st_size,
        "manifest_sha256": sha(REPO / manifest_path),
        "all_manifest_members_ignored_and_untracked": True,
        "prospective_checkpoint_candidates": len(candidates),
        "candidate_files_over_8000000_bytes": oversized,
        "largest_candidate_bytes": max((REPO / name).stat().st_size for name in candidates),
        "staging_index_empty": True,
        "original_checkout_and_installation_hashes_verified": len(receipt["source_files"]),
        "original_safety_hashes_verified": len(safety["checks"]),
        "original_browser_report": browser,
        "original_downloads_verified": original["downloads_verified"],
        "original_screenshots_verified": original["screenshots_verified"],
        "original_trace_hashes_and_zip_integrity_verified": len(original["traces"]),
        "original_full_suite_junit": {"tests": tests, "failures": 0, "errors": 0, "skipped": 0},
        "unchanged_existing_tracked_large_artifacts": tracked_large,
        "browser_and_full_suite_reexecuted": False,
        "git_mutations_performed": False,
        "v1_complete": False,
        "limitations": manifest["limitations"] + [
            "Candidate-size scan uses ordinary Git visibility and a conservative 8,000,000-byte "
            "limit; the supervisor's actual checkpoint is not executed or modified.",
            "The original passing suite/browser/restore receipts retain their historical scope. "
            "This repair rechecks bytes/reports, not page interactions or a fresh installation.",
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
