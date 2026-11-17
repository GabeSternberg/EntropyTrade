"""Real HTTP handler + OwnerAuth, explicitly emulating trusted loopback Serve headers.

These controlled tests do not claim to exercise actual TLS, Tailscale, Windows or WSL.
No provider/collector worker is started and no exchange account is configured.
"""

import http.client
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pytest

from entropytrade.api.owner import SESSION_SECONDS, OwnerAuth, initialize
from entropytrade.api.server import WorkbenchServer
from tests.integration.test_workbench_process import REPO

ORIGIN = "https://research.controlled-tailnet.ts.net"
HOST = "research.controlled-tailnet.ts.net"
LOGIN = "owner@example.com"
PASSWORD = "CONTROLLED private owner password"  # noqa: S105 - synthetic test secret


@dataclass
class Listener:
    server: WorkbenchServer
    client: httpx.Client
    owner_file: Path

    def login(self) -> str:
        bootstrap = self.client.get("/api/owner").json()
        response = self.client.post(
            "/api/owner/login",
            json={"password": PASSWORD},
            headers={"X-EntropyTrade-CSRF": bootstrap["csrf_token"]},
        )
        assert response.status_code == 200, response.text
        cookie = response.headers["set-cookie"]
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=Strict" in cookie
        assert "Domain=" not in cookie
        self.client.headers["Cookie"] = cookie.split(";", 1)[0]
        csrf = bootstrap["csrf_token"]
        assert isinstance(csrf, str)
        return csrf

    def raw(self, method: str, path: str, headers: list[tuple[str, str]]) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders()
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()


@contextmanager
def listening(workspace: Path, owner_file: Path, *, private: bool = True) -> Iterator[Listener]:
    with WorkbenchServer(
        REPO,
        workspace,
        port=0,
        owner_file=owner_file,
        private_origin=ORIGIN if private else None,
        tailscale_owner=LOGIN if private else None,
    ) as server:
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        headers = {"Host": HOST, "Origin": ORIGIN, "Tailscale-User-Login": LOGIN} if private else {}
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{server.server_port}",
                headers=headers,
                trust_env=False,
                timeout=10,
            ) as client:
                yield Listener(server, client, owner_file)
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert not thread.is_alive()
    assert not server.labels.thread.is_alive()


@pytest.fixture
def paths(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    owner_file = tmp_path / "private/owner.json"
    initialize(owner_file, REPO, "controlled-private-owner", PASSWORD)
    with TemporaryDirectory(prefix="private-listener-", dir=REPO / "data/cache") as name:
        yield Path(name), owner_file


@pytest.fixture
def private(paths: tuple[Path, Path]) -> Iterator[Listener]:
    with listening(*paths) as listener:
        yield listener


def test_identity_and_actual_host_precede_even_bootstrap(private: Listener) -> None:
    valid = [("Host", HOST), ("Tailscale-User-Login", LOGIN)]
    invalid_headers = [
        [("Host", HOST)],  # Funnel/tagged devices have no verified user login.
        [("Host", HOST), ("Tailscale-User-Login", "outsider@example.com")],
        [("Host", HOST), ("Tailscale-User-Name", LOGIN)],
        [("Host", HOST), ("Tailscale-User-Login", "tag:research")],
        [("Host", HOST), ("Tailscale-User-Login", LOGIN.upper())],
        [*valid, ("Tailscale-User-Login", LOGIN)],
        [*valid, ("Host", HOST)],
        [*valid, ("Origin", ORIGIN), ("Origin", ORIGIN)],
        [*valid, ("Cookie", "a=b"), ("Cookie", "c=d")],
        [*valid, ("Sec-Fetch-Site", "cross-site")],
        [*valid, ("Sec-Fetch-Site", "same-site")],
        [*valid, ("Sec-Fetch-Site", "same-origin"), ("Sec-Fetch-Site", "same-origin")],
        [*valid, ("Origin", "http://" + HOST)],
        [*valid, ("Origin", ORIGIN + "/")],
        [*valid, ("Origin", "null")],
        [("Host", HOST + ":443"), ("Tailscale-User-Login", LOGIN)],
        [("Host", HOST.upper()), ("Tailscale-User-Login", LOGIN)],
        [("Host", "127.0.0.1"), ("Tailscale-User-Login", LOGIN), ("X-Forwarded-Host", HOST)],
        [("Host", HOST), ("X-Forwarded-User", LOGIN), ("X-Forwarded-Proto", "https")],
    ]
    for headers in invalid_headers:
        status, body = private.raw("GET", "/api/owner", headers)
        assert status == 403, headers
        assert "csrf_token" not in json.loads(body)
    status, _ = private.raw("GET", "https://attacker.invalid/api/owner", valid)
    assert status == 403
    # Forwarded metadata supplies no authority: the actual Host/login alone decide.
    status, body = private.raw(
        "GET",
        "/api/owner",
        [*valid, ("X-Forwarded-Host", "attacker.invalid"), ("X-Forwarded-Proto", "http")],
    )
    assert status == 200
    assert not json.loads(body)["authenticated"]


def test_private_bootstrap_is_minimal_and_all_api_data_require_a_session(private: Listener) -> None:
    bootstrap = private.client.get("/api/owner")
    assert bootstrap.status_code == 200
    assert set(bootstrap.json()) == {
        "csrf_token",
        "configured",
        "authenticated",
        "principal",
        "execution_authorized",
        "submission_enabled",
    }
    assert bootstrap.json()["principal"] is None
    assert (
        bootstrap.json()["execution_authorized"] is bootstrap.json()["submission_enabled"] is False
    )
    csrf = bootstrap.json()["csrf_token"]
    routes = (
        "/api",
        "/api/catalog",
        "/api/workspace/summary",
        "/api/cis1990",
        "/api/cis1990/00000000-0000-4000-8000-000000000000/trace",
        "/api/jobs",
        "/api/jobs/00000000-0000-4000-8000-000000000000/report",
        "/api/jobs/00000000-0000-4000-8000-000000000000/review",
        "/api/jobs/00000000-0000-4000-8000-000000000000/shadow-inputs",
        "/api/monitors",
        "/api/alerts",
        "/api/controls",
        "/api/readiness/unknown",
        "/api/weather/datasets",
        "/api/weather/schedules",
        "/api/weather/partitions",
        "/api/research",
        "/api/research/jobs",
        "/api/research/jobs/unknown/export",
        "/api/fees",
        "/api/v1-gates",
        "/api/recovery",
        "/api/owner/login",
        "/api/future-route",
    )
    for route in routes:
        response = private.client.get(route)
        assert response.status_code == 401, route
        assert response.json() == {"error": "An authenticated owner session is required"}
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    for route in (
        "/api/jobs",
        "/api/research/jobs",
        "/api/controls/halt",
        "/api/owner",
        "/api/new",
    ):
        response = private.client.post(route, json={}, headers={"X-EntropyTrade-CSRF": csrf})
        assert response.status_code == 401, route
    assert private.client.get("/").status_code == 200  # shell can open the owner dialog
    assert private.client.get("/views-ops.js").status_code == 200


def test_real_owner_session_https_audience_cookie_and_all_flags_remain_off(
    private: Listener,
) -> None:
    csrf = private.login()
    cookie = private.client.headers["Cookie"]
    assert private.server.owner.status(cookie, ORIGIN)["authenticated"]
    assert not private.server.owner.status(cookie, "http://" + HOST)["authenticated"]
    catalog = private.client.get("/api/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["submission_enabled"] is False
    status = private.client.get("/api/owner").json()
    assert status["authenticated"]
    assert status["principal"]["id"] == "controlled-private-owner"
    assert status["execution_authorized"] is status["submission_enabled"] is False
    controls = private.client.post(
        "/api/controls/halt",
        json={"reason": "CONTROLLED private session test"},
        headers={"X-EntropyTrade-CSRF": csrf},
    )
    assert controls.status_code == 200
    assert controls.json()["halted"]
    assert controls.json()["submission_enabled"] is False
    assert private.client.get("/api/orders").status_code == 404
    logged_out = private.client.post(
        "/api/owner/logout", json={}, headers={"X-EntropyTrade-CSRF": csrf}
    )
    assert logged_out.status_code == 200
    assert not logged_out.json()["authenticated"]
    assert "Secure" in logged_out.headers["set-cookie"]
    assert "Max-Age=0" in logged_out.headers["set-cookie"]
    assert private.client.get("/api/catalog").status_code == 401


def test_csrf_origin_framing_and_unsupported_methods_do_not_bypass_sessions(
    private: Listener,
) -> None:
    owner = private.client.get("/api/owner").json()
    assert private.client.post("/api/owner/login", json={"password": PASSWORD}).status_code == 403
    assert (
        private.client.post(
            "/api/owner/login",
            json={"password": PASSWORD},
            headers={"X-EntropyTrade-CSRF": "wrong"},
        ).status_code
        == 403
    )
    headers = [
        ("Host", HOST),
        ("Tailscale-User-Login", LOGIN),
        ("X-EntropyTrade-CSRF", owner["csrf_token"]),
    ]
    assert private.raw("POST", "/api/owner/login", headers)[0] == 403  # POST Origin required
    assert (
        private.raw(
            "POST",
            "/api/owner/login",
            [*headers, ("Origin", ORIGIN), ("X-EntropyTrade-CSRF", owner["csrf_token"])],
        )[0]
        == 403
    )
    for method in ("HEAD", "OPTIONS", "PUT", "PATCH", "DELETE", "CONTROLLED"):
        assert private.client.request(method, "/api/catalog").status_code == 401
    private.login()
    for method in ("HEAD", "OPTIONS", "PUT", "PATCH", "DELETE", "CONTROLLED"):
        response = private.client.request(method, "/api/catalog")
        assert response.status_code == 405
        assert response.headers["cache-control"] == "no-store"
    assert (
        private.client.post(
            "/api/jobs", content="{}", headers={"X-EntropyTrade-CSRF": owner["csrf_token"]}
        ).status_code
        == 415
    )


def test_expired_wrong_audience_restart_and_rotated_credentials_refuse(private: Listener) -> None:
    timer = [0.0]
    private.server.owner.timer = lambda: timer[0]
    private.login()
    cookie = private.client.headers["Cookie"]
    timer[0] = SESSION_SECONDS
    assert private.client.get("/api/catalog").status_code == 401
    timer[0] += 61
    token = private.server.owner.login(PASSWORD, "http://" + HOST)
    private.client.headers["Cookie"] = private.server.owner.cookie_name + "=" + token
    assert private.client.get("/api/catalog").status_code == 401
    # Replacing the auth instance reproduces process-restart RAM session invalidation.
    private.server.owner = OwnerAuth(REPO, private.owner_file)
    private.client.headers["Cookie"] = cookie
    assert private.client.get("/api/catalog").status_code == 401
    private.login()
    payload = json.loads(private.owner_file.read_bytes())
    payload["owner_id"] = "controlled-rotated-owner"
    private.owner_file.write_text(json.dumps(payload))
    assert private.client.get("/api/catalog").status_code == 401
    assert not private.client.get("/api/owner").json()["authenticated"]


def test_actual_server_restart_and_local_http_compatibility(paths: tuple[Path, Path]) -> None:
    with listening(*paths) as first:
        old_csrf = first.login()
        old_cookie = first.client.headers["Cookie"]
    with listening(*paths) as second:
        second.client.headers["Cookie"] = old_cookie
        assert second.client.get("/api/catalog").status_code == 401
        assert (
            second.client.post(
                "/api/owner/login",
                json={"password": PASSWORD},
                headers={"X-EntropyTrade-CSRF": old_csrf},
            ).status_code
            == 403
        )
    with listening(*paths, private=False) as local:
        catalog = local.client.get("/api/catalog")
        assert catalog.status_code == 200
        assert catalog.json()["submission_enabled"] is False
        assert local.client.get("/api/owner").json()["authenticated"] is False
        response = local.client.post(
            "/api/owner/login",
            json={"password": PASSWORD},
            headers={"X-EntropyTrade-CSRF": catalog.json()["csrf_token"]},
        )
        assert response.status_code == 200
        assert "Secure" not in response.headers["set-cookie"]
        assert local.client.get("/api/catalog", headers={"Host": HOST}).status_code == 403
