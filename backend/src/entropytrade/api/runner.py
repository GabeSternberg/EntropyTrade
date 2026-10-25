"""One isolated credential-free process at a time, with cancellation and wall-time bounds."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from entropytrade.api.jobs import Jobs


def worker_environment(repo: Path, workspace: Path) -> dict[str, str]:
    # An allowlist, never a copy of the parent's credentials or SDK configuration.
    return {
        "PATH": os.defpath,
        "PYTHONPATH": str(repo / "backend" / "src"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(workspace),
        "MPLCONFIGDIR": str(workspace / "matplotlib"),
        "MLFLOW_TRACKING_URI": (workspace / "mlflow").as_uri(),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "TZ": "UTC",
    }


class Runner:
    def __init__(self, jobs: Jobs, repo: Path, *, timeout: float = 600) -> None:
        self.jobs, self.repo, self.timeout = jobs, repo, timeout
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name="research-queue", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=5)

    def run(self) -> None:
        while not self.stop.is_set():
            job_id = self.jobs.queued()
            if job_id is None:
                self.stop.wait(0.25)
                continue
            if not self.jobs.update(job_id, "starting", "Starting isolated research worker"):
                continue
            try:
                self.execute(job_id)
            except OSError:
                self.jobs.update(job_id, "failed", "Worker could not start", status="failed")

    def execute(self, job_id: str) -> None:
        command = [
            sys.executable,
            "-m",
            "entropytrade.api.worker",
            "--workspace",
            str(self.jobs.root),
            "--repo",
            str(self.repo),
            "--job",
            job_id,
        ]
        with subprocess.Popen(  # noqa: S603 - fixed module and validated UUID, no shell
            command,
            cwd=self.repo,
            env=worker_environment(self.repo, self.jobs.root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as process:
            started = time.monotonic()
            while process.poll() is None:
                job = self.jobs.get(job_id)
                if self.stop.is_set() or not job or job["status"] == "cancelled":
                    process.kill()
                    process.wait()
                    self.jobs.update(
                        job_id,
                        "interrupted",
                        "Worker stopped with the server",
                        status="interrupted",
                    )
                    return
                if time.monotonic() - started > self.timeout:
                    process.kill()
                    process.wait()
                    self.jobs.update(
                        job_id,
                        "failed",
                        "Worker exceeded the ten-minute wall-time budget",
                        status="failed",
                    )
                    return
                self.stop.wait(0.2)
        job = self.jobs.get(job_id)
        if job and job["status"] == "running":
            self.jobs.update(
                job_id,
                "failed",
                "Worker exited without a completed result; check dependencies",
                status="failed",
            )
