"""Book-channel gaps use the SDK tracker. Trade and lifecycle use ours.

``LiveIngest`` is the seam between a WebSocket message we have already decoded into a
domain frame and the collector feed. Opening the socket is ``run_read_only_session``,
which is not exercised without a credential; the gap and reconnect behaviour is.
"""

from kalshi.ws.sequence import SequenceTracker

from entropytrade.domain.time import UtcDatetime
from entropytrade.exchange.feed import CollectorFeed, GapEffect, StreamEffect
from entropytrade.exchange.frames import MarketFrame
from entropytrade.exchange.sequence import BOOK_CHANNELS, GapKind, SequenceGap


class BookSequenceWatch:
    """SDK sequence tracker, restricted to the book channels it actually follows."""

    def __init__(self) -> None:
        self._tracker = SequenceTracker()

    def observe(self, channel: str, sid: int, seq: int | None) -> tuple[bool, SequenceGap | None]:
        if channel not in BOOK_CHANNELS:
            raise ValueError(f"book watch does not track {channel}")
        ok, gap = self._tracker.track_sync(sid, seq, channel)
        if gap is None:
            return ok, None
        kind = GapKind.RESET if gap.kind == "reset" else GapKind.GAP
        return ok, SequenceGap(channel, sid, gap.expected, gap.received, kind)


class LiveIngest:
    """Push decoded frames. Book gaps come from the SDK; everything else from ``CollectorFeed``."""

    def __init__(self, feed: CollectorFeed) -> None:
        self.feed = feed
        self._books = BookSequenceWatch()

    def note_disconnect(self, at: UtcDatetime) -> None:
        self.feed.note_disconnect(at)
        self._books = BookSequenceWatch()

    def note_reconnect(self, at: UtcDatetime) -> None:
        self.feed.note_reconnect(at)

    def push(self, frame: MarketFrame) -> tuple[StreamEffect, ...]:
        if frame.channel in BOOK_CHANNELS:
            return self._push_book(frame)
        return self.feed.apply(frame)

    def _push_book(self, frame: MarketFrame) -> tuple[StreamEffect, ...]:
        ok, gap = self._books.observe(frame.channel, frame.sid, frame.seq)
        if gap is not None:
            effect = GapEffect(
                channel=gap.channel,
                sid=gap.sid,
                expected=gap.expected,
                received=gap.received,
                kind=gap.kind,
            )
            self.feed.invalidate_sid(frame.sid, effect)
            return (effect,)
        if not ok:
            return (
                GapEffect(
                    channel=frame.channel,
                    sid=frame.sid,
                    expected=(frame.seq or 0),
                    received=frame.seq or 0,
                    kind=GapKind.DUPLICATE,
                ),
            )
        return self.feed.apply_trusted(frame)
