"""Manual owner attestation for readiness reviews. Never a live-order permission.

The credential lives outside the checkout. Provider workers receive neither its path nor
session state. Local HTTP assumes trusted local services; private HTTPS supplies the
stronger transport boundary. Sessions are RAM-only and disappear on restart.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from getpass import getpass
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from entropytrade.domain.time import Clock, SystemClock
from entropytrade.research.store import reject_collector_chain

SCHEMA = "entropytrade-owner-v1"
ITERATIONS = 600_000
SESSION_SECONDS = 1800
MAX_SESSIONS = 8
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW = 60
MAX_KDFS = 2
_OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9.@_+-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class OwnerAuthError(ValueError):
    """Authentication was absent, expired or invalid; no supplied secret is echoed."""


class OwnerRateError(OwnerAuthError):
    """KDF capacity is reserved before work so parallel guesses cannot bypass limits."""


@dataclass(frozen=True)
class OwnerPrincipal:
    owner_id: str
    authenticated_at: str
    _expires: float = field(repr=False, compare=False)
    _timer: Callable[[], float] = field(repr=False, compare=False)
    _credential_check: Callable[[], None] = field(repr=False, compare=False)

    def actor(self) -> dict[str, str]:
        return {"kind": "human", "actor_id": self.owner_id}

    def require_current(self) -> None:
        """Recheck expiry and credentials at commit while the owner lock is held."""
        if self._timer() >= self._expires:
            raise OwnerAuthError("owner session expired before the privileged commit")
        self._credential_check()
        if self._timer() >= self._expires:
            raise OwnerAuthError("owner session expired before the privileged commit")


@dataclass(frozen=True)
class _Credential:
    owner_id: str
    salt: bytes
    verifier: bytes
    fingerprint: str


@dataclass(frozen=True)
class _Session:
    principal: OwnerPrincipal
    fingerprint: str
    audience: str
    expires: float


def credential_path(path: Path, repo: Path) -> Path:
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("owner credentials require an absolute path without symlinks")
    resolved = path.resolve()
    reject_collector_chain(resolved)
    if resolved.is_relative_to(repo.resolve()):
        raise ValueError("owner credentials must be outside the checkout and workspace")
    return resolved


def _password(password: object) -> bytes:
    if not isinstance(password, str) or not 12 <= len(password) <= 256 or not password.strip():
        raise OwnerAuthError("owner passphrase must contain 12-256 characters")
    return password.encode("utf-8")


def _derive(password: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password, salt, ITERATIONS)


def initialize(path: Path, repo: Path, owner_id: str, password: str) -> Path:
    """Local operator setup only. No HTTP endpoint calls this function."""
    target = credential_path(path, repo)
    if _OWNER.fullmatch(owner_id) is None:
        raise ValueError("owner ID must contain 1-128 simple identifier characters")
    encoded = _password(password)
    if target.exists():
        raise ValueError("owner credential file already exists; it is never overwritten")
    target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if (
        target.parent.stat().st_uid != os.getuid()
        or stat.S_IMODE(target.parent.stat().st_mode) & 0o077
    ):
        raise ValueError("owner credential directory must be private to its owner (0700)")
    salt = secrets.token_bytes(32)
    payload = {
        "schema": SCHEMA,
        "owner_id": owner_id,
        "iterations": ITERATIONS,
        "salt": salt.hex(),
        "verifier": _derive(encoded, salt).hex(),
    }
    stage: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb", prefix=".owner-", dir=target.parent, delete=False
        ) as out:
            stage = Path(out.name)
            os.fchmod(out.fileno(), 0o600)
            out.write((json.dumps(payload, sort_keys=True) + "\n").encode())
            out.flush()
            os.fsync(out.fileno())
        os.link(stage, target)  # atomic no-replace, including a target created concurrently
        return target
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def _read(path: Path, repo: Path) -> _Credential:
    target = credential_path(path, repo)
    descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 16_384
        ):
            raise ValueError("owner credential file must be a private regular file (0600)")
        raw = source.read(16_385)
    payload = json.loads(raw)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "owner_id", "iterations", "salt", "verifier"}
        or payload["schema"] != SCHEMA
        or type(payload["iterations"]) is not int
        or payload["iterations"] != ITERATIONS
        or not isinstance(payload["owner_id"], str)
        or _OWNER.fullmatch(payload["owner_id"]) is None
        or not isinstance(payload["salt"], str)
        or _HEX.fullmatch(payload["salt"]) is None
        or not isinstance(payload["verifier"], str)
        or _HEX.fullmatch(payload["verifier"]) is None
    ):
        raise ValueError("owner credential format failed verification")
    return _Credential(
        payload["owner_id"],
        bytes.fromhex(payload["salt"]),
        bytes.fromhex(payload["verifier"]),
        hashlib.sha256(raw).hexdigest(),
    )


class OwnerAuth:
    def __init__(
        self,
        repo: Path,
        path: Path | None = None,
        *,
        clock: Clock | None = None,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        self.repo, self.path = repo, path
        self.clock, self.timer = clock or SystemClock(), timer
        self.cookie_name = "et_owner_" + secrets.token_hex(8)
        self.lock = threading.RLock()
        self._sessions: dict[str, _Session] = {}
        self._attempts: deque[float] = deque()
        self._active_kdfs = 0
        self._fingerprint: str | None = None
        if path is not None:
            self._credentials()  # explicit invalid configuration fails before server writes

    def _credentials(self) -> _Credential:
        if self.path is None:
            raise OwnerAuthError(
                "owner review is unavailable until local credentials are configured"
            )
        credential = _read(self.path, self.repo)
        if credential.fingerprint != self._fingerprint:
            self._sessions.clear()
            self._fingerprint = credential.fingerprint
        return credential

    def _token(self, cookie: str | None) -> str | None:
        if cookie is None or len(cookie) > 8192:
            return None
        try:
            parsed = SimpleCookie()
            parsed.load(cookie)
            item = parsed.get(self.cookie_name)
            value = item.value if item is not None else ""
        except (CookieError, ValueError):
            return None
        return hashlib.sha256(value.encode()).hexdigest() if _TOKEN.fullmatch(value) else None

    def _prune(self) -> None:
        now = self.timer()
        self._sessions = {
            key: value for key, value in self._sessions.items() if value.expires > now
        }

    def _principal(self, cookie: str | None, audience: str) -> OwnerPrincipal | None:
        self._credentials()
        self._prune()
        session = self._sessions.get(self._token(cookie) or "")
        if session is None or session.audience != audience:
            return None
        return session.principal

    def status(self, cookie: str | None, audience: str) -> dict[str, Any]:
        with self.lock:
            try:
                principal = self._principal(cookie, audience) if self.path is not None else None
            except (OSError, ValueError):
                self._sessions.clear()
                principal = None
            return {
                "configured": self.path is not None,
                "authenticated": principal is not None,
                "principal": (
                    {"id": principal.owner_id, "authenticated_at": principal.authenticated_at}
                    if principal is not None
                    else None
                ),
                "execution_authorized": False,
                "submission_enabled": False,
            }

    def login(self, password: str, audience: str) -> str:
        with self.lock:
            credential = self._credentials()
            now = self.timer()
            while self._attempts and self._attempts[0] <= now - ATTEMPT_WINDOW:
                self._attempts.popleft()
            if len(self._attempts) >= MAX_ATTEMPTS or self._active_kdfs >= MAX_KDFS:
                raise OwnerRateError("owner login is rate limited; try again shortly")
            self._attempts.append(now)
            encoded = _password(password)
            self._active_kdfs += 1
        try:
            matched = hmac.compare_digest(_derive(encoded, credential.salt), credential.verifier)
        finally:
            with self.lock:
                self._active_kdfs -= 1
        with self.lock:
            if not matched or self._credentials().fingerprint != credential.fingerprint:
                raise OwnerAuthError("owner login failed")
            self._prune()
            if len(self._sessions) >= MAX_SESSIONS:
                oldest = min(self._sessions, key=lambda key: self._sessions[key].expires)
                self._sessions.pop(oldest)
            token = secrets.token_urlsafe(32)
            expires = self.timer() + SESSION_SECONDS

            def check_credential() -> None:
                try:
                    current = self._credentials()
                except (OSError, ValueError) as exc:
                    raise OwnerAuthError("owner credentials changed before commit") from exc
                if current.fingerprint != credential.fingerprint:
                    raise OwnerAuthError("owner credentials changed before commit")

            self._sessions[hashlib.sha256(token.encode()).hexdigest()] = _Session(
                OwnerPrincipal(
                    credential.owner_id,
                    self.clock.now().isoformat(),
                    expires,
                    self.timer,
                    check_credential,
                ),
                credential.fingerprint,
                audience,
                expires,
            )
            return token

    def logout(self, cookie: str | None) -> None:
        with self.lock:
            self._sessions.pop(self._token(cookie) or "", None)

    @contextmanager
    def authorize(self, cookie: str | None, audience: str) -> Iterator[OwnerPrincipal]:
        """Recheck after evidence verification; retain this lock through the DB commit.

        Lock order is always owner -> Jobs DB. Logout cannot race a half-authorized commit.
        No store calls this function while holding its own transaction.
        """
        with self.lock:
            principal = self._principal(cookie, audience)
            if principal is None:
                raise OwnerAuthError("an authenticated owner session is required")
            yield principal

    def set_cookie(self, token: str | None, *, secure: bool = False) -> str:
        value = SimpleCookie()
        value[self.cookie_name] = token or ""
        item = value[self.cookie_name]
        item["path"], item["httponly"], item["samesite"] = "/", True, "Strict"
        item["max-age"] = str(SESSION_SECONDS if token is not None else 0)
        if secure:
            item["secure"] = True
        return item.OutputString()


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure manual EntropyTrade owner review")
    parser.add_argument("action", choices=("init",))
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--owner-id", default="owner")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("run owner setup in an interactive local terminal")
    password = getpass("Owner passphrase (12-256 characters): ")
    confirmation = getpass("Confirm owner passphrase: ")
    if not hmac.compare_digest(password.encode(), confirmation.encode()):
        parser.error("passphrases do not match")
    try:
        initialize(
            args.file.expanduser(), Path(__file__).resolve().parents[4], args.owner_id, password
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
