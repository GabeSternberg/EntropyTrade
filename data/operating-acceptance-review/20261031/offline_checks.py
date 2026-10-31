"""Scoped offline operating proof; this never runs a browser, listener or full suite."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.tracking.accounting import verify_export
from entropytrade.tracking.store import TrackingStore
from tests.integration.alerts_fixture import operate
from tests.integration.paper_fixture import seed


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "status": "running",
        "browser_or_listener_executed": False,
        "limitation": "Offline software proof only; controlled fills/health/outcomes are synthetic. "
        "Authentic data replays original receipts without new acquisition or empirical returns.",
        "paper": [],
    }

    def save():
        (args.output / "receipt.json").write_bytes(encoded(receipt))

    def backup(workspace, name):
        archive = args.repo / "data" / (name + ".zip")
        restored = workspace.with_name(workspace.name + "-restored")
        snapshot(args.repo, workspace, archive)
        restore(args.repo, archive, restored)
        shutil.copyfile(archive, args.output / archive.name)
        return restored

    save()
    try:
        for authentic in (False, True):
            name = "authentic" if authentic else "controlled"
            workspace = args.repo / "data/cache" / ("offline-paper-" + name)
            setup = seed(workspace, authentic=authentic)
            store = TrackingStore(Jobs(workspace))
            original = store.get(setup["monitor_id"], export=True)
            assert original and original["submission_enabled"] is False
            verified = verify_export(original)
            before = encoded(original)
            (args.output / (name + "-shadow.json")).write_bytes(before)
            reopened = TrackingStore(Jobs(workspace))
            reopened.recover()
            assert encoded(reopened.get(setup["monitor_id"], export=True)) == before
            restored = TrackingStore(Jobs(backup(workspace, "offline-paper-" + name)))
            restored.recover()
            after = encoded(restored.get(setup["monitor_id"], export=True))
            assert after == before
            if authentic:
                assert setup["summary"]["fill_count"] == 0
                assert setup["summary"]["cash"] == "1000.000000"
                assert setup["summary"]["fees"] == "0.000000"
                decisions = original["cycles"][0]["result"]["paper"]["decisions"]
                assert decisions and all(d["status"] == "blocked" for d in decisions)
                assert all(d["intent"] is None for d in decisions)
                assert all(not d["gates"]["point_in_time_prediction"] for d in decisions)
                assert all(not d["gates"]["certified_fees"] for d in decisions)
            else:
                assert setup["summary"]["fill_count"] == 2
                assert setup["summary"]["settlement_count"] == 1
            receipt["paper"].append({
                "name": name,
                "setup": setup,
                "account_reproduction": verified,
                "reopened_export_identical": True,
                "restored_export_identical": True,
                "export_sha256": hashlib.sha256(before).hexdigest(),
                "restored_export_sha256": hashlib.sha256(after).hexdigest(),
            })
            save()

        workspace = args.repo / "data/cache/offline-alerts"
        seeded = operate(workspace, "seed")
        mid = seeded["monitor_id"]
        assert len(seeded["alerts"]) == 3
        store = TrackingStore(Jobs(workspace))
        for alert in seeded["alerts"]:
            store.acknowledge(mid, alert["id"])
            first = encoded(store.get(mid, export=True))
            store.acknowledge(mid, alert["id"])
            assert first == encoded(store.get(mid, export=True))
        acknowledged = encoded(store.get(mid, export=True))
        reopened = TrackingStore(Jobs(workspace))
        reopened.recover()
        assert acknowledged == encoded(reopened.get(mid, export=True))
        recovered = operate(workspace, "recover")
        assert all(a["resolved_at"] and a["acknowledged_at"] for a in recovered["alerts"])
        recurring = operate(workspace, "recur")
        incidents = [a for a in recurring["alerts"] if not a["resolved_at"]]
        assert len(incidents) == 1
        assert incidents[0]["kind"] == "repeated_failures"
        assert incidents[0]["acknowledged_at"] is None
        assert incidents[0]["id"] not in {a["id"] for a in seeded["alerts"]}
        final = encoded(TrackingStore(Jobs(workspace)).get(mid, export=True))
        (args.output / "alerts-final.json").write_bytes(final)
        restored = TrackingStore(Jobs(backup(workspace, "offline-alerts")))
        restored.recover()
        after = encoded(restored.get(mid, export=True))
        assert after == final
        receipt["alerts"] = {
            "acknowledgement_idempotent": True,
            "acknowledged_reopen_identical": True,
            "recovered": recovered["alerts"],
            "recurring": recurring["alerts"],
            "restored_export_identical": True,
            "export_sha256": hashlib.sha256(final).hexdigest(),
            "restored_export_sha256": hashlib.sha256(after).hexdigest(),
        }
        receipt["status"] = "passed"
    except Exception as error:
        receipt.update(status="failed", failure=repr(error))
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
