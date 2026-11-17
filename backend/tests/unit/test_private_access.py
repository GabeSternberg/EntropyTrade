"""Pure private audience validation; invalid configuration never creates a workspace."""

from email.message import Message
from pathlib import Path

import pytest

from entropytrade.api.private_access import PrivateAccess
from entropytrade.api.server import WorkbenchServer

ORIGIN = "https://research.controlled-tailnet.ts.net"
LOGIN = "owner@example.com"


@pytest.mark.parametrize(
    ("origin", "login", "owner_file"),
    [
        (ORIGIN, None, Path("/unopened/owner.json")),
        (None, LOGIN, Path("/unopened/owner.json")),
        (ORIGIN, LOGIN, None),
        ("", LOGIN, Path("/unopened/owner.json")),
        ("http://research.example.com", LOGIN, Path("/unopened/owner.json")),
        ("https://localhost", LOGIN, Path("/unopened/owner.json")),
        ("https://127.0.0.1", LOGIN, Path("/unopened/owner.json")),
        ("https://Research.example.com", LOGIN, Path("/unopened/owner.json")),
        ("https://research.example.com:443", LOGIN, Path("/unopened/owner.json")),
        ("https://research.example.com/", LOGIN, Path("/unopened/owner.json")),
        ("https://research.example.com?query", LOGIN, Path("/unopened/owner.json")),
        ("https://research.example.com#fragment", LOGIN, Path("/unopened/owner.json")),
        ("https://user@research.example.com", LOGIN, Path("/unopened/owner.json")),
        ("https://*.example.com", LOGIN, Path("/unopened/owner.json")),
        ("https://-research.example.com", LOGIN, Path("/unopened/owner.json")),
        (ORIGIN, "", Path("/unopened/owner.json")),
        (ORIGIN, "owner", Path("/unopened/owner.json")),
        (ORIGIN, "tag:research", Path("/unopened/owner.json")),
        (ORIGIN, "owner@example.com,other@example.com", Path("/unopened/owner.json")),
        (ORIGIN, "owner@example.com\r\nHost: attacker", Path("/unopened/owner.json")),
    ],
)
def test_invalid_configuration_refuses_before_workspace_writes(
    tmp_path: Path, origin: str | None, login: str | None, owner_file: Path | None
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match=r"private|Tailscale"):
        WorkbenchServer(
            repo,
            repo / "data/cache/research",
            port=0,
            private_origin=origin,
            tailscale_owner=login,
            owner_file=owner_file,
        )
    assert list(repo.iterdir()) == []


def test_local_mode_and_exact_private_configuration() -> None:
    assert PrivateAccess.configure(None, None, None) is None
    assert PrivateAccess.configure(None, None, Path("/unopened/owner.json")) is None
    private = PrivateAccess.configure(ORIGIN, LOGIN, Path("/unopened/owner.json"))
    assert private == PrivateAccess(ORIGIN, "research.controlled-tailnet.ts.net", LOGIN)
    assert private is not None
    headers = Message()
    headers["Host"], headers["Tailscale-User-Login"] = private.host, LOGIN
    assert private.accepts(headers, method="GET")
    assert not private.accepts(headers, method="POST")
    headers["Origin"] = ORIGIN
    assert private.accepts(headers, method="POST")


def test_private_owner_and_canonical_workspace_errors_precede_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for workspace in (repo / "data/cache/research", repo / "data/cache/chain/.work-new"):
        with pytest.raises((ValueError, FileNotFoundError)):
            WorkbenchServer(
                repo,
                workspace,
                port=0,
                private_origin=ORIGIN,
                tailscale_owner=LOGIN,
                owner_file=tmp_path / "absent/owner.json",
            )
        assert list(repo.iterdir()) == []
    alias = tmp_path / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        WorkbenchServer(
            alias,
            alias / "data/cache/research",
            port=0,
            private_origin=ORIGIN,
            tailscale_owner=LOGIN,
            owner_file=tmp_path / "absent/owner.json",
        )
    assert list(repo.iterdir()) == []
