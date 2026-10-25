"""Exercise the HTTP boundary without opening a listener or requiring model packages."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self, cast
from uuid import uuid4

import pytest

from entropytrade.api.jobs import Jobs, identifier, validate_request
from entropytrade.api.runner import Runner, worker_environment
from entropytrade.api.server import Handler, WorkbenchServer, workspace_path

REPO = Path(__file__).resolve().parents[3]
REQUEST = {"idea": "Test forecast revisions", "family": "weather", "mode": "recorded"}


class MemorySocket:
    def __init__(self, request: bytes) -> None:
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()

    def makefile(self, mode: str, *_args: object) -> io.BytesIO:
        return self.input if "r" in mode else self.output

    def sendall(self, value: bytes) -> None:
        self.output.write(value)

    def settimeout(self, value: float) -> None:
        del value


def exchange(
    server: WorkbenchServer,
    path: str,
    *,
    method: str = "GET",
    body: object = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    payload = json.dumps(body).encode() if body is not None else b""
    fields = {
        "Host": "127.0.0.1:43128",
        "Content-Type": "application/json",
        "Content-Length": str(len(payload)),
        **(headers or {}),
    }
    request = f"{method} {path} HTTP/1.0\r\n"
    request += "".join(f"{k}: {v}\r\n" for k, v in fields.items()) + "\r\n"
    socket = MemorySocket(request.encode() + payload)
    Handler(cast("Any", socket), ("127.0.0.1", 12345), server)
    head, result = socket.output.getvalue().split(b"\r\n\r\n", 1)
    lines = head.decode().split("\r\n")
    return int(lines[0].split()[1]), dict(line.split(": ", 1) for line in lines[1:]), result


@pytest.fixture
def server(tmp_path: Path) -> WorkbenchServer:
    return cast(
        "WorkbenchServer",
        SimpleNamespace(
            repo=REPO,
            jobs=Jobs(tmp_path),
            server_port=43128,
            token=str(uuid4()),
        ),
    )


def test_idea_to_saved_review_and_download_survive_reopen(server: WorkbenchServer) -> None:
    status, headers, body = exchange(server, "/api/catalog")
    catalog = json.loads(body)
    assert status == 200
    assert not catalog["submission_enabled"]
    assert not catalog["provider_enabled"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    status, _, body = exchange(
        server,
        "/api/jobs",
        method="POST",
        body=REQUEST,
        headers={"X-EntropyTrade-CSRF": catalog["csrf_token"]},
    )
    assert status == 202
    job_id = json.loads(body)["id"]
    jobs = Jobs(server.jobs.root)
    assert jobs.update(job_id, "data", "Inspecting actual evidence")
    review = {"data_kind": "real", "report": "INSUFFICIENT_DATA: zero eligible source vintages"}
    assert jobs.update(job_id, "completed", "Saved", status="completed", result=review)
    assert not jobs.update(job_id, "late-worker", "Cannot overwrite", status="running")
    status, _, body = exchange(server, f"/api/jobs/{job_id}")
    saved = json.loads(body)
    assert status == 200
    assert saved["result"] == review
    assert [e["stage"] for e in saved["events"]] == ["queued", "data", "completed"]
    status, _, body = exchange(server, f"/api/jobs/{job_id}/report")
    assert status == 200
    assert body.decode() == review["report"]
    status, _, body = exchange(server, f"/api/jobs/{job_id}/review")
    assert status == 200
    assert json.loads(body) == review
    status, _, body = exchange(server, "/api/jobs")
    assert status == 200
    assert json.loads(body)[0]["request"] == REQUEST


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.invalid:43128"},
        {"Origin": "https://attacker.invalid"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "null"},
    ],
)
def test_cross_origin_reads_and_writes_fail(
    server: WorkbenchServer, headers: dict[str, str]
) -> None:
    assert exchange(server, "/api/catalog", headers=headers)[0] == 403
    assert (
        exchange(
            server,
            "/api/jobs",
            method="POST",
            body=REQUEST,
            headers={"X-EntropyTrade-CSRF": server.token, **headers},
        )[0]
        == 403
    )
    assert server.jobs.history() == []


def test_missing_csrf_and_oversized_or_injected_requests_fail(server: WorkbenchServer) -> None:
    assert exchange(server, "/api/jobs", method="POST", body=REQUEST)[0] == 403
    token = {"X-EntropyTrade-CSRF": server.token}
    for body in (
        {**REQUEST, "provider": "openai"},
        {**REQUEST, "root": "/etc"},
        {**REQUEST, "mode": "live"},
        {**REQUEST, "idea": "x" * 6001},
    ):
        assert exchange(server, "/api/jobs", method="POST", body=body, headers=token)[0] == 400
    assert (
        exchange(
            server,
            "/api/jobs",
            method="POST",
            body=REQUEST,
            headers={**token, "Content-Length": "25000"},
        )[0]
        == 400
    )
    assert (
        exchange(
            server,
            "/api/jobs",
            method="POST",
            body=REQUEST,
            headers={**token, "Transfer-Encoding": "chunked"},
        )[0]
        == 415
    )
    for path in (
        "/../../AGENTS.md",
        "/api/jobs/../../AGENTS.md",
        "/api/orders",
        "/api/credentials",
    ):
        assert exchange(server, path)[0] == 404


def test_cancel_terminal_race_and_restart_keep_history(server: WorkbenchServer) -> None:
    job_id = server.jobs.create(REQUEST)
    server.jobs.update(job_id, "starting", "Worker starting")
    assert (
        exchange(
            server,
            f"/api/jobs/{job_id}/cancel",
            method="POST",
            body={},
            headers={"X-EntropyTrade-CSRF": server.token},
        )[0]
        == 200
    )
    assert not server.jobs.update(
        job_id,
        "done",
        "Late completion",
        status="completed",
        result={"report": "must not replace cancellation"},
    )
    second = server.jobs.create(REQUEST)
    server.jobs.recover()
    assert server.jobs.get(job_id)["status"] == "cancelled"  # type: ignore[index]
    assert server.jobs.get(second)["status"] == "interrupted"  # type: ignore[index]
    assert server.jobs.queued() is None


def test_queue_cap_validation_and_no_arbitrary_family_modes(tmp_path: Path) -> None:
    jobs = Jobs(tmp_path)
    for _ in range(8):
        jobs.create(REQUEST)
    with pytest.raises(ValueError, match="queue is full"):
        jobs.create(REQUEST)
    invalid_requests: tuple[tuple[object, str], ...] = (
        ([], "provide only idea, family and mode"),
        ({**REQUEST, "idea": 9}, "request values must be strings"),
        ({**REQUEST, "idea": " "}, "idea must contain 1-6000 characters"),
        (
            {**REQUEST, "family": "bitcoin"},
            "Bitcoin currently supports public forward capture only",
        ),
    )
    for request, reason in invalid_requests:
        with pytest.raises(ValueError, match=reason):
            validate_request(request)
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        identifier("../../runs")
    assert identifier(str(uuid4()))


def test_credential_free_worker_environment_and_confined_workspace(tmp_path: Path) -> None:
    env = worker_environment(REPO, tmp_path)
    assert set(env) == {
        "PATH",
        "PYTHONPATH",
        "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE",
        "TMPDIR",
        "MPLCONFIGDIR",
        "MLFLOW_TRACKING_URI",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "TZ",
    }
    assert not any("KEY" in key or "TOKEN" in key or key == "HOME" for key in env)
    assert workspace_path(REPO, REPO / "data/cache/test") == REPO / "data/cache/test"
    for path in (REPO, REPO / "data/cache", tmp_path):
        with pytest.raises(ValueError, match="workspace"):
            workspace_path(REPO, path)
    Runner(Jobs(tmp_path), REPO).close()


def test_all_static_assets_are_served_with_no_external_scripts(server: WorkbenchServer) -> None:
    for path in ("/", "/app.js", "/style.css"):
        status, headers, body = exchange(server, path)
        assert status == 200
        assert body
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Content-Type-Options"] == "nosniff"
    script = (REPO / "frontend/src/app.js").read_text()
    assert "innerHTML" not in script
    assert "eval(" not in script


class ControlledProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode
        self.killed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self) -> int:
        assert self.returncode is not None
        return self.returncode


@pytest.mark.parametrize("condition", ["timeout", "shutdown", "cancelled", "crash"])
def test_worker_deadline_shutdown_cancellation_and_crash_are_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    jobs = Jobs(tmp_path)
    job_id = jobs.create(REQUEST)
    jobs.update(job_id, "starting", "Worker starting")
    process = ControlledProcess(1 if condition == "crash" else None)
    launches: list[tuple[list[str], dict[str, Any]]] = []

    def launch(command: list[str], **kwargs: Any) -> ControlledProcess:
        launches.append((command, kwargs))
        return process

    monkeypatch.setattr("entropytrade.api.runner.subprocess.Popen", launch)
    runner = Runner(jobs, REPO, timeout=0)
    if condition == "shutdown":
        runner.stop.set()
    if condition == "cancelled":
        jobs.update(job_id, "cancelled", "Cancelled", status="cancelled")
    runner.execute(job_id)
    job = jobs.get(job_id)
    assert job is not None
    expected = (
        "interrupted"
        if condition == "shutdown"
        else ("cancelled" if condition == "cancelled" else "failed")
    )
    assert job["status"] == expected
    assert job["result"] is None
    assert process.killed == (condition != "crash")
    command, options = launches[0]
    assert command[1:3] == ["-m", "entropytrade.api.worker"]
    assert command[-1] == job_id
    assert "shell" not in options
    assert options["env"] == worker_environment(REPO, tmp_path)
