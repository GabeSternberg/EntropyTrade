"""Test the reviewed source plus the explicitly hashed acceptance deadlock fix."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path

bundle = Path(__file__).resolve().parent
repo = bundle.parents[2]
baseline = json.loads((bundle / "clean-root/checks.json").read_text())
checkout = repo / baseline["checkout"]
manifest = json.loads((bundle / "clean-root/export-manifest.json").read_text())
for name, expected in manifest.items():
    assert hashlib.sha256((checkout / name).read_bytes()).hexdigest() == expected, name
overlay = ["backend/src/entropytrade/api/jobs.py", "backend/tests/integration/test_workbench_process.py"]
for name in overlay:
    shutil.copyfile(repo / name, checkout / name)
    manifest[name] = hashlib.sha256((checkout / name).read_bytes()).hexdigest()
patch = subprocess.check_output(["git", "diff", "--binary", "HEAD", "--", *overlay], cwd=repo)
(bundle / "candidate.patch").write_bytes(patch)
(bundle / "candidate-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
receipt = {"base_commit": baseline["commit"], "base_tree": baseline["tree"],
           "candidate": "uncommitted acceptance fix; not the reviewed commit",
           "code_patch_sha256": hashlib.sha256(patch).hexdigest(), "overlay": overlay,
           "cwd": baseline["checkout"], "environment": baseline["environment"],
           "permission": "Normal per-command localhost-listener approval; locked offline dependencies",
           "started_at": datetime.now(UTC).isoformat(), "commands": []}


def save():
    (bundle / "candidate-checks.json").write_text(json.dumps(receipt, indent=2) + "\n")


save()
for name, command in [("candidate-sync", ["uv", "sync", "--locked"]),
                      ("candidate-make-check", ["make", "check"]),
                      ("candidate-js-syntax", ["node", "--check", "frontend/src/app.js"]),
                      ("candidate-frontend", ["node", "--test", "frontend/tests/acquisition.test.cjs"])]:
    started = datetime.now(UTC).isoformat()
    log = bundle / (name + ".log")
    timed_out = False
    with log.open("w") as output:
        with subprocess.Popen(command, cwd=checkout, env=baseline["environment"], stdout=output,
                              stderr=subprocess.STDOUT, start_new_session=True) as process:
            try:
                code = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    receipt["commands"].append({"name": name, "command": command, "started_at": started,
                                "finished_at": datetime.now(UTC).isoformat(), "exit_code": code,
                                "timed_out": timed_out, "log": log.name,
                                "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
    save()
    print(f"{name}: exit {code}", flush=True)
    if name == "candidate-sync" and code:
        break
receipt["modified_exported_files"] = [name for name, expected in manifest.items()
                                      if hashlib.sha256((checkout / name).read_bytes()).hexdigest() != expected]
receipt["finished_at"] = datetime.now(UTC).isoformat()
save()
assert not receipt["modified_exported_files"]
raise SystemExit(1 if any(c["exit_code"] for c in receipt["commands"]) else 0)
