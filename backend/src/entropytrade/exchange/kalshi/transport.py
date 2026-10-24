"""HTTP transport that keeps the last response body and headers.

The SDK drops Kalshi's error ``code`` and does not surface rate-limit headers. Wrapping
the transport is how the gateway sees a 429 body and whatever limit headers the edge sends.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from entropytrade.domain.time import Clock, SystemClock


@dataclass(frozen=True)
class RawCapture:
    method: str
    path: str
    status: int
    body: bytes
    headers: dict[str, str]
    received_at: datetime


class ObservingTransport(httpx.AsyncBaseTransport):
    """Delegates to ``inner`` and remembers the last completed response."""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        capture: Callable[[RawCapture], None] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._inner = inner
        self._capture = capture
        self._clock = clock or SystemClock()
        self.last: RawCapture | None = None
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._inner.handle_async_request(request)
        await response.aread()
        self.calls += 1
        self.last = RawCapture(
            method=request.method,
            path=request.url.raw_path.decode("ascii"),
            status=response.status_code,
            body=bytes(response.content),
            headers=dict(response.headers.items()),
            received_at=self._clock.now(),
        )
        if self._capture is not None and not request.url.path.endswith("/api_keys"):
            self._capture(self.last)
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()
