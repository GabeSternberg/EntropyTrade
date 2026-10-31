"""Loopback-only HTTP workbench with same-origin writes and a fixed asset allowlist."""

import argparse
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from entropytrade.api.jobs import Jobs, identifier, provider_config
from entropytrade.api.runner import Runner
from entropytrade.api.workspace import acquire_workspace
from entropytrade.api.workspace import workspace_path as workspace_path
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore
from entropytrade.weather.label_service import LabelService

ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = True

    def __init__(
        self,
        repo: Path,
        workspace: Path,
        *,
        port: int = 43128,
        research_provider: dict[str, str] | None = None,
    ) -> None:
        self.repo = repo.resolve()
        self.research_provider = provider_config(research_provider) if research_provider else None
        root = workspace_path(self.repo, workspace)
        self.lock = acquire_workspace(root)
        try:
            self.jobs = Jobs(root)
            self.runner = Runner(self.jobs, self.repo, lease_fd=self.lock.fileno())
            self.tracking = TrackingStore(self.jobs)
            self.shadow = ShadowRunner(self.tracking, self.repo, lease_fd=self.lock.fileno())
            self.weather_lock = threading.Lock()
            self.labels = LabelService(self.jobs.root, self.weather_lock)
            self.labels.recover()
            self.labels.scheduler.validate()
            super().__init__(("127.0.0.1", port), Handler)
            self.jobs.recover()
            self.tracking.recover()
        except BaseException:
            self.lock.close()
            raise
        self.token = secrets.token_urlsafe(32)
        self.labels.thread.start()

    def server_close(self) -> None:
        self.labels.close()
        self.runner.close()
        self.shadow.close()
        super().server_close()
        self.lock.close()


class Handler(BaseHTTPRequestHandler):
    server: WorkbenchServer
    timeout = 5

    def log_message(self, format: str, *args: object) -> None:
        # Prompts and URLs are private research history, not console access logs.
        del format, args

    def safe_origin(self) -> bool:
        host = self.headers.get("Host", "")
        port = self.server.server_port
        if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            return False
        origin = self.headers.get("Origin")
        return self.headers.get("Sec-Fetch-Site") != "cross-site" and (
            origin is None or origin == "http://" + host
        )

    def send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(body)

    def document(self, status: int, value: object) -> None:
        self.send(status, json.dumps(value, allow_nan=False).encode())

    def job_route(self) -> tuple[str, str] | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) not in {3, 4} or parts[:2] != ["api", "jobs"]:
            return None
        try:
            job_id = identifier(parts[2])
        except ValueError:
            return None
        return job_id, parts[3] if len(parts) == 4 else ""

    def monitor_route(self) -> tuple[str, str] | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) not in {3, 4} or parts[:2] != ["api", "monitors"]:
            return None
        try:
            return identifier(parts[2]), parts[3] if len(parts) == 4 else ""
        except ValueError:
            return None

    def do_GET(self) -> None:
        if not self.safe_origin():
            self.document(403, {"error": "localhost same-origin access required"})
            return
        path = urlsplit(self.path).path
        if path in ASSETS:
            name, kind = ASSETS[path]
            self.send(200, (self.server.repo / "frontend" / "src" / name).read_bytes(), kind)
        elif path == "/api/catalog":
            self.document(
                200,
                {
                    "csrf_token": self.server.token,
                    "reasoning": "local_templates; synthetic mode uses explicit mock proposals",
                    "families": ["weather", "bitcoin"],
                    "modes": ["recorded", "public", "synthetic", "history", "weather_history"],
                    "provider_enabled": bool(getattr(self.server, "research_provider", None)),
                    "research_provider": getattr(self.server, "research_provider", None),
                    "submission_enabled": False,
                    "limits": {"queued_jobs": 8, "worker_seconds": 600, "synthetic_days": 240},
                },
            )
        elif path == "/api/fees" or path.startswith("/api/fees/"):
            from entropytrade.execution.fee_evidence import FeeEvidenceStore

            try:
                store = FeeEvidenceStore(self.server.jobs.root)
                if path == "/api/fees":
                    self.document(
                        200,
                        {
                            "submission_enabled": False,
                            "versions": [v.summary() for v in store.snapshot()],
                        },
                    )
                else:
                    fee_route = path.removeprefix("/api/fees/").split("/")
                    version = store.get("sha256:" + fee_route[0])
                    if len(fee_route) == 1:
                        self.document(200, version.model_dump(mode="json"))
                    elif (
                        len(fee_route) == 3 and fee_route[1] == "sources" and fee_route[2].isdigit()
                    ):
                        # Always download opaque original bytes, including HTML error bodies.
                        self.send(
                            200,
                            version.sources[int(fee_route[2])].body(),
                            "application/octet-stream",
                        )
                    else:
                        self.document(404, {"error": "not found"})
            except (ValueError, OSError, IndexError) as exc:
                self.document(
                    409, {"error": "Fee evidence verification failed: " + type(exc).__name__}
                )
        elif path == "/api/weather/schedules" or path.startswith("/api/weather/schedules/"):
            try:
                scheduler = self.server.labels.scheduler
                self.document(
                    200,
                    scheduler.catalog()
                    if path == "/api/weather/schedules"
                    else scheduler.summary(
                        scheduler.get(path.removeprefix("/api/weather/schedules/"))
                    ),
                )
            except (ValueError, OSError, KeyError, TypeError):
                self.document(409, {"error": "Forward validation state verification failed"})
        elif path == "/api/weather/labels" or path.startswith("/api/weather/labels/"):
            try:
                if path == "/api/weather/labels":
                    self.document(200, self.server.labels.catalog())
                else:
                    label_version = "sha256:" + path.removeprefix("/api/weather/labels/")
                    from entropytrade.weather.labels import load_batch

                    batch = load_batch(self.server.labels.batch_path(label_version))
                    self.document(200, batch.model_dump(mode="json"))
            except (ValueError, OSError, KeyError, TypeError):
                self.document(409, {"error": "Weather label evidence verification failed"})
        elif path == "/api/weather/partitions":
            self.document(200, self.server.jobs.weather_partitions())
        elif path == "/api/weather/datasets":
            from entropytrade.weather.history import load_snapshot

            try:
                root = self.server.jobs.root / "runs/weather-datasets"
                snapshots = [load_snapshot(p) for p in sorted(root.glob("[0-9a-f]" * 64))]
                self.document(
                    200,
                    [
                        {
                            k: s[k]
                            for k in (
                                "dataset_id",
                                "capture_count",
                                "observation_count",
                                "readiness",
                            )
                        }
                        for s in snapshots
                    ],
                )
            except (ValueError, OSError, KeyError) as exc:
                self.document(
                    400,
                    {
                        "error": "Retained weather dataset verification failed "
                        f"({type(exc).__name__})"
                    },
                )
        elif path == "/api/jobs":
            self.document(200, self.server.jobs.history())
        elif path == "/api/monitors":
            self.document(200, self.server.tracking.history())
        elif path == "/api/alerts":
            self.document(
                200, {"alerts": self.server.tracking.alerts(), "submission_enabled": False}
            )
        elif path.startswith("/api/monitors/"):
            route = self.monitor_route()
            try:
                monitor = (
                    self.server.tracking.get(route[0], export=route[1] == "export")
                    if route
                    else None
                )
            except ValueError:
                self.document(
                    409, {"error": "Paper account verification failed; inspect workspace"}
                )
                return
            if monitor is None or route is None or route[1] not in {"", "export", "paper"}:
                self.document(404, {"error": "not found"})
            elif route[1] == "paper":
                self.document(
                    200,
                    {
                        "account": monitor["paper_account"],
                        "summary": monitor["paper_summary"],
                        "submission_enabled": False,
                    },
                )
            else:
                self.document(200, monitor)
        else:
            route = self.job_route()
            job = self.server.jobs.get(route[0]) if route else None
            if (
                job is None
                or route is None
                or route[1] not in {"", "report", "review", "shadow-inputs", "fee-evidence"}
            ):
                self.document(404, {"error": "not found"})
            elif route[1] == "report":
                self.send(
                    200,
                    ((job["result"] or {}).get("report", "Run has no report yet.")).encode(),
                    "text/plain; charset=utf-8",
                )
            elif route[1] in {"shadow-inputs", "fee-evidence"}:
                artifact_name = (
                    "shadow-replay.json" if route[1] == "shadow-inputs" else "fee-evidence.json"
                )
                from entropytrade.data.sources import file_hash

                artifact = next(
                    (
                        a
                        for a in (job["result"] or {}).get("artifacts", [])
                        if a["path"] == artifact_name
                    ),
                    None,
                )
                target = self.server.jobs.root / "runs" / route[0] / "workflow" / artifact_name
                if artifact is None:
                    self.document(404, {"error": "run has no retained shadow inputs"})
                elif (
                    not target.is_file()
                    or target.is_symlink()
                    or file_hash(target) != artifact["sha256"]
                ):
                    self.document(
                        409, {"error": "retained shadow inputs failed checksum verification"}
                    )
                else:
                    self.send(200, target.read_bytes())
            elif route[1] == "review":
                self.document(200, job["result"])
            else:
                self.document(200, job)

    def do_POST(self) -> None:
        if not self.safe_origin() or not secrets.compare_digest(
            self.headers.get("X-EntropyTrade-CSRF", ""), self.server.token
        ):
            self.document(403, {"error": "same-origin token required"})
            return
        if self.headers.get("Content-Type") != "application/json" or self.headers.get(
            "Transfer-Encoding"
        ):
            self.document(415, {"error": "use application/json without transfer encoding"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 24_000:
                raise ValueError("request exceeds size budget or is empty")
            value = json.loads(self.rfile.read(size))
            if self.path == "/api/weather/schedules":
                self.document(202, self.server.labels.scheduler.create(value))
                return
            if self.path.startswith("/api/weather/schedules/"):
                parts = self.path.removeprefix("/api/weather/schedules/").split("/")
                if len(parts) != 2 or value != {}:
                    raise ValueError("schedule control requires ID, pause/resume and empty body")
                self.document(200, self.server.labels.scheduler.control(parts[0], parts[1]))
                return
            if self.path == "/api/weather/labels":
                self.document(202, self.server.labels.create(value))
                return
            if self.path == "/api/weather/datasets":
                from entropytrade.tracking.history import anchor
                from entropytrade.weather.history import build_snapshot

                if not isinstance(value, dict) or set(value) - {
                    "partition_id",
                    "outcome_partition_id",
                    "partition_ids",
                    "outcome_partition_ids",
                }:
                    raise ValueError("select history and outcome partition IDs only")
                cohort = bool({"partition_ids", "outcome_partition_ids"} & set(value))
                if cohort and {"partition_id", "outcome_partition_id"} & set(value):
                    raise ValueError("select a single partition or a cohort")
                if cohort and any(not isinstance(v, list) for v in value.values()):
                    raise ValueError("cohort partition IDs must be arrays")
                if not cohort and any(not isinstance(v, str) for v in value.values()):
                    raise ValueError("partition IDs must be strings")

                if not self.server.weather_lock.acquire(blocking=False):
                    raise ValueError("a weather snapshot is already being built")
                try:
                    if cohort:
                        from entropytrade.weather.cohorts import build_cohort

                        snapshot = build_cohort(
                            self.server.jobs,
                            value.get("partition_ids"),
                            value.get("outcome_partition_ids"),
                        )
                    else:
                        captures, outcomes, protected = self.server.jobs.weather_inputs(
                            value.get("partition_id"), value.get("outcome_partition_id")
                        )
                        from entropytrade.weather.label_service import batches as label_batches

                        snapshot = build_snapshot(
                            self.server.jobs.root / "runs/weather-datasets",
                            captures,
                            outcome_roots=outcomes,
                            scalar_batches=label_batches(self.server.jobs.root),
                            protected_events=protected,
                            frozen_anchor=anchor(self.server.jobs),
                            selection=value or None,
                        )
                    self.document(
                        201,
                        {
                            k: snapshot[k]
                            for k in (
                                "dataset_id",
                                "capture_count",
                                "observation_count",
                                "readiness",
                            )
                        },
                    )
                finally:
                    self.server.weather_lock.release()
                return
            if self.path == "/api/jobs":
                job_id = self.server.jobs.create(
                    value, provider=getattr(self.server, "research_provider", None)
                )
                self.document(202, {"id": job_id})
                return
            if self.path == "/api/monitors":
                monitor_id = self.server.tracking.create(value)
                self.document(202, {"id": monitor_id})
                return
            monitor_route = self.monitor_route()
            if monitor_route and monitor_route[1] == "acknowledge":
                if (
                    not isinstance(value, dict)
                    or set(value) != {"alert_id"}
                    or not isinstance(value["alert_id"], str)
                ):
                    raise ValueError("provide alert_id only")
                self.server.tracking.acknowledge(monitor_route[0], value["alert_id"])
                self.document(200, {"id": monitor_route[0]})
                return
            if monitor_route and monitor_route[1] in {"pause", "resume"} and value == {}:
                self.server.tracking.control(*monitor_route)
                self.document(200, {"id": monitor_route[0]})
                return
            route = self.job_route()
            if route and route[1] == "cancel" and value == {}:
                job = self.server.jobs.get(route[0])
                if job is not None:
                    changed = self.server.jobs.update(
                        route[0], "cancelled", "Cancelled by user", status="cancelled"
                    )
                    self.document(200, {"cancelled": changed})
                    return
        except (ValueError, UnicodeError, OSError, KeyError) as exc:
            self.document(400, {"error": str(exc)})
            return
        self.document(404, {"error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description="EntropyTrade private localhost workbench")
    parser.add_argument("--port", type=int, default=43128)
    parser.add_argument("--workspace", type=Path, default=Path("data/cache/workbench"))
    parser.add_argument("--research-provider", choices=("openai", "anthropic"))
    parser.add_argument("--research-model")
    args = parser.parse_args()
    if bool(args.research_provider) != bool(args.research_model):
        parser.error("--research-provider and --research-model must be configured together")
    configured = (
        provider_config({"provider": args.research_provider, "model_name": args.research_model})
        if args.research_provider
        else None
    )
    repo = Path(__file__).resolve().parents[4]
    workspace = args.workspace if args.workspace.is_absolute() else repo / args.workspace
    server = WorkbenchServer(repo, workspace, port=args.port, research_provider=configured)
    server.runner.start()
    server.shadow.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
