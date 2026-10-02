"""Applies recorded frames to local books and reports sequence gaps.

This is the streaming surface strategies and the recorder share. It does not open a socket.
A dropped session is ``note_disconnect`` followed by ``note_reconnect``; deltas are refused
until a snapshot arrives, which is the same recovery a live reconnect has to do.
"""

from datetime import datetime

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.market_data import OrderBook, TradePrint
from entropytrade.domain.time import UtcDatetime
from entropytrade.exchange.book import BookError, LocalBook, signed_quantity
from entropytrade.exchange.frames import (
    BookDeltaFrame,
    BookSnapshotFrame,
    MarketFrame,
    TradeFrame,
    frame_levels,
)
from entropytrade.exchange.sequence import BOOK_CHANNELS, GapKind, SequenceGap, SequenceWatch


class AppliedBook(DomainModel):
    book: OrderBook


class AppliedTrade(DomainModel):
    trade: TradePrint


class AppliedLifecycle(DomainModel):
    market_ticker: str
    event_type: str
    sequence: int | None
    exchange_index: int | None
    received_at: UtcDatetime


class GapEffect(DomainModel):
    channel: str
    sid: int
    expected: int
    received: int
    kind: GapKind


class StaleBook(DomainModel):
    """A delta arrived before a snapshot. The frame was not applied."""

    market_ticker: str
    sid: int
    sequence: int


class FeedHealth(DomainModel):
    connected: bool
    last_message_at: UtcDatetime | None
    last_gap: GapEffect | None
    stale_tickers: tuple[str, ...]
    missing_sequence_frames: int = Field(ge=0)
    lag_seconds: float | None = None


StreamEffect = AppliedBook | AppliedTrade | AppliedLifecycle | GapEffect | StaleBook


class CollectorFeed:
    """In-memory book state plus the sequence watch for every channel."""

    def __init__(self) -> None:
        self._books: dict[str, LocalBook] = {}
        self._sid_tickers: dict[int, set[str]] = {}
        self._stale: set[str] = set()
        self._watch = SequenceWatch()
        self.connected = False
        self.last_message_at: datetime | None = None
        self.last_gap: GapEffect | None = None

    def note_disconnect(self, at: datetime) -> None:
        self.connected = False
        self.last_message_at = at
        self._watch.reset()
        for ticker, book in self._books.items():
            book.wipe()
            self._stale.add(ticker)

    def note_reconnect(self, at: datetime) -> None:
        self.connected = True
        self.last_message_at = at

    def book(self, market_ticker: str) -> OrderBook | None:
        local = self._books.get(market_ticker)
        if local is None or not local.ready or local.sequence is None:
            return None
        received = self.last_message_at
        if received is None:
            return None
        return local.view(received_at=received)

    def health(self, now: datetime) -> FeedHealth:
        lag = None
        if self.last_message_at is not None:
            lag = (now - self.last_message_at).total_seconds()
        return FeedHealth(
            connected=self.connected,
            last_message_at=self.last_message_at,
            last_gap=self.last_gap,
            stale_tickers=tuple(sorted(self._stale)),
            missing_sequence_frames=self._watch.missing_seq,
            lag_seconds=lag,
        )

    def apply(self, frame: MarketFrame) -> tuple[StreamEffect, ...]:
        # A delta before the post-reconnect snapshot must not move the watermark.
        # The snapshot that follows is the new sequence, often starting again at 1.
        if isinstance(frame, BookDeltaFrame) and not self._book_ready(frame.market_ticker):
            self.last_message_at = frame.received_at
            return (self._stale_delta(frame),)
        self.last_message_at = frame.received_at
        gap = self._watch.observe(frame.channel, frame.sid, frame.seq)
        if gap is not None:
            effect = _gap_effect(gap)
            if gap.kind is not GapKind.DUPLICATE:
                self.last_gap = effect
            if gap.kind is GapKind.DUPLICATE:
                return (effect,)
            if frame.channel in BOOK_CHANNELS:
                self._invalidate(frame.sid)
                return (effect,)
            # Trade and lifecycle gaps are recorded, then the frame is still stored:
            # the hole is real, and dropping the message we did receive would hide it.
            return (effect, *self._apply_payload(frame))
        return self._apply_payload(frame)

    def apply_trusted(self, frame: MarketFrame) -> tuple[StreamEffect, ...]:
        """Apply a frame the SDK book tracker has already accepted.

        Book gaps are decided by ``kalshi.ws.sequence.SequenceTracker`` before this is
        called. Running them through :meth:`apply` as well would report the same hole twice.
        """
        self.last_message_at = frame.received_at
        return self._apply_payload(frame)

    def invalidate_sid(self, sid: int, gap: GapEffect) -> None:
        self.last_gap = gap
        self._invalidate(sid)

    def _apply_payload(self, frame: MarketFrame) -> tuple[StreamEffect, ...]:
        if isinstance(frame, BookSnapshotFrame):
            local = self._local(frame.market_ticker)
            book = local.apply_snapshot(
                frame_levels(frame.yes),
                frame_levels(frame.no),
                sequence=frame.seq,
                received_at=frame.received_at,
                exchange_ts=frame.exchange_ts,
            )
            self._sid_tickers.setdefault(frame.sid, set()).add(frame.market_ticker)
            self._stale.discard(frame.market_ticker)
            return (AppliedBook(book=book),)
        if isinstance(frame, BookDeltaFrame):
            if not self._book_ready(frame.market_ticker):
                return (self._stale_delta(frame),)
            existing = self._books[frame.market_ticker]
            try:
                book = existing.apply_delta(
                    frame.side,
                    frame.price,
                    signed_quantity(frame.delta),
                    sequence=frame.seq,
                    received_at=frame.received_at,
                    exchange_ts=frame.exchange_ts,
                )
            except BookError:
                return (
                    StaleBook(
                        market_ticker=frame.market_ticker,
                        sid=frame.sid,
                        sequence=frame.seq,
                    ),
                )
            return (AppliedBook(book=book),)
        if isinstance(frame, TradeFrame):
            trade = TradePrint(
                trade_id=frame.trade_id,
                market_ticker=frame.market_ticker,
                yes_price=frame.yes_price,
                quantity=frame.quantity,
                taker_side=frame.taker_side,
                executed_at=frame.executed_at,
                received_at=frame.received_at,
                is_block_trade=frame.is_block_trade,
            )
            return (AppliedTrade(trade=trade),)
        lifecycle = frame
        return (
            AppliedLifecycle(
                market_ticker=lifecycle.market_ticker,
                event_type=lifecycle.event_type,
                sequence=lifecycle.seq,
                exchange_index=lifecycle.exchange_index,
                received_at=lifecycle.received_at,
            ),
        )

    def _book_ready(self, ticker: str) -> bool:
        local = self._books.get(ticker)
        return local is not None and local.ready and ticker not in self._stale

    def _stale_delta(self, frame: BookDeltaFrame) -> StaleBook:
        return StaleBook(market_ticker=frame.market_ticker, sid=frame.sid, sequence=frame.seq)

    def _local(self, ticker: str) -> LocalBook:
        book = self._books.get(ticker)
        if book is None:
            book = LocalBook(ticker)
            self._books[ticker] = book
        return book

    def _invalidate(self, sid: int) -> None:
        for ticker in self._sid_tickers.get(sid, ()):
            local = self._books.get(ticker)
            if local is not None:
                local.wipe()
            self._stale.add(ticker)


def _gap_effect(gap: SequenceGap) -> GapEffect:
    return GapEffect(
        channel=gap.channel,
        sid=gap.sid,
        expected=gap.expected,
        received=gap.received,
        kind=gap.kind,
    )
