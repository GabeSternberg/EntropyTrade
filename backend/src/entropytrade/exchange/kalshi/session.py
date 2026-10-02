"""Reconnect loop for a read-only market stream.

Each async iterator is one socket lifetime. When it raises ``ConnectionError`` the feed is
marked disconnected and the next iterator is a new subscription: the caller resubscribes,
and book deltas stay stale until that connection's snapshot. This module does not open a
socket. A live Kalshi session would feed it frames from ``frame_from_wire``.
"""

from collections.abc import AsyncIterator, Sequence

from entropytrade.exchange.frames import MarketFrame
from entropytrade.exchange.kalshi.stream import LiveIngest


async def run_connections(
    ingest: LiveIngest,
    connections: Sequence[AsyncIterator[MarketFrame]],
) -> int:
    """Drive one or more connections. The return value is how many were opened."""
    opened = 0
    for connection in connections:
        opened += 1
        try:
            await _one_connection(ingest, connection)
        except ConnectionError:
            continue
    return opened


async def _one_connection(ingest: LiveIngest, frames: AsyncIterator[MarketFrame]) -> None:
    started = False
    try:
        async for frame in frames:
            if not started:
                ingest.note_reconnect(frame.received_at)
                started = True
            ingest.push(frame)
    except ConnectionError:
        if ingest.feed.last_message_at is not None:
            ingest.note_disconnect(ingest.feed.last_message_at)
        raise
