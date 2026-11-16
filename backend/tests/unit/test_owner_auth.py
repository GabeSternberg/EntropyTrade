"""CONTROLLED owner credentials and RAM sessions; never an approval to trade."""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from entropytrade.api import owner
from entropytrade.api.owner import OwnerAuth, OwnerAuthError, OwnerRateError, initialize
from entropytrade.domain.time import SimulatedClock

PASSWORD = "  CONTROLLED owner passphrase  "  # noqa: S105 - synthetic test secret, never a credential
AUDIENCE = "http://127.0.0.1:43128"


@pytest.fixture
def configured(tmp_path: Path) -> tuple[OwnerAuth, Path, list[float]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = tmp_path / "private/owner.json"
    initialize(target, repo, "controlled-owner", PASSWORD)
    timer = [0.0]
    auth = OwnerAuth(
        repo,
        target,
        clock=SimulatedClock(datetime(2026, 11, 16, tzinfo=UTC)),
        timer=lambda: timer[0],
    )
    return auth, target, timer


def cookie(auth: OwnerAuth, token: str) -> str:
    return auth.cookie_name + "=" + token


def test_setup_is_private_without_plaintext_and_never_overwrites(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, path, _ = configured
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    data = path.read_bytes()
    assert PASSWORD.encode() not in data
    assert json.loads(data)["iterations"] == 600_000
    with pytest.raises(ValueError, match="already exists"):
        initialize(path, auth.repo, "another-owner", "another controlled passphrase")
    assert path.read_bytes() == data
    assert list(path.parent.iterdir()) == [path]


def test_password_bytes_owner_identity_and_audience_are_exact(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, _, _ = configured
    with pytest.raises(OwnerAuthError, match="login failed"):
        auth.login(PASSWORD.strip(), AUDIENCE)
    token = auth.login(PASSWORD, AUDIENCE)
    header = cookie(auth, token)
    state = auth.status(header, AUDIENCE)
    assert state["authenticated"] is True
    assert state["principal"]["id"] == "controlled-owner"
    assert PASSWORD not in json.dumps(state)
    assert token not in json.dumps(state)
    assert state["execution_authorized"] is state["submission_enabled"] is False
    assert not auth.status(header, "http://127.0.0.1:43129")["authenticated"]
    with auth.authorize(header, AUDIENCE) as principal:
        assert principal.actor() == {"kind": "human", "actor_id": "controlled-owner"}


def test_expiry_logout_restart_and_rotation_invalidate_sessions(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, path, timer = configured
    header = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    restarted = OwnerAuth(auth.repo, path)
    assert restarted.cookie_name != auth.cookie_name
    assert not restarted.status(header, AUDIENCE)["authenticated"]
    auth.logout(header)
    with pytest.raises(OwnerAuthError, match="authenticated"), auth.authorize(header, AUDIENCE):
        pytest.fail("logout must reject a later privileged commit")
    header = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    timer[0] = owner.SESSION_SECONDS
    assert not auth.status(header, AUDIENCE)["authenticated"]
    timer[0] += 61
    header = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    payload = json.loads(path.read_text())
    payload["owner_id"] = "rotated-owner"
    path.write_text(json.dumps(payload))
    assert not auth.status(header, AUDIENCE)["authenticated"]


def test_no_implicit_owner_or_browser_configuration(tmp_path: Path) -> None:
    auth = OwnerAuth(tmp_path)
    state = auth.status(None, AUDIENCE)
    assert state["configured"] is state["authenticated"] is False
    with pytest.raises(OwnerAuthError, match="configured"):
        auth.login(PASSWORD, AUDIENCE)
    assert list(tmp_path.iterdir()) == []


def test_deadline_is_rechecked_after_waiting_for_a_transaction(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, _, timer = configured
    header = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    with auth.authorize(header, AUDIENCE) as principal:
        principal.require_current()
        timer[0] = owner.SESSION_SECONDS
        with pytest.raises(OwnerAuthError, match="privileged commit"):
            principal.require_current()


def test_rotation_is_rechecked_at_the_privileged_write_point(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, path, _ = configured
    header = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    with auth.authorize(header, AUDIENCE) as principal:
        payload = json.loads(path.read_text())
        payload["owner_id"] = "rotated-owner"
        path.write_text(json.dumps(payload))
        with pytest.raises(OwnerAuthError, match="credentials changed"):
            principal.require_current()


def test_expiry_during_credential_read_refuses_the_privileged_commit(
    configured: tuple[OwnerAuth, Path, list[float]], monkeypatch: pytest.MonkeyPatch
) -> None:
    auth, _, timer = configured
    header = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    with auth.authorize(header, AUDIENCE) as principal:
        original = auth._credentials

        def slow_read() -> owner._Credential:
            credential = original()
            timer[0] = owner.SESSION_SECONDS
            return credential

        monkeypatch.setattr(auth, "_credentials", slow_read)
        with pytest.raises(OwnerAuthError, match="privileged commit"):
            principal.require_current()


@pytest.mark.parametrize("mode", [0o640, 0o644, 0o400])
def test_non_private_credential_mode_is_refused(
    configured: tuple[OwnerAuth, Path, list[float]], mode: int
) -> None:
    auth, path, _ = configured
    path.chmod(mode)
    with pytest.raises(ValueError, match="0600"):
        OwnerAuth(auth.repo, path)


def test_checkout_canonical_and_symlink_paths_refuse_before_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="outside"):
        initialize(repo / "credentials/owner.json", repo, "owner", PASSWORD)
    assert list(repo.iterdir()) == []
    chain = tmp_path / "chain"
    with pytest.raises(ValueError, match="collector"):
        initialize(chain / "private/owner.json", repo, "owner", PASSWORD)
    assert not chain.exists()
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path / "destination", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        initialize(alias / "owner.json", repo, "owner", PASSWORD)
    assert not (tmp_path / "destination").exists()


def test_fifo_credential_refusal_cannot_block_startup(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, path, _ = configured
    path.unlink()
    os.mkfifo(path, 0o600)
    script = (
        "import sys; from pathlib import Path; from entropytrade.api.owner import OwnerAuth; "
        "OwnerAuth(Path(sys.argv[1]), Path(sys.argv[2]))"
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter, fixed script, isolated test paths
        [sys.executable, "-c", script, str(auth.repo), str(path)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode != 0
    assert "private regular file" in result.stderr


def test_cookie_flags_and_malformed_headers_do_not_authenticate(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, _, _ = configured
    token = auth.login(PASSWORD, AUDIENCE)
    header = auth.set_cookie(token, secure=True)
    for flag in ("HttpOnly", "SameSite=Strict", "Path=/", "Secure", "Max-Age=1800"):
        assert flag in header
    assert "Domain=" not in header
    assert "Max-Age=0" in auth.set_cookie(None)
    for invalid in (None, "unknown=token", cookie(auth, "bad"), "x" * 8193):
        assert not auth.status(invalid, AUDIENCE)["authenticated"]


def test_rate_capacity_is_reserved_before_parallel_kdfs(
    configured: tuple[OwnerAuth, Path, list[float]], monkeypatch: pytest.MonkeyPatch
) -> None:
    auth, _, _ = configured
    original = owner._derive
    calls = []
    entered, release = threading.Event(), threading.Event()
    call_lock = threading.Lock()

    def blocked(password: bytes, salt: bytes) -> bytes:
        with call_lock:
            calls.append(1)
            if len(calls) == owner.MAX_KDFS:
                entered.set()
        assert release.wait(timeout=5)
        return original(password, salt)

    monkeypatch.setattr(owner, "_derive", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(auth.login, PASSWORD, AUDIENCE)
        second = pool.submit(auth.login, PASSWORD, AUDIENCE)
        try:
            assert entered.wait(timeout=5)
            with pytest.raises(OwnerRateError):
                auth.login(PASSWORD, AUDIENCE)
            assert len(calls) == 2
        finally:
            release.set()
        assert first.result(timeout=5) != second.result(timeout=5)


def test_global_attempt_limit_expires_and_sessions_remain_bounded(
    configured: tuple[OwnerAuth, Path, list[float]],
) -> None:
    auth, _, timer = configured
    for _ in range(owner.MAX_ATTEMPTS):
        with pytest.raises(OwnerAuthError, match="login failed"):
            auth.login("wrong controlled passphrase", AUDIENCE)
    with pytest.raises(OwnerRateError):
        auth.login(PASSWORD, AUDIENCE)
    timer[0] += 61
    oldest = cookie(auth, auth.login(PASSWORD, AUDIENCE))
    for _ in range(owner.MAX_SESSIONS):
        timer[0] += 61
        auth.login(PASSWORD, AUDIENCE)
    assert not auth.status(oldest, AUDIENCE)["authenticated"]
