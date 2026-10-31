"""Restore the stopped browser workspaces and compare their actual downloaded evidence."""

import hashlib
import json
import shutil
from pathlib import Path

from entropytrade.api.jobs import Jobs
from entropytrade.api.recovery import restore, snapshot
from entropytrade.tracking.accounting import verify_export
from entropytrade.tracking.store import TrackingStore

OUTPUT = Path(__file__).resolve().parent
INSTALLATION = OUTPUT / "installation"


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def main():
    output = OUTPUT / "paper-offline-restore"
    output.mkdir(exist_ok=False)
    receipt = {
        "status": "running", "browser_workspaces": [],
        "limitation": "Offline restore of the stopped actual browser workspaces/downloads. "
                      "No new page interaction, collection or empirical evidence.",
    }
    try:
        for name in ("controlled", "authentic"):
            downloaded = json.loads((OUTPUT / "browser" / name / "shadow.json").read_bytes())
            workspace = INSTALLATION / "data/cache" / ("acceptance-" + name)
            archive = INSTALLATION / "data/recovery" / ("paper-" + name + ".zip")
            restored = workspace.with_name(workspace.name + "-offline-restored")
            snapshot(INSTALLATION, workspace, archive)
            restore(INSTALLATION, archive, restored)
            shutil.copyfile(archive, output / archive.name)
            store = TrackingStore(Jobs(restored))
            store.recover()
            exported = store.get(downloaded["id"], export=True)
            if encoded(exported) != encoded(downloaded):
                raise ValueError(name + " restored export differs from browser download")
            replay = verify_export(exported)
            if not replay["verified"]:
                raise ValueError(name + " restored account cannot reproduce")
            (output / (name + "-restored.json")).write_bytes(encoded(exported))
            receipt["browser_workspaces"].append({
                "name": name, "restored_export_identical_to_download": True,
                "export_sha256": hashlib.sha256(encoded(exported)).hexdigest(),
                "archive": archive.name,
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "account_reproduction": replay,
            })
        alerts_archive = INSTALLATION / "data/cache/operator-acceptance-alerts.zip"
        shutil.copyfile(alerts_archive, OUTPUT / "browser/alerts/workspace.zip")
        receipt["alerts_browser_archive_retained"] = {
            "path": "browser/alerts/workspace.zip",
            "sha256": hashlib.sha256(alerts_archive.read_bytes()).hexdigest(),
        }
        receipt["status"] = "passed"
    except Exception as exc:
        receipt.update(status="failed", failure=repr(exc))
        raise
    finally:
        (output / "receipt.json").write_bytes(encoded(receipt))
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
