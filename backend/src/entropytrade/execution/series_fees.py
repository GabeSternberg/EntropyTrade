"""Stored series fee fields. This module does not open a socket.

A series payload has ``fee_type`` and ``fee_multiplier``. It does not have the
quadratic coefficient from the general trading-fee table. Maker fractions come
from the fee-type description: makers pay nothing on ``quadratic``, 0.25 of the
taker coefficient on ``quadratic_with_maker_fees``, and 0.5 on
``quadratic_with_combo_maker_fees``. The coefficient itself stays an argument
because the fee-schedule PDF was not retrieved.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import FeeType
from entropytrade.domain.fees import FeeModelRef
from entropytrade.domain.time import ensure_utc
from entropytrade.execution.fees import FeeFormulaError, FeeSchedule

FEE_MODEL_VERSION = "series-fields-v1"

_MAKER_FRACTION: dict[FeeType, Decimal] = {
    FeeType.QUADRATIC: Decimal(0),
    FeeType.QUADRATIC_WITH_MAKER_FEES: Decimal("0.25"),
    FeeType.QUADRATIC_WITH_COMBO_MAKER_FEES: Decimal("0.5"),
}


@dataclass(frozen=True)
class StoredSeries:
    """Fee fields copied from one stored ``GET /series/{ticker}`` body."""

    ticker: str
    fee_type: FeeType
    fee_multiplier: Decimal
    maker_fraction: Decimal
    last_updated_at: datetime
    available_at: datetime
    endpoint: str

    @property
    def maker_pays(self) -> bool:
        return self.maker_fraction > Decimal(0)


@dataclass(frozen=True)
class SeriesFeeTable:
    """Series rows from ``data/public``. Empty fee-change arrays add no rows."""

    version: str
    rows: tuple[StoredSeries, ...]

    def match(self, market_ticker: str) -> StoredSeries:
        """Longest stored ticker that is the market ticker or its series prefix."""
        found = [
            row
            for row in self.rows
            if market_ticker == row.ticker or market_ticker.startswith(f"{row.ticker}-")
        ]
        if not found:
            raise KeyError(market_ticker)
        return max(found, key=lambda row: len(row.ticker))

    def schedule(self, series: StoredSeries, *, coefficient: Decimal) -> FeeSchedule:
        """Series fields from storage. ``coefficient`` is not in the payload."""
        if series.fee_type not in _MAKER_FRACTION:
            raise FeeFormulaError(f"{series.fee_type.value} has no stored maker fraction")
        return FeeSchedule(
            fee_type=series.fee_type,
            fee_multiplier=series.fee_multiplier,
            maker_pays=series.maker_pays,
            maker_fraction=series.maker_fraction,
            quadratic_coefficient=coefficient,
        )

    def fee_model(self, series: StoredSeries) -> FeeModelRef:
        """Identity recorded on a replay that used this series."""
        return FeeModelRef(
            version=self.version,
            fee_type=series.fee_type,
            fee_multiplier=series.fee_multiplier,
            maker_pays=series.maker_pays,
            effective_from=series.last_updated_at,
            notes="quadratic coefficient is not in the series payload",
        )


def load_series_fees(root: Path) -> SeriesFeeTable:
    """Read ``kalshi-fees`` series bodies. The PDF error file is not a series."""
    manifest = _mapping(_read(root / "kalshi-fees" / "manifest.json"), "manifest")
    calls = manifest.get("calls")
    if not isinstance(calls, list):
        raise ValueError("calls is not a list")
    rows: list[StoredSeries] = []
    for call in calls:
        item = _mapping(call, "call")
        status = item.get("status")
        path = _text(item.get("path"), "path")
        if status != 200 or not path.endswith(".json"):
            continue
        body = _read(root / path)
        if not isinstance(body, dict) or "series" not in body:
            continue
        series = _mapping(body.get("series"), "series")
        rows.append(
            StoredSeries(
                ticker=_text(series.get("ticker"), "ticker"),
                fee_type=_fee_type(_text(series.get("fee_type"), "fee_type")),
                fee_multiplier=_decimal(series.get("fee_multiplier")),
                maker_fraction=_fraction(_text(series.get("fee_type"), "fee_type")),
                last_updated_at=_stamp(_text(series.get("last_updated_ts"), "last_updated_ts")),
                available_at=_stamp(_text(item.get("fetched_at"), "fetched_at")),
                endpoint=_text(item.get("url"), "url"),
            )
        )
    return SeriesFeeTable(version=FEE_MODEL_VERSION, rows=tuple(rows))


def _fraction(fee_type: str) -> Decimal:
    parsed = _fee_type(fee_type)
    fraction = _MAKER_FRACTION.get(parsed)
    if fraction is None:
        raise FeeFormulaError(f"{parsed.value} has no stored maker fraction")
    return fraction


def _fee_type(value: str) -> FeeType:
    try:
        return FeeType(value)
    except ValueError as exc:
        raise ValueError(f"unknown fee_type {value!r}") from exc


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


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool | float):
        raise ValueError("fee multiplier is not an exact decimal")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError("fee multiplier is not an exact decimal")


def _stamp(value: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
