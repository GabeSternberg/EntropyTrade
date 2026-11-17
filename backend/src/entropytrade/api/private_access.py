"""Explicit private HTTPS audience behind a trusted loopback Tailscale Serve proxy.

Serve strips untrusted identity headers and supplies its verified user login. This is
not an OS-user isolation boundary: other services on this same host must be trusted.
Forwarded host/protocol headers never establish either audience or identity here.
"""

import re
from dataclasses import dataclass
from email.message import Message
from pathlib import Path

_HOST = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)
_LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}@[A-Za-z0-9][A-Za-z0-9._+-]{0,127}\Z")


@dataclass(frozen=True)
class PrivateAccess:
    origin: str
    host: str
    owner_login: str

    @classmethod
    def configure(
        cls, origin: str | None, owner_login: str | None, owner_file: Path | None
    ) -> "PrivateAccess | None":
        """Validate configuration without opening or creating workspace contents."""
        if origin is None and owner_login is None:
            return None
        if origin is None or owner_login is None or owner_file is None:
            raise ValueError(
                "private access requires --private-origin, --tailscale-owner and --owner-file"
            )
        host = origin.removeprefix("https://")
        if not origin.startswith("https://") or _HOST.fullmatch(host) is None:
            raise ValueError("private origin must be one exact HTTPS FQDN without port or path")
        if _LOGIN.fullmatch(owner_login) is None:
            raise ValueError(
                "Tailscale owner must be one exact user login, such as owner@example.com"
            )
        return cls(origin, host, owner_login)

    def accepts(self, headers: Message, *, method: str) -> bool:
        """Require one actual Host/login, never a forwarded substitute or display name."""
        if headers.get_all("Host", []) != [self.host] or headers.get_all(
            "Tailscale-User-Login", []
        ) != [self.owner_login]:
            return False
        origins = headers.get_all("Origin", [])
        if origins != [self.origin] and (origins or method == "POST"):
            return False
        sites = headers.get_all("Sec-Fetch-Site", [])
        if sites not in ([], ["same-origin"], ["none"]):
            return False
        # Duplicated authentication/framing fields have no canonical interpretation.
        return all(
            len(headers.get_all(name, [])) <= 1
            for name in (
                "Cookie",
                "X-EntropyTrade-CSRF",
                "Content-Length",
                "Content-Type",
                "Transfer-Encoding",
            )
        )
