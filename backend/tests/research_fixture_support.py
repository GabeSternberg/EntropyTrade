"""Replay real captured public responses (gzip, unmodified) through an httpx transport.

The fixtures under ``tests/fixtures/research`` were captured from the live public sources for
one fixed window (2026-11-06 to 2026-11-12, KXHIGHPHIL/CLIPHL). Tests that replay them are
controlled replays of authentic bytes, not live acquisition.
"""

import gzip
import json
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "research"


def recorded() -> dict[str, tuple[int, dict[str, str], bytes]]:
    index = json.loads((FIXTURES / "index.json").read_text())
    return {
        item["url"]: (
            int(item["status"]),
            dict(item["headers"]),
            gzip.decompress((FIXTURES / item["file"]).read_bytes()),
        )
        for item in index["responses"]
    }


class ReplayTransport(httpx.BaseTransport):
    """Serve recorded bytes by exact URL; anything else is a 404 and is counted."""

    def __init__(self, *, fail: set[str] | None = None) -> None:
        self.responses = recorded()
        self.requested: list[str] = []
        self.unknown: list[str] = []
        self.fail = fail or set()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requested.append(url)
        if any(part in url for part in self.fail):
            return httpx.Response(503, content=b"unavailable", request=request)
        if url not in self.responses:
            self.unknown.append(url)
            return httpx.Response(404, content=b"not recorded", request=request)
        status, headers, body = self.responses[url]
        return httpx.Response(status, headers=headers, content=body, request=request)
