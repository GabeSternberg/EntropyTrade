"""Sequence checks for channels the Kalshi SDK does not track.

The SDK's ``SequenceTracker`` follows ``orderbook_snapshot``, ``orderbook_delta`` and
``order_group_updates`` only. Trade and market-lifecycle frames carry a ``seq`` too, and a
recorder that ignores it cannot tell a gap from a quiet market. Book channels are checked
with the SDK tracker inside ``exchange.kalshi``; this module is the one used for the rest,
and for replaying a recording with no SDK at all.
"""

from dataclasses import dataclass
from enum import StrEnum


class GapKind(StrEnum):
    GAP = "gap"
    RESET = "reset"
    DUPLICATE = "duplicate"


BOOK_CHANNELS = frozenset({"orderbook_snapshot", "orderbook_delta"})
REFETCH_CHANNELS = frozenset({"trade", "market_lifecycle_v2"})


@dataclass(frozen=True)
class SequenceGap:
    """A break in one subscription's sequence. ``sid`` is the server subscription id."""

    channel: str
    sid: int
    expected: int
    received: int
    kind: GapKind


class SequenceWatch:
    """Per-subscription sequence watermark.

    The first frame on a subscription is accepted at whatever ``seq`` the server sends.
    A forward jump or a step backwards is a gap. An exact repeat is a duplicate and must
    not be applied twice. After a book gap the watch waits for a snapshot before it will
    accept another delta; trade and lifecycle gaps are reported and the watermark moves
    to the frame we did receive, so the next hole is still visible.
    """

    def __init__(self) -> None:
        self._last: dict[int, int] = {}
        self._awaiting_snapshot: set[int] = set()
        self.missing_seq: int = 0

    def reset(self) -> None:
        """Drop every watermark. Called on disconnect so the next session starts clean."""
        self._last.clear()
        self._awaiting_snapshot.clear()

    def observe(self, channel: str, sid: int, seq: int | None) -> SequenceGap | None:
        if seq is None:
            self.missing_seq += 1
            return None
        if sid in self._awaiting_snapshot:
            if channel == "orderbook_snapshot":
                self._last[sid] = seq
                self._awaiting_snapshot.discard(sid)
                return None
            return SequenceGap(channel, sid, self._last.get(sid, seq) + 1, seq, GapKind.GAP)

        last = self._last.get(sid)
        if last is None:
            self._last[sid] = seq
            return None
        if seq == last + 1:
            self._last[sid] = seq
            return None
        if seq == last:
            return SequenceGap(channel, sid, last + 1, seq, GapKind.DUPLICATE)

        kind = GapKind.RESET if seq < last else GapKind.GAP
        gap = SequenceGap(channel, sid, last + 1, seq, kind)
        if channel in BOOK_CHANNELS:
            self._awaiting_snapshot.add(sid)
            return gap
        self._last[sid] = seq
        return gap
