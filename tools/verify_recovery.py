"""Offline recovery proof on an existing quiescent workspace; no network or new receipts."""

import argparse
import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

from entropytrade.api.jobs import Jobs, timestamp
from entropytrade.api.recovery import confined, restore, snapshot
from entropytrade.data.sources import file_hash
from entropytrade.tracking.replay import verify
from entropytrade.tracking.store import TrackingStore
from entropytrade.tracking.worker import reservations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--restored", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = confined(repo, args.output)
    output.mkdir(parents=True, exist_ok=False)
    store = TrackingStore(Jobs(confined(repo, args.workspace)))
    original = [store.get(m["id"], export=True) for m in store.history()]
    receipt: dict[str, object] = {
        "started_at": timestamp(),
        "status": "running",
        "limitation": (
            "Offline recovery of retained bytes; not current browser or ingestion acceptance"
        ),
    }
    try:
        receipt["snapshot"] = snapshot(repo, store.jobs.root, output / "workspace.zip")
        receipt["restore"] = restore(repo, output / "workspace.zip", args.restored)
        restored = TrackingStore(Jobs(args.restored.absolute()))
        with ZipFile(output / "workspace.zip") as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
        (output / "snapshot-manifest.json").write_text(json.dumps(manifest, indent=2))
        unchanged = []
        for item in manifest["files"]:
            # SQLite changes journal mode on normal app open; logical rows are compared below.
            if item["path"] not in {"jobs.sqlite", "registry.sqlite"}:
                if (
                    file_hash(restored.jobs.root / item["path"]) != item["sha256"]
                    or file_hash(store.jobs.root / item["path"]) != item["sha256"]
                ):
                    raise ValueError("source/restored bytes differ from manifest")
                unchanged.append(item["path"])
        for name in ("jobs.sqlite", "registry.sqlite"):
            if (store.jobs.root / name).is_file():
                with (
                    sqlite3.connect((store.jobs.root / name).as_uri() + "?mode=ro") as source,
                    sqlite3.connect((restored.jobs.root / name).as_uri() + "?mode=ro") as target,
                ):
                    if list(source.iterdump()) != list(target.iterdump()):
                        raise ValueError("restored database rows differ")
                source.close()
                target.close()
        restored.jobs.recover()
        restored.recover()
        exports = []
        replays = []
        for monitor in original:
            if monitor is None:
                raise ValueError("source monitor missing")
            after = restored.get(monitor["id"], export=True)
            # This real-receipt proof requires stopped, paused monitors; active/in-flight
            # recovery and nonempty reservations have separate controlled regressions.
            if monitor["status"] != "paused" or after != monitor:
                raise ValueError("paused export changed during recovery")
            if after is None or reservations(after) != reservations(monitor):
                raise ValueError("reservations changed during recovery")
            exports.append(monitor)
            replays.extend(
                {
                    "cycle_id": cycle["id"],
                    **verify(restored.jobs.root / "shadow" / monitor["id"] / cycle["id"]),
                }
                for cycle in monitor["cycles"]
                if cycle["status"] == "completed"
            )
        (output / "restored-monitors.json").write_text(json.dumps(exports, indent=2))
        receipt.update(
            status="passed",
            identical_files=unchanged,
            identical_database_rows=True,
            identical_paused_exports=True,
            replay=replays,
            submission_enabled=False,
        )
    except Exception as exc:
        receipt.update(status="failed", failure=str(exc))
        raise
    finally:
        receipt["finished_at"] = timestamp()
        (output / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
