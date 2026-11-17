"""Loopback-only HTTP workbench with same-origin writes and a fixed asset allowlist."""

import argparse
import json
import os
import re
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from entropytrade.api.jobs import COURSE_MODE, Jobs, identifier, provider_config
from entropytrade.api.owner import OwnerAuth, OwnerAuthError, OwnerRateError
from entropytrade.api.private_access import PrivateAccess
from entropytrade.api.runner import COURSE_KEY_VARIABLE, Runner
from entropytrade.api.workspace import acquire_workspace
from entropytrade.api.workspace import workspace_path as workspace_path
from entropytrade.tracking.runner import ShadowRunner
from entropytrade.tracking.store import TrackingStore
from entropytrade.weather.label_service import LabelService

if TYPE_CHECKING:
    from entropytrade.research.readiness import ResearchReadinessService

ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    # Presentation shell. Demo Mode sample data is generated in the browser by
    # demo-data.js and never reaches an API route; see frontend/src/README.md.
    "/ui.js": ("ui.js", "text/javascript; charset=utf-8"),
    "/demo-data.js": ("demo-data.js", "text/javascript; charset=utf-8"),
    "/shell.js": ("shell.js", "text/javascript; charset=utf-8"),
    "/views-markets.js": ("views-markets.js", "text/javascript; charset=utf-8"),
    "/views-lab.js": ("views-lab.js", "text/javascript; charset=utf-8"),
    "/views-ops.js": ("views-ops.js", "text/javascript; charset=utf-8"),
    "/views-cis1990.js": ("views-cis1990.js", "text/javascript; charset=utf-8"),
    "/views-research.js": ("views-research.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
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
        owner_file: Path | None = None,
        private_origin: str | None = None,
        tailscale_owner: str | None = None,
    ) -> None:
        self.private_access = PrivateAccess.configure(private_origin, tailscale_owner, owner_file)
        if self.private_access is not None:
            from entropytrade.operations.research_server import validate_research_layout

            validate_research_layout(repo, workspace)
        self.repo = repo.resolve()
        self.owner = OwnerAuth(self.repo, owner_file)
        self.research_provider = provider_config(research_provider) if research_provider else None
        from entropytrade.research.store import CollectorChainError, reject_collector_chain

        try:
            reject_collector_chain(workspace)
        except CollectorChainError:
            if self.private_access is not None:
                raise  # private research must never initialize the canonical collector
            # The existing collector serves its legacy API from chain/.work-*.
            # Keep that collection path usable without activating research or E writes.
            collector_workspace = True
        else:
            collector_workspace = False
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
            from entropytrade.research.service import ResearchService

            self.research = ResearchService(root, self.repo, lease_fd=self.lock.fileno())
            from entropytrade.research.paper import ResearchPaperService

            self.paper = ResearchPaperService(root, self.tracking)
            self._readiness: ResearchReadinessService | None = None
            self._readiness_lock = threading.Lock()
            if not collector_workspace:
                _ = self.readiness  # initialize before starting normal research threads
                self.shadow.health_check = lambda: self.readiness.refresh_monitoring()
            super().__init__(("127.0.0.1", port), Handler)
            self.jobs.recover()
            self.tracking.recover()
        except BaseException:
            self.lock.close()
            raise
        self.token = secrets.token_urlsafe(32)
        self.labels.thread.start()

    @property
    def readiness(self) -> "ResearchReadinessService":
        from entropytrade.research.readiness import ResearchReadinessService

        with self._readiness_lock:
            if self._readiness is None:
                # Construction retains the canonical/symlink guard before any E writes.
                self._readiness = ResearchReadinessService(
                    self.jobs.root, self.tracking, self.research
                )
            return self._readiness

    @readiness.setter
    def readiness(self, service: "ResearchReadinessService") -> None:
        with self._readiness_lock:
            self._readiness = service

    def server_close(self) -> None:
        self.research.close()
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
        private: PrivateAccess | None = getattr(self.server, "private_access", None)
        if private is not None:
            return self.path.startswith("/") and private.accepts(self.headers, method=self.command)
        host = self.headers.get("Host", "")
        port = self.server.server_port
        if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            return False
        origin = self.headers.get("Origin")
        return self.headers.get("Sec-Fetch-Site") != "cross-site" and (
            origin is None or origin == "http://" + host
        )

    def send(
        self,
        status: int,
        body: bytes,
        content_type: str = "application/json",
        *,
        cookie: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if cookie is not None:
            self.send_header("Set-Cookie", cookie)
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(body)

    def document(self, status: int, value: object, *, cookie: str | None = None) -> None:
        self.send(status, json.dumps(value, allow_nan=False).encode(), cookie=cookie)

    def owner_audience(self) -> str:
        private: PrivateAccess | None = getattr(self.server, "private_access", None)
        if private is not None:
            return private.origin
        return "http://" + self.headers.get("Host", "")

    def private_session(self, path: str) -> bool:
        """Gate every private API route, including downloads and unknown future APIs."""
        if getattr(self.server, "private_access", None) is None or not (
            path == "/api" or path.startswith("/api/")
        ):
            return True
        if (self.command == "GET" and path == "/api/owner") or (
            self.command == "POST" and path in {"/api/owner/login", "/api/owner/logout"}
        ):
            return True
        try:
            with self.server.owner.authorize(self.headers.get("Cookie"), self.owner_audience()):
                return True
        except (OwnerAuthError, OSError, ValueError):
            self.document(401, {"error": "An authenticated owner session is required"})
            return False

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        if code == 501 and getattr(self.server, "private_access", None) is not None:
            if not self.safe_origin():
                self.document(403, {"error": "verified same-origin access required"})
            elif self.private_session(urlsplit(self.path).path):
                self.document(405, {"error": "method not allowed"})
            return
        super().send_error(code, message, explain)

    def readiness_route(self) -> tuple[str, str] | None:
        from entropytrade.research.readiness import proposal_identifier

        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) not in {3, 4} or parts[:2] != ["api", "readiness"]:
            return None
        return proposal_identifier(unquote(parts[2])), parts[3] if len(parts) == 4 else ""

    def governance_get(self, path: str) -> bool:
        if path == "/api/owner":
            self.document(
                200,
                {
                    "csrf_token": self.server.token,
                    **self.server.owner.status(self.headers.get("Cookie"), self.owner_audience()),
                },
            )
            return True
        if path == "/api/controls":
            self.document(
                200, {**self.server.readiness.store.status(), "submission_enabled": False}
            )
            return True
        monitor = self.monitor_route()
        if monitor and monitor[1] in {"readiness", "monitoring"}:
            value = (
                self.server.readiness.proposals(monitor[0])
                if monitor[1] == "readiness"
                else self.server.readiness.monitoring(monitor[0])
            )
            self.document(200, value)
            return True
        route = self.readiness_route()
        if route and route[1] == "":
            self.document(200, self.server.readiness.detail(route[0]))
            return True
        return False

    def governance_post(self, path: str, value: object) -> bool:
        from entropytrade.research.readiness import ReadinessEligibilityError

        monitor = self.monitor_route()
        route = self.readiness_route()
        if not (
            path
            in {
                "/api/owner/login",
                "/api/owner/logout",
                "/api/controls/halt",
                "/api/controls/release",
            }
            or (monitor and monitor[1] == "readiness")
            or (route and route[1] in {"review", "revoke", "rollback"})
        ):
            return False
        auth, service = self.server.owner, self.server.readiness
        audience, cookies = self.owner_audience(), self.headers.get("Cookie")
        if path == "/api/owner/login":
            if (
                not isinstance(value, dict)
                or set(value) != {"password"}
                or not isinstance(value["password"], str)
            ):
                raise ValueError("provide the owner passphrase only")
            try:
                token = auth.login(value["password"], audience)
            except OwnerRateError:
                self.document(429, {"error": "Owner login is rate limited; try again shortly"})
                return True
            except (OwnerAuthError, OSError, ValueError):
                self.document(
                    401, {"error": "Owner login failed or credentials are not configured"}
                )
                return True
            self.document(
                200,
                auth.status(auth.cookie_name + "=" + token, audience),
                cookie=auth.set_cookie(
                    token, secure=getattr(self.server, "private_access", None) is not None
                ),
            )
            return True
        if path == "/api/owner/logout" and value == {}:
            auth.logout(cookies)
            self.document(
                200,
                auth.status(None, audience),
                cookie=auth.set_cookie(
                    None, secure=getattr(self.server, "private_access", None) is not None
                ),
            )
            return True
        if path == "/api/controls/halt":
            if (
                not isinstance(value, dict)
                or set(value) != {"reason"}
                or not isinstance(value["reason"], str)
                or not 1 <= len(value["reason"].strip()) <= 1000
            ):
                raise ValueError("provide a halt reason containing 1-1000 characters")
            self.document(
                200, {**service.store.halt(value["reason"].strip()), "submission_enabled": False}
            )
            return True
        if path == "/api/controls/release":
            if (
                not isinstance(value, dict)
                or set(value) != {"expected_epoch", "reason"}
                or type(value["expected_epoch"]) is not int
                or not isinstance(value["reason"], str)
                or not 1 <= len(value["reason"].strip()) <= 1000
            ):
                raise ValueError("provide the exact control epoch and a release reason")
            with auth.authorize(cookies, audience) as principal:
                result = service.store.release(
                    value["expected_epoch"],
                    actor=principal.actor(),
                    reason=value["reason"].strip(),
                    before_commit=principal.require_current,
                )
            self.document(200, {**result, "submission_enabled": False})
            return True
        monitor = self.monitor_route()
        if monitor and monitor[1] == "readiness":
            self.document(201, service.create(monitor[0], value))
            return True
        route = self.readiness_route()
        if route and route[1] == "review":
            with auth.authorize(cookies, audience):
                pass  # reject anonymous expensive review work before reading evidence
            try:
                prepared = service.prepare_review(route[0], value)
            except ReadinessEligibilityError as exc:
                self.document(409, {"error": str(exc), "current_checks": exc.checks})
                return True
            with auth.authorize(cookies, audience) as principal:
                result = service.commit_review(prepared, principal)
            self.document(200, result)
            return True
        if route and route[1] == "revoke":
            self.document(200, service.revoke(route[0], value))
            return True
        if route and route[1] == "rollback":
            with auth.authorize(cookies, audience) as principal:
                result = service.rollback(route[0], value, principal)
            self.document(201, result)
            return True
        return False

    def job_route(self, collection: str = "jobs") -> tuple[str, str] | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) not in {3, 4} or parts[:2] != ["api", collection]:
            return None
        try:
            job_id = identifier(parts[2])
        except ValueError:
            return None
        return job_id, parts[3] if len(parts) == 4 else ""

    def research_route(self) -> tuple[str, str] | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) != 5 or parts[:3] != ["api", "research", "jobs"]:
            return None
        try:
            return identifier(parts[3]), parts[4]
        except ValueError:
            return None

    def monitor_route(self) -> tuple[str, str] | None:
        parts = urlsplit(self.path).path.strip("/").split("/")
        if len(parts) not in {3, 4} or parts[:2] != ["api", "monitors"]:
            return None
        try:
            return identifier(parts[2]), parts[3] if len(parts) == 4 else ""
        except ValueError:
            return None

    def research_get(self, path: str) -> None:
        research = self.server.research
        if path == "/api/research":
            self.document(200, {"csrf_token": self.server.token, **research.catalog()})
            return
        if path == "/api/research/jobs":
            self.document(200, {"jobs": research.list_jobs(), "submission_enabled": False})
            return
        if path == "/api/research/inventory":
            self.document(200, research.inventory_summary())
            return
        if path == "/api/research/forward":
            self.document(
                200,
                {
                    "forward_requests": research.store.forward_requests()
                    if research.started()
                    else [],
                    "submission_enabled": False,
                },
            )
            return
        parts = path.strip("/").split("/")
        if len(parts) in {4, 5} and parts[:3] == ["api", "research", "jobs"]:
            try:
                job_id = identifier(parts[3])
            except ValueError:
                job_id = ""
            action = parts[4] if len(parts) == 5 else ""
            if job_id and action == "":
                found = research.detail(job_id)
            elif job_id and action == "report":
                found = research.report(job_id)
            elif job_id and action == "paper":
                try:
                    found = self.server.paper.proposals(job_id)
                except KeyError:
                    found = None
                except (ValueError, OSError):
                    self.document(409, {"error": "Paper source verification failed"})
                    return
            else:
                found = None
            if found is not None:
                self.document(200, found)
                return
        self.extra_research_get(path)

    def extra_research_get(self, path: str) -> None:
        del path
        self.document(404, {"error": "not found"})

    def do_GET(self) -> None:
        if not self.safe_origin():
            self.document(403, {"error": "verified same-origin access required"})
            return
        path = urlsplit(self.path).path
        if not self.private_session(path):
            return
        try:
            if self.governance_get(path):
                return
        except KeyError:
            self.document(404, {"error": "readiness source not found"})
            return
        except (ValueError, OSError, sqlite3.Error):
            self.document(409, {"error": "Readiness evidence or controls failed verification"})
            return
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
        elif path == "/api/workspace/summary":
            from entropytrade.api.workspace_summary import workspace_summary

            self.document(200, workspace_summary(self.server.jobs.root))
        elif path == "/api/cis1990":
            from entropytrade.agents.course_demo import DEMO_MODEL

            self.document(
                200,
                {
                    "csrf_token": self.server.token,
                    "configured": bool(os.environ.get(COURSE_KEY_VARIABLE, "").strip()),
                    "model_name": DEMO_MODEL,
                    "latest": self.server.jobs.latest_course(),
                },
            )
        elif path.startswith("/api/cis1990/"):
            route = self.job_route(COURSE_MODE)
            job = self.server.jobs.get(route[0]) if route else None
            if job is None or job["request"]["mode"] != COURSE_MODE or route is None:
                self.document(404, {"error": "course run not found"})
            elif route[1] == "":
                self.document(200, job)
            elif route[1] == "trace" and (job["result"] or {}).get("run_id") == route[0]:
                self.document(200, job["result"])
            else:
                self.document(404, {"error": "course trace not available"})
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
        elif path == "/api/weather/label-partitions" or path.startswith(
            "/api/weather/label-partitions/"
        ):
            try:
                with self.server.labels.lock:
                    label_store = self.server.labels.partitions
                    if path == "/api/weather/label-partitions":
                        self.document(200, label_store.catalog())
                    else:
                        parts = path.removeprefix("/api/weather/label-partitions/").split("/")
                        root = label_store.selected(parts[0])
                        if len(parts) == 2 and parts[1] == "manifest":
                            label_store.validate()
                            self.document(200, label_store.manifest(root))
                        elif len(parts) == 1:
                            self.document(200, self.server.labels.catalog(parts[0]))
                        else:
                            self.document(404, {"error": "not found"})
            except (ValueError, OSError, KeyError, TypeError):
                self.document(409, {"error": "Label partition verification failed"})
        elif path == "/api/weather/labels" or path.startswith("/api/weather/labels/"):
            try:
                if path == "/api/weather/labels":
                    self.document(200, self.server.labels.active_catalog())
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
        elif path == "/api/v1-gates":
            from entropytrade.operations.v1_gates import v1_gate_report

            self.document(
                200,
                {
                    **v1_gate_report(self.server.repo / "data" / "acceptance"),
                    "submission_enabled": False,
                },
            )
        elif path == "/api/research" or path.startswith("/api/research/"):
            self.research_get(path)
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
            if route and route[1] in {"evaluation", "evaluation.csv"}:
                from entropytrade.tracking.prospective import csv_report, report

                try:
                    evaluation = report(self.server.jobs, route[0])
                    if route[1] == "evaluation.csv":
                        self.send(200, csv_report(evaluation).encode(), "text/csv; charset=utf-8")
                    else:
                        self.document(200, evaluation)
                except (ValueError, KeyError, OSError, TypeError):
                    self.document(
                        409,
                        {"error": "Prospective evidence verification failed; inspect workspace"},
                    )
                return
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
                or job["request"]["mode"] == COURSE_MODE
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
        if not self.private_session(urlsplit(self.path).path):
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
            from entropytrade.research.readiness import ReadinessConflictError

            try:
                if self.governance_post(urlsplit(self.path).path, value):
                    return
            except OwnerAuthError:
                self.document(401, {"error": "An authenticated owner session is required"})
                return
            except ReadinessConflictError as exc:
                self.document(409, {"error": str(exc)})
                return
            except sqlite3.Error:
                self.document(409, {"error": "Readiness metadata failed verification"})
                return
            if self.path == "/api/cis1990":
                if not isinstance(value, dict) or set(value) - {"api_key"}:
                    raise ValueError("the course run accepts only an optional Gemini API key")
                key = value.get("api_key", "")
                if not isinstance(key, str):
                    raise ValueError("Enter a Gemini API key as text.")
                key = key.strip()
                if key and not re.fullmatch(r"[!-~]{1,512}", key):
                    raise ValueError(
                        "The Gemini API key contains invalid characters or is too long."
                    )
                if not key and not os.environ.get(COURSE_KEY_VARIABLE, "").strip():
                    self.document(
                        503,
                        {"error": "Enter a Gemini API key or set GEMINI_API_KEY on the server."},
                    )
                    return
                self.document(202, {"id": self.server.runner.submit_course(key)})
                return
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
            if self.path == "/api/research/jobs":
                self.document(202, self.server.research.submit(value))
                return
            research_route = self.research_route()
            if research_route and research_route[1] == "paper":
                from entropytrade.research.paper import PaperEligibilityError

                try:
                    created = self.server.paper.create(research_route[0], value)
                except PaperEligibilityError as exc:
                    self.document(409, {"error": str(exc), "eligibility": exc.proposal})
                    return
                self.document(201, created)
                return
            if research_route and research_route[1] == "approve":
                changed = self.server.research.approve(research_route[0], value)
                self.document(200, {"id": research_route[0], "changed": changed})
                return
            if research_route and research_route[1] in {"cancel", "resume"} and value == {}:
                action = (
                    self.server.research.cancel
                    if research_route[1] == "cancel"
                    else self.server.research.resume
                )
                self.document(200, {"id": research_route[0], "changed": action(research_route[0])})
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
            if (
                monitor_route
                and monitor_route[1] in {"pause", "resume", "suspend", "cancel"}
                and value == {}
            ):
                self.server.tracking.control(*monitor_route)
                self.document(200, {"id": monitor_route[0]})
                return
            course_route = self.job_route(COURSE_MODE)
            route = course_route or self.job_route()
            if route and route[1] == "cancel" and value == {}:
                job = self.server.jobs.get(route[0])
                if job is not None and (job["request"]["mode"] == COURSE_MODE) == bool(
                    course_route
                ):
                    changed = self.server.jobs.update(
                        route[0], "cancelled", "Cancelled by user", status="cancelled"
                    )
                    if course_route and changed:
                        self.server.runner.forget_course_key(route[0])
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
    parser.add_argument("--owner-file", type=Path)
    parser.add_argument("--private-origin")
    parser.add_argument("--tailscale-owner")
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
    server = WorkbenchServer(
        repo,
        workspace,
        port=args.port,
        research_provider=configured,
        owner_file=args.owner_file.expanduser() if args.owner_file else None,
        private_origin=args.private_origin,
        tailscale_owner=args.tailscale_owner,
    )
    server.runner.start()
    server.shadow.start()
    server.research.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
