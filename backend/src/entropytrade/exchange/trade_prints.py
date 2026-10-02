"""Stored public trade prints. This module does not open a socket.

A print has the size the exchange reported for that trade. That size is not
a size at the touch, and the print is not a fill we received.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.time import ensure_utc

_RELATIVE = "kalshi-public/trades"


@dataclass(frozen=True)
class TradePrint:
    """One reported trade. ``count`` is ``count_fp``, not a book size."""

    trade_id: str
    ticker: str
    created_at: datetime
    fetched_at: datetime
    endpoint: str
    yes_price: Decimal
    count: Decimal


@dataclass(frozen=True)
class TradeTape:
    """Counts from the stored pull, plus the B80.5 prints used for scoring."""

    fetched_at: datetime
    host: str
    tickers: int
    trade_count: int
    tickers_with_trades: int
    failed_calls: int
    b805_prints: tuple[TradePrint, ...]


def load_trade_tape(root: Path) -> TradeTape:
    """Read ``kalshi-public/trades``. Empty pages add no prints."""
    folder = root / _RELATIVE
    manifest = _mapping(_read(folder / "manifest.json"), "manifest")
    calls = _seq(manifest.get("calls"), "calls")
    fetched_by_path: dict[str, tuple[datetime, str]] = {}
    for call in calls:
        item = _mapping(call, "call")
        path = item.get("path")
        url = item.get("url")
        stamp = item.get("fetched_at")
        if isinstance(path, str) and isinstance(url, str) and isinstance(stamp, str):
            fetched_by_path[path] = (_stamp(stamp), url)
    total = 0
    b805: list[TradePrint] = []
    for path in sorted((folder / "pages").glob("*.json")):
        relative = path.relative_to(root).as_posix()
        fetched_at, endpoint = fetched_by_path[relative]
        body = _mapping(_read(path), path.name)
        for trade in _seq(body.get("trades"), "trades"):
            row = _mapping(trade, "trade")
            total += 1
            ticker = _text(row.get("ticker"), "ticker")
            if not ticker.endswith("-B80.5"):
                continue
            b805.append(
                TradePrint(
                    trade_id=_text(row.get("trade_id"), "trade_id"),
                    ticker=ticker,
                    created_at=_stamp(_text(row.get("created_time"), "created_time")),
                    fetched_at=fetched_at,
                    endpoint=endpoint,
                    yes_price=_decimal(row.get("yes_price_dollars"), "yes_price"),
                    count=_decimal(row.get("count_fp"), "count"),
                )
            )
    declared = _count(manifest.get("trade_count"), "trade_count")
    if total != declared:
        raise ValueError("stored pages do not match the trade count")
    return TradeTape(
        fetched_at=_stamp(_text(manifest.get("fetched_at"), "fetched_at")),
        host=_text(manifest.get("host"), "host"),
        tickers=_count(manifest.get("tickers"), "tickers"),
        trade_count=total,
        tickers_with_trades=_count(manifest.get("tickers_with_trades"), "tickers_with_trades"),
        failed_calls=_count(manifest.get("failed_calls"), "failed_calls"),
        b805_prints=tuple(b805),
    )


def _read(path: Path) -> object:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return payload


def _mapping(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{what} has a non-string key")
        mapped[key] = item
    return mapped


def _seq(value: object, what: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a list")
    return tuple(value)


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is not a count")
    return value


def _decimal(value: object, what: str) -> Decimal:
    if isinstance(value, bool | float):
        raise ValueError(f"{what} is not an exact decimal")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError(f"{what} is not an exact decimal")


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return ensure_utc(parsed)
