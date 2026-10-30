"""Loopback-only HTTP workbench with same-origin writes and a fixed asset allowlist."""

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from entropytrade.api.jobs import Jobs, identifier, provider_config
from entropytrade.api.runner import Runner
from entropytrade.api.workspace import acquire_workspace
from entropytrade.api.workspace import workspace_path as workspace_path
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore

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
            super().__init__(("127.0.0.1", port), Handler)
            self.jobs.recover()
            self.tracking.recover()
        except BaseException:
            self.lock.close()
            raise
        self.token = secrets.token_urlsafe(32)

    def server_close(self) -> None:
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
                    "modes": ["recorded", "public", "synthetic", "history"],
                    "provider_enabled": bool(getattr(self.server, "research_provider", None)),
                    "research_provider": getattr(self.server, "research_provider", None),
                    "submission_enabled": False,
                    "limits": {"queued_jobs": 8, "worker_seconds": 600, "synthetic_days": 240},
                },
            )
        elif path == "/api/jobs":
            self.document(200, self.server.jobs.history())
        elif path == "/api/monitors":
            self.document(200, self.server.tracking.history())
        elif path.startswith("/api/monitors/"):
            route = self.monitor_route()
            monitor = (
                self.server.tracking.get(route[0], export=route[1] == "export") if route else None
            )
            if monitor is None or route is None or route[1] not in {"", "export"}:
                self.document(404, {"error": "not found"})
            else:
                self.document(200, monitor)
        else:
            route = self.job_route()
            job = self.server.jobs.get(route[0]) if route else None
            if job is None or route is None or route[1] not in {"", "report", "review"}:
                self.document(404, {"error": "not found"})
            elif route[1] == "report":
                self.send(
                    200,
                    ((job["result"] or {}).get("report", "Run has no report yet.")).encode(),
                    "text/plain; charset=utf-8",
                )
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
        except (ValueError, UnicodeError) as exc:
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
