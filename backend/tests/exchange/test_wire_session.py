"""WebSocket envelopes and a dropped socket, with no network."""

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

from entropytrade.exchange.feed import CollectorFeed
from entropytrade.exchange.frames import MarketFrame
from entropytrade.exchange.kalshi.session import run_connections
from entropytrade.exchange.kalshi.stream import LiveIngest
from entropytrade.exchange.kalshi.wire import frame_from_wire
from tests.exchange.test_feed_recorder import TICKER, WHEN, _delta, _snapshot


def test_snapshot_envelope_becomes_a_domain_frame() -> None:
    frame = frame_from_wire(
        {
            "type": "orderbook_snapshot",
            "sid": 7,
            "seq": 1,
            "msg": {
                "market_ticker": TICKER,
                "market_id": "m1",
                "yes_dollars_fp": [["0.4200", "10.00"]],
                "no_dollars_fp": [["0.5600", "4.00"]],
            },
        },
        received_at=WHEN,
    )
    assert frame is not None
    assert frame.channel == "orderbook_snapshot"
    ack = frame_from_wire(
        {"type": "subscribed", "msg": {"channel": "trade", "sid": 3}},
        received_at=WHEN,
    )
    assert ack is None


def test_dropped_socket_resyncs_from_the_next_snapshot() -> None:
    ingest = LiveIngest(CollectorFeed())

    async def dropped() -> AsyncIterator[MarketFrame]:
        yield _snapshot(1)
        raise ConnectionError("socket dropped")

    async def resumed() -> AsyncIterator[MarketFrame]:
        yield _delta(2)
        yield _snapshot(3, yes="0.4100")

    opened = asyncio.run(run_connections(ingest, (dropped(), resumed())))
    assert opened == 2
    book = ingest.feed.book(TICKER)
    assert book is not None
    assert book.best_bid is not None
    assert book.best_bid.price == Decimal("0.4100")
    assert book.best_bid.quantity == Decimal("10.00")
    assert ingest.feed.connected is True
