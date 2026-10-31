"""Cross-check this executed acceptance bundle; never substitute for its actual tests."""

import hashlib
import json
import runpy
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
REPO = OUTPUT.parents[2]
BROWSER = OUTPUT / "browser"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    receipt = read(OUTPUT / "acceptance.json")
    require(receipt["status"] == "passed", "Driver did not pass")
    require(receipt["acceptance_complete"] is True, "Driver acceptance incomplete")
    require(not receipt["unexecuted_checks"], "Unexecuted driver gates")
    require(not receipt["provisioning"]["reused_virtualenv"], "Environment reused")
    require(len(receipt["steps"]) == 14, "Missing driver steps")
    require(all(s["status"] == "passed" and s["exit_code"] == 0 for s in receipt["steps"]),
            "Failed driver step")
    driver = runpy.run_path(str(REPO / "tools/local_acceptance.py"))
    report = driver["inspect_browser_report"](
        BROWSER / "playwright-results.json", execution=True,
        expected=driver["REQUIRED_BROWSER_PROCEDURES"], require_all=True,
    )
    require(report["status"] == "passed" and not report["missing_required"],
            "Incomplete actual browser results")

    sources = []
    installation = Path(receipt["installation"])
    for item in receipt["source_files"]:
        source, installed = REPO / item["path"], installation / item["path"]
        require(sha(source) == sha(installed) == item["sha256"],
                "Source fingerprint mismatch: " + item["path"])
        sources.append(item)
    (OUTPUT / "source-verification.json").write_text(json.dumps({
        "files": len(sources), "checkout_and_installation_match": True, "checks": sources,
    }, indent=2) + "\n")
    baseline = REPO / "data/debugging-review/20261031-provider-deadline/safety-receipt.json"
    safety = {}
    for name, check in read(baseline)["checks"].items():
        actual = "sha256:" + sha(REPO / name)
        require(actual == check["expected"], "Protected bytes changed: " + name)
        safety[name] = {"expected": check["expected"], "actual": actual, "unchanged": True}
    require(len(safety) == 73, "Missing protected receipt/boundary checks")
    (OUTPUT / "safety-receipt.json").write_text(json.dumps({
        "baseline": str(baseline.relative_to(REPO)), "all_unchanged": True,
        "original_receipt_files": 68, "bitcoin_boundary_files": 5, "checks": safety,
    }, indent=2) + "\n")

    procedures = []
    for relative in ["alerts/receipt.json", "controlled/receipt.json", "authentic/receipt.json",
                     "provider-browser-receipt.json", "recovery-browser-receipt.json",
                     "weather-browser-receipt.json"]:
        path = BROWSER / relative
        browser = read(path)
        require(browser["status"] == "passed" and browser["page_errors"] == [],
                "Failed browser receipt: " + relative)
        require("frontend/browser/.browsers/chromium-" in browser["executable"],
                "Unmanaged Chromium: " + relative)
        artifacts = []
        for kind in ("downloads", "screenshots"):
            require(browser[kind], "No " + kind + ": " + relative)
            for item in browser[kind]:
                artifact = path.parent / item["file"]
                digest = sha(artifact)
                if "sha256" in item:
                    require(digest == item["sha256"], "Artifact hash mismatch: " + str(artifact))
                if kind == "screenshots":
                    require(artifact.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"),
                            "Invalid screenshot: " + str(artifact))
                artifacts.append({"path": str(artifact.relative_to(OUTPUT)), "kind": kind,
                                  "bytes": artifact.stat().st_size, "sha256": digest})
        procedures.append({"receipt": relative, "status": browser["status"],
                           "browser": browser["browser"], "page_errors": [],
                           "screenshots": len(browser["screenshots"]),
                           "downloads": len(browser["downloads"]), "artifacts": artifacts})

    pairs = [
        ("alerts/acknowledged.json", "alerts/restarted.json"),
        ("alerts/recurring.json", "alerts/final.json"),
        ("alerts/final.json", "alerts/restored.json"),
        ("controlled/account.json", "controlled/restarted-account.json"),
        ("controlled/shadow.json", "controlled/restarted-shadow.json"),
        ("authentic/account.json", "authentic/restarted-account.json"),
        ("authentic/shadow.json", "authentic/restarted-shadow.json"),
        ("provider-success.json", "provider-success-restarted.json"),
        ("provider-success.txt", "provider-success-restarted.txt"),
        ("provider-outage.json", "provider-outage-restarted.json"),
        ("provider-unpriced-first.json", "provider-unpriced-first-restarted.json"),
        ("provider-unpriced-second.json", "provider-unpriced-second-restarted.json"),
        ("synthetic-review.json", "synthetic-restored.json"),
        ("synthetic-report.txt", "synthetic-restored.txt"),
        ("recorded-review.json", "recorded-restored.json"),
        ("paused-original.json", "paused-restored.json"),
        ("paused-original.json", "paused-second-restart.json"),
        ("weather-review.json", "weather-restart-review.json"),
        ("weather-report.txt", "weather-restart-report.txt"),
    ]
    comparisons = []
    for before, after in pairs:
        require((BROWSER / before).read_bytes() == (BROWSER / after).read_bytes(),
                "Reopened downloads differ: " + before + " / " + after)
        comparisons.append({"before": before, "after": after, "identical": True,
                            "sha256": sha(BROWSER / before)})
    traces = []
    for trace in sorted((BROWSER / "playwright-artifacts").glob("*/trace.zip")):
        with zipfile.ZipFile(trace) as archive:
            require(archive.testzip() is None, "Corrupt trace: " + str(trace))
            require(any(n.endswith(".trace") for n in archive.namelist()), "Missing action trace")
        traces.append({"path": str(trace.relative_to(OUTPUT)), "bytes": trace.stat().st_size,
                       "sha256": sha(trace)})
    require(len(traces) == 6, "Missing procedure traces")
    offline = read(OUTPUT / "paper-offline-restore/receipt.json")
    require(offline["status"] == "passed", "Paper workspace restoration failed")
    require({w["name"] for w in offline["browser_workspaces"]} == {"controlled", "authentic"},
            "Missing actual paper browser workspace restore")
    for workspace in offline["browser_workspaces"]:
        require(workspace["restored_export_identical_to_download"]
                and workspace["account_reproduction"]["verified"], "Paper restore/replay failed")
        require(sha(OUTPUT / "paper-offline-restore" / workspace["archive"])
                == workspace["archive_sha256"], "Retained paper archive changed")
    require(sha(OUTPUT / offline["alerts_browser_archive_retained"]["path"])
            == offline["alerts_browser_archive_retained"]["sha256"], "Missing alert archive")
    retained = read(OUTPUT / "workspaces/receipt.json")
    require(retained["status"] == "passed" and len(retained["archives"]) == 3,
            "Missing stopped final browser workspaces")
    for archive in retained["archives"]:
        require(sha(OUTPUT / archive["archive"]) == archive["sha256"],
                "Retained final workspace archive changed")
    suites = list(ET.parse(OUTPUT / "pytest.xml").getroot().iter("testsuite"))
    require(suites, "Missing pytest JUnit suites")
    require(all(int(s.get(k, "0")) == 0 for s in suites
                for k in ("failures", "errors", "skipped")), "Incomplete pytest suite")
    tests = sum(int(s.get("tests", "0")) for s in suites)
    require(tests == len(list(ET.parse(OUTPUT / "pytest.xml").getroot().iter("testcase")))
            and tests > 0, "Inconsistent pytest counts")
    result = {
        "checked_at": datetime.now(UTC).isoformat(), "status": "passed",
        "operating_acceptance_complete": True, "v1_complete": False,
        "browser_report": report, "source_files_verified": len(sources),
        "safety_files_verified": len(safety), "procedures": procedures,
        "screenshots_verified": sum(p["screenshots"] for p in procedures),
        "downloads_verified": sum(p["downloads"] for p in procedures),
        "identical_download_pairs": comparisons, "traces": traces, "page_errors": [],
        "paper_browser_workspace_offline_restore": offline,
        "retained_final_browser_workspaces": retained,
        "pytest": {"tests": tests, "failures": 0, "errors": 0, "skipped": 0,
                   "seconds": sum(float(s.get("time", "0")) for s in suites)},
        "limitations": ["Independent supervisor review is still required.",
                        "Controlled provider/health/accounting evidence is software evidence.",
                        "Authentic empirical models, fees, two-family validation and an authorized "
                        "external provider session remain open; no profitability claim."],
    }
    (OUTPUT / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "operating_acceptance_complete",
                                           "v1_complete", "source_files_verified",
                                           "screenshots_verified", "downloads_verified", "pytest")},
                     indent=2))


if __name__ == "__main__":
    main()
