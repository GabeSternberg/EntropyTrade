"""Retain stopped final browser workspaces, including newly acquired authentic source bytes."""

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from entropytrade.api.recovery import snapshot

OUTPUT = Path(__file__).resolve().parent
INSTALLATION = OUTPUT / "installation"


def main():
    acceptance = json.loads((OUTPUT / "acceptance.json").read_bytes())
    browser = next(step for step in acceptance["steps"] if step["name"] == "browser")
    if browser["status"] != "passed":
        raise ValueError("All browser procedures must finish successfully before retention")
    evidence = OUTPUT / "workspaces"
    evidence.mkdir(exist_ok=False)
    results = []
    for name, suffix in (("recovery-final", "-restored"), ("provider-final", "-provider"),
                         ("weather-final", "-weather-history")):
        workspace = INSTALLATION / "data/cache" / ("acceptance" + suffix)
        archive = INSTALLATION / "data/recovery" / (name + ".zip")
        result = snapshot(INSTALLATION, workspace, archive)
        retained = evidence / archive.name
        shutil.copyfile(archive, retained)
        with zipfile.ZipFile(retained) as zipped:
            if zipped.testzip() is not None:
                raise ValueError("Corrupt retained archive")
            manifest = json.loads(zipped.read("manifest.json"))
            for item in manifest["files"]:
                data = zipped.read("files/" + item["path"])
                if len(data) != item["bytes"] or "sha256:" + hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise ValueError("Retained workspace member differs: " + item["path"])
        (evidence / (name + "-manifest.json")).write_text(json.dumps(manifest, indent=2) + "\n")
        results.append({"name": name, "snapshot": result,
                        "archive": str(retained.relative_to(OUTPUT)),
                        "sha256": hashlib.sha256(retained.read_bytes()).hexdigest(),
                        "verified_files": len(manifest["files"]),
                        "limitation": "Stopped workspace retention and checksum verification; "
                                      "does not add browser or empirical validation."})
    (evidence / "receipt.json").write_text(json.dumps({"status": "passed", "archives": results},
                                                      indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
