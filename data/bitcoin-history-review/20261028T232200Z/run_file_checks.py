"""Additional bounded per-file checks; never a substitute for a passing make check.

Already stalled files retain their earlier failure receipts and are not rerun here.
Timeouts and permission failures remain failures, with their original pytest assertions.
"""
import json
import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

repo = Path(__file__).resolve().parents[3]
root = Path(__file__).resolve().parent
out = root / "per-file"
out.mkdir(exist_ok=False)
blocked = {
    "backend/tests/exchange/test_collector_service.py": "prior bounded collector stall",
    "backend/tests/unit/test_experiments_r4.py": "prior 45-second asyncio/AnyIO stack dump",
}
files = [p.relative_to(repo).as_posix() for p in sorted((repo / "backend/tests").rglob("test_*.py"))]
pending = [p for p in files if p not in blocked]
active = []
receipt = {"started_at": datetime.now(UTC).isoformat(), "not_rerun": blocked, "checks": []}
env = {"PATH": os.defpath, "PYTHONPATH": str(repo / "backend/src"), "TZ": "UTC", "TMPDIR": "/tmp",
       "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1",
       "OPENBLAS_NUM_THREADS": "1", "LOKY_MAX_CPU_COUNT": "1"}
while pending or active:
    while pending and len(active) < 3:
        file = pending.pop(0)
        name = file.replace("/", "__")
        log = (out / (name + ".log")).open("wb")
        command = [str(repo / ".venv/bin/python"), "-m", "pytest", file, "-q", "--tb=short",
                   "-o", "faulthandler_timeout=25", "--junitxml=" + str(out / (name + ".xml"))]
        child = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        active.append((child, time.monotonic(), log, file, False))
    next_active = []
    for child, start, log, file, terminated in active:
        elapsed = time.monotonic() - start
        if child.poll() is None and elapsed >= 40 and not terminated:
            os.killpg(child.pid, signal.SIGTERM)
            terminated = True
        if child.poll() is None and elapsed >= 45:
            os.killpg(child.pid, signal.SIGKILL)
        if child.poll() is None:
            next_active.append((child, start, log, file, terminated))
        else:
            log.close()
            receipt["checks"].append({"file": file, "exit_code": child.returncode,
                                      "timed_out": terminated, "seconds": round(elapsed, 3)})
            (root / "per-file-checks.json").write_text(json.dumps(receipt, indent=2) + "\n")
    active = next_active
    time.sleep(.1)
receipt["finished_at"] = datetime.now(UTC).isoformat()
(root / "per-file-checks.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"files": len(files), "executed_files": len(receipt["checks"]),
                  "passed_files": sum(c["exit_code"] == 0 for c in receipt["checks"]),
                  "not_rerun": blocked}, indent=2))
