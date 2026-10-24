"""SDK connection/authentication with a lossless raw-message tap before SDK filtering.

The high-level SDK dispatcher discards duplicates/gaps before dispatch and doesn't expose
raw receipts. Use its public ConnectionManager, with our existing frame/feed boundary.
The only outbound WS commands here are the three fixed public-data subscriptions.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from kalshi.auth import KalshiAuth
from kalshi.errors import KalshiError
from kalshi.ws.connection import ConnectionManager
from websockets.exceptions import ConnectionClosed

from entropytrade.collector.service import Stream, StreamFactory
from entropytrade.domain.enums import KalshiEnvironment
from entropytrade.exchange.kalshi.config import kalshi_config_for, refuse_unknown_host_override


class ReadSocket:
    def __init__(self, connection: ConnectionManager) -> None:
        self._connection = connection

    async def recv(self) -> str:
        try:
            return await self._connection.recv()
        except (KalshiError, ConnectionClosed, OSError):
            raise ConnectionError("market-data socket disconnected") from None


def stream_factory(*, key_id: str, key_path: Path, environment: KalshiEnvironment) -> StreamFactory:
    @asynccontextmanager
    async def connect(tickers: tuple[str, ...]) -> AsyncIterator[Stream]:
        refuse_unknown_host_override()
        auth = KalshiAuth.from_key_path(key_id, key_path)
        connection = ConnectionManager(auth, kalshi_config_for(environment))
        try:
            await connection.connect()
            for index, channel in enumerate(("orderbook_delta", "trade", "market_lifecycle_v2"), 1):
                params: dict[str, object] = {"channels": [channel]}
                if channel != "market_lifecycle_v2":
                    params["market_tickers"] = list(tickers)
                await connection.send({"id": index, "cmd": "subscribe", "params": params})
            yield ReadSocket(connection)
        except (KalshiError, ConnectionClosed, OSError):
            raise ConnectionError("read-only subscription unavailable") from None
        finally:
            await connection.close()
            auth.close()

    return connect
