"""HTTP transport that keeps the last response body and headers.

The SDK drops Kalshi's error ``code`` and does not surface rate-limit headers. Wrapping
the transport is how the gateway sees a 429 body and whatever limit headers the edge sends.
"""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class RawCapture:
    method: str
    path: str
    status: int
    body: bytes
    headers: dict[str, str]


class ObservingTransport(httpx.AsyncBaseTransport):
    """Delegates to ``inner`` and remembers the last completed response."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner
        self.last: RawCapture | None = None
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._inner.handle_async_request(request)
        await response.aread()
        self.calls += 1
        self.last = RawCapture(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            body=bytes(response.content),
            headers=dict(response.headers.items()),
        )
        return response
