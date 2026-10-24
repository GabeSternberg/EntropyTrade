"""Bounded, restartable collector. A socket lifetime is a durable recording session."""

import asyncio
import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import MarketStatus
from entropytrade.domain.historical import ApiOrigin
from entropytrade.domain.market import Market
from entropytrade.domain.time import utc_now
from entropytrade.exchange.feed import BookInvalidated, CollectorFeed, GapEffect, StaleBook

if TYPE_CHECKING:
    from entropytrade.exchange.frames import MarketFrame
from entropytrade.exchange.gateway import ExchangeGateway, GatewayError
from entropytrade.exchange.kalshi.wire import frame_from_wire
from entropytrade.exchange.sequence import GapKind
from entropytrade.storage.recorder import Recorder


class CollectorConfig(DomainModel):
    series: tuple[str, ...] = Field(min_length=1)
    events: tuple[str, ...] = ()
    refresh_seconds: int = Field(default=300, ge=5, le=3600)
    stale_seconds: int = Field(default=120, ge=2, le=3600)
    health_seconds: int = Field(default=10, ge=1, le=300)
    max_markets: int = Field(default=128, ge=1, le=1000)
    max_failures: int = Field(default=6, ge=1, le=20)
    max_bytes: int = Field(default=5_000_000_000, ge=100_000)


class Stream(Protocol):
    async def recv(self) -> str: ...


StreamFactory = Callable[[tuple[str, ...]], AbstractAsyncContextManager[Stream]]
Emit = Callable[[str], None]


def check_space(path: Path, limit: int) -> None:
    size = sum(
        p.stat().st_size for p in (path, Path(f"{path}-wal"), Path(f"{path}-shm")) if p.exists()
    )
    if size >= limit:
        raise OSError("recording disk budget reached; archive the closed database before resuming")


async def discover(gateway: ExchangeGateway, config: CollectorConfig) -> tuple[Market, ...]:
    markets: dict[str, Market] = {}
    for series in config.series:
        for market in await gateway.list_markets(series_ticker=series, status=MarketStatus.ACTIVE):
            if not config.events or market.event_ticker in config.events:
                markets[market.ticker] = market
    if len(markets) > config.max_markets:
        raise ValueError("discovery exceeds max_markets; narrow the configured universe")
    return tuple(markets[t] for t in sorted(markets))


def ingest_message(
    store: Recorder, feed: CollectorFeed, *, session: str, ordinal: int, raw: str
) -> bool:
    """Capture receipt time before decoding. Persist malformed messages before failing closed."""
    received = utc_now()
    frame: MarketFrame | None = None
    try:
        envelope: object = json.loads(raw)
        if isinstance(envelope, dict) and envelope.get("type") == "error":
            raise ValueError("subscription rejected")
        frame = frame_from_wire(envelope, received_at=received)
        effects = () if frame is None else feed.apply(frame)
    except (ValueError, GatewayError):
        store.record_message(
            session=session,
            ordinal=ordinal,
            raw=raw,
            received_at=received,
            frame=None,
            error="decode_or_subscription_error",
        )
        raise ConnectionError("invalid stream message") from None
    store.record_message(
        session=session,
        ordinal=ordinal,
        raw=raw,
        received_at=received,
        frame=frame,
        effects=tuple(
            json.dumps(
                {"kind": type(e).__name__, "value": e.model_dump(mode="json")}, sort_keys=True
            )
            for e in effects
        ),
    )
    return any(
        isinstance(e, StaleBook | BookInvalidated)
        or (isinstance(e, GapEffect) and e.kind is not GapKind.DUPLICATE)
        for e in effects
    )


async def collect(
    *,
    gateway: ExchangeGateway,
    store: Recorder,
    config: CollectorConfig,
    stream_factory: StreamFactory,
    stop: asyncio.Event,
    emit: Emit,
) -> None:
    failures = 0
    while not stop.is_set():
        check_space(store.path, config.max_bytes)
        session = store.start_session(utc_now())
        feed = CollectorFeed()
        reason = "shutdown"
        started = asyncio.get_running_loop().time()
        try:
            markets = await discover(gateway, config)
            for market in markets:
                check_space(store.path, config.max_bytes)
                store.save_market(
                    market,
                    ApiOrigin.LIVE,
                    raw_receipt_id=store.market_receipt(market.ticker, market.rules.captured_at),
                )
            if not markets:
                raise ConnectionError("no active markets")
            tickers = tuple(m.ticker for m in markets)
            feed.expect(tickers)
            async with stream_factory(tickers) as socket:
                feed.note_reconnect(utc_now())
                ordinal = 0
                last_health = 0.0
                while not stop.is_set():
                    check_space(store.path, config.max_bytes)
                    now = utc_now()
                    elapsed = asyncio.get_running_loop().time() - started
                    if elapsed >= config.refresh_seconds:
                        reason = "scheduled_discovery"
                        break
                    if elapsed > 60 and not feed.health(now).stale_tickers:
                        failures = 0  # Healthy quiet sessions also reset the reconnect budget.
                    if elapsed > config.stale_seconds and feed.health(now).stale_tickers:
                        raise ConnectionError("initial snapshots incomplete")
                    if feed.expire(now, config.stale_seconds):
                        raise ConnectionError("stale book requires a new snapshot")
                    if elapsed - last_health >= config.health_seconds or ordinal == 0:
                        payload = feed.health(now).model_dump_json()
                        store.save_health(payload, now)
                        emit(payload)
                        last_health = elapsed
                    try:
                        raw = await asyncio.wait_for(socket.recv(), timeout=1)
                    except TimeoutError:
                        continue
                    ordinal += 1
                    if ingest_message(store, feed, session=session, ordinal=ordinal, raw=raw):
                        raise ConnectionError("integrity failure requires resubscription")
                    if elapsed > 60:
                        failures = 0
        except (ConnectionError, GatewayError) as exc:
            reason = type(exc).__name__
            failures += 1
            emit(json.dumps({"state": "retrying", "reason": reason, "attempt": failures}))
            if failures >= config.max_failures:
                raise ConnectionError("collector retry budget exhausted; inspect health") from None
        finally:
            feed.note_disconnect(utc_now())
            payload = feed.health(utc_now()).model_dump_json()
            store.save_health(payload, utc_now())
            emit(payload)
            store.end_session(session, utc_now(), reason)
        if reason != "scheduled_discovery" and not stop.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=min(30, 2**failures))
