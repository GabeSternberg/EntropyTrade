"""One isolated worker; only opted-in research can inherit its dedicated credential."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from entropytrade.api.jobs import COURSE_MODE, Jobs, validate_request

RESEARCH_KEY_VARIABLE = "ENTROPYTRADE_RESEARCH_API_KEY"
COURSE_KEY_VARIABLE = "GEMINI_API_KEY"


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
    def __init__(
        self, jobs: Jobs, repo: Path, *, timeout: float = 600, lease_fd: int | None = None
    ) -> None:
        self.jobs, self.repo, self.timeout = jobs, repo, timeout
        self.lease_fds = () if lease_fd is None else (lease_fd,)
        self.stop = threading.Event()
        self._course_keys: dict[str, str] = {}
        self._course_key_lock = threading.Lock()
        self.thread = threading.Thread(target=self.run, name="research-queue", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self, *, timeout: float = 5) -> None:
        self.stop.set()
        with self._course_key_lock:
            self._course_keys.clear()
        if self.thread.ident is not None:
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                raise RuntimeError(
                    "legacy research worker has not stopped; workspace lease retained"
                )

    def submit_course(self, key: str) -> str:
        # The worker waits on the same lock before consuming the credential.
        with self._course_key_lock:
            if self.stop.is_set():
                raise ValueError("The research worker has stopped.")
            job_id, created = self.jobs.create_course()
            if created and key:
                self._course_keys[job_id] = key
        return job_id

    def forget_course_key(self, job_id: str) -> str | None:
        with self._course_key_lock:
            return self._course_keys.pop(job_id, None)

    def run(self) -> None:
        while not self.stop.is_set():
            job_id = self.jobs.queued()
            if job_id is None:
                self.stop.wait(0.25)
                continue
            if not self.jobs.update(job_id, "starting", "Starting isolated research worker"):
                self.forget_course_key(job_id)
                continue
            try:
                self.execute(job_id)
            except (OSError, ValueError):
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
        course_key = self.forget_course_key(job_id)
        job = self.jobs.get(job_id)
        if job is None or job["status"] != "running":
            return
        request = validate_request(job["request"], stored=True)
        environment = worker_environment(self.repo, self.jobs.root)
        # Never forward ambient SDK/exchange credentials, HOME, base URLs or key files.
        # Missing research credentials are handled durably by the research pipeline.
        if request.get("reasoning") == "provider" and RESEARCH_KEY_VARIABLE in os.environ:
            environment[RESEARCH_KEY_VARIABLE] = os.environ[RESEARCH_KEY_VARIABLE]
        course = request["mode"] == COURSE_MODE
        if course:
            course_key = course_key or os.environ.get(COURSE_KEY_VARIABLE, "").strip()
            if course_key:
                environment[COURSE_KEY_VARIABLE] = course_key
        if course or request.get("reasoning") == "provider":
            for name in (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "NO_PROXY",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
            ):
                if name in os.environ:
                    environment[name] = os.environ[name]
        with subprocess.Popen(  # noqa: S603 - fixed module and validated UUID, no shell
            command,
            cwd=self.repo,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=self.lease_fds,
        ) as process:
            if course:
                environment.pop(COURSE_KEY_VARIABLE, None)
                course_key = None
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
