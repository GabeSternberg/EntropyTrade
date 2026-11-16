"""Single bounded subprocess for continuous shadow work; restart always takes a fresh receipt."""

import json
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from entropytrade.api.runner import worker_environment
from entropytrade.data.sources import file_hash
from entropytrade.tracking.store import TrackingStore


class ShadowRunner:
    def __init__(
        self, store: TrackingStore, repo: Path, *, timeout: float = 240, lease_fd: int | None = None
    ) -> None:
        self.store, self.repo, self.timeout = store, repo, timeout
        self.lease_fds = () if lease_fd is None else (lease_fd,)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="shadow-monitor", daemon=True)
        self.next_alert_check = 0.0
        self.health_check: Callable[[], None] | None = None
        self.health_error: str | None = None

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=self.timeout + 5 if self.health_check is not None else 5)
            if self.thread.is_alive():
                raise RuntimeError("Shadow monitoring has not stopped; retain the workspace lease")

    def check_alerts(self) -> None:
        if time.monotonic() >= self.next_alert_check:
            self.store.alerts()
            self.next_alert_check = time.monotonic() + 5
            if self.health_check is not None:
                try:
                    self.health_check()
                    self.health_error = None
                except Exception as exc:  # noqa: BLE001 - a diagnostic failure cannot stop the runner
                    self.health_error = type(exc).__name__

    def run(self) -> None:
        while not self.stop.is_set():
            self.check_alerts()
            claim = self.store.claim()
            if claim is None:
                self.stop.wait(0.25)
                continue
            monitor_id, cycle_id = claim
            try:
                self.execute(monitor_id, cycle_id)
            except OSError:
                self.fail(monitor_id, cycle_id, "Worker could not start")

    def fail(self, monitor_id: str, cycle_id: str, detail: str) -> None:
        if not self.store.running(monitor_id, cycle_id):
            return
        root = self.store.jobs.root / "shadow" / monitor_id / cycle_id
        root.mkdir(parents=True, exist_ok=True)
        result_file = root / "result.json"
        if result_file.is_file():
            # A worker can die after writing its outbox but before the account transaction.
            # Preserve those bytes as uncommitted evidence, never as a simulated fill commit.
            uncommitted = root / "uncommitted-result.json"
            if uncommitted.exists():
                raise ValueError("uncommitted worker evidence already exists")
            result_file.rename(uncommitted)
        result = {
            "detail": detail,
            "failure": detail,
            "submission_enabled": False,
            "decisions": [],
            "model_refusals": {"worker": "No committed computation: " + detail},
            "artifacts": [
                {
                    "path": p.relative_to(root).as_posix(),
                    "sha256": file_hash(p),
                    "bytes": p.stat().st_size,
                }
                for p in sorted(root.rglob("*"))
                if p.is_file()
            ],
        }
        capture = root / "public/capture.json"
        if capture.is_file():
            # Interrupted bytes remain indexed even if normalization did not finish.
            with suppress(ValueError, OSError):
                result["capture"] = json.loads(capture.read_text())
        result_file.write_text(json.dumps(result, sort_keys=True, indent=2))
        self.store.finish(monitor_id, cycle_id, result, failed=True)

    def execute(self, monitor_id: str, cycle_id: str) -> None:
        command = [
            sys.executable,
            "-m",
            "entropytrade.tracking.worker",
            "--repo",
            str(self.repo),
            "--workspace",
            str(self.store.jobs.root),
            "--monitor",
            monitor_id,
            "--cycle",
            cycle_id,
        ]
        with subprocess.Popen(  # noqa: S603 - fixed module, UUID arguments, no shell
            command,
            cwd=self.repo,
            env=worker_environment(self.repo, self.store.jobs.root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=self.lease_fds,
        ) as process:
            started = time.monotonic()
            while process.poll() is None:
                self.check_alerts()
                active = self.store.running(monitor_id, cycle_id)
                if self.stop.is_set() or not active:
                    process.kill()
                    process.wait()
                    # Shutdown leaves the schedule active; next startup records interruption.
                    if self.stop.is_set():
                        self.store.recover()
                    return
                if time.monotonic() - started > self.timeout:
                    process.kill()
                    process.wait()
                    self.fail(
                        monitor_id,
                        cycle_id,
                        "Worker exceeded the four-minute budget; partial receipts retained",
                    )
                    return
                self.stop.wait(0.2)
        self.fail(
            monitor_id,
            cycle_id,
            "Worker exited without a committed cycle; partial receipts retained",
        )
