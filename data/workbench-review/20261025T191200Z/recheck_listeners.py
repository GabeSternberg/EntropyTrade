"""Full unchanged gate under normal per-command localhost-listener approval."""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

bundle = Path(__file__).resolve().parent
repo = bundle.parents[2]
baseline = json.loads((bundle / "clean-root/checks.json").read_text())
checkout = repo / baseline["checkout"]
manifest = json.loads((bundle / "clean-root/export-manifest.json").read_text())


def verify_source():
    for name, expected in manifest.items():
        assert hashlib.sha256((checkout / name).read_bytes()).hexdigest() == expected, name


verify_source()
result = {"commit": baseline["commit"], "tree": baseline["tree"],
          "cwd": baseline["checkout"], "command": ["make", "check"],
          "environment": baseline["environment"],
          "permission": "Normal per-command approval for localhost listeners; no sandbox bypass",
          "started_at": datetime.now(UTC).isoformat()}
with (bundle / "make-check-listeners.log").open("w") as output:
    command = subprocess.run(["make", "check"], cwd=checkout, env=baseline["environment"],
                             stdout=output, stderr=subprocess.STDOUT)
result.update(finished_at=datetime.now(UTC).isoformat(), exit_code=command.returncode,
              log="make-check-listeners.log",
              sha256=hashlib.sha256((bundle / "make-check-listeners.log").read_bytes()).hexdigest())
verify_source()
result["all_exported_files_unchanged"] = True
(bundle / "listener-check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "environment"}), flush=True)
raise SystemExit(command.returncode)
