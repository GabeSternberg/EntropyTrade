"""NWS CLI labels for Philadelphia from a stored IEM pull. No socket.

The contract for ``KXHIGHPHIL`` on these dates names The Weather Company.
A CLI product is the closest public report for station CLIPHL. It is not
treated as the settlement value. Open-Meteo archive highs are a third
series, also not settlement.

``available_at`` is the UTC time in the product's WMO header
(``KPHI ddhhmm``). A product whose header falls on the observation day is
the afternoon "valid today" note. ``parse_cli_daily_high`` rejects it, and
it is not a label. The comparison uses the earliest header that falls on a
later calendar day.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.domain.time import ensure_utc
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.weather.recorded import RecordedBodyError, parse_cli_daily_high

_WMO = re.compile(r"KPHI\s+(\d{6})")
_SOURCE = "iem-nws-cli"
_STATION = "CLIPHL"


@dataclass(frozen=True)
class CliLabel:
    """One final CLI high. ``available_at`` is the WMO header time."""

    available_at: datetime
    source: str
    endpoint: str
    valid_on: date
    high_f: Decimal
    header: str


@dataclass(frozen=True)
class SettlementComparison:
    """Counts only. Open-Meteo is not a settlement source."""

    final_labels: int
    preliminary_skipped: int
    revised_days: int
    archive_days: int
    archive_exact_disagreements: int
    archive_rounded_disagreements: int
    archive_mean_absolute_difference: Decimal
    b80_markets: int
    b80_cli_disagreements: int
    b80_archive_disagreements: int
    nearby_markets: int
    nearby_cli_disagreements: int
    nearby_archive_disagreements: int
    contract_source: str


def load_comparison(root: Path) -> tuple[tuple[CliLabel, ...], SettlementComparison]:
    """Read the stored IEM body plus the Phase 4.50 archive and markets."""
    manifest = _mapping(_read(root / "iem" / "manifest.json"), "iem manifest")
    endpoint = _endpoint(manifest)
    ingested = _stamp(_text(manifest.get("fetched_at"), "fetched_at"))
    labels, preliminary, revised = _labels(root / "iem" / "cliphl-afos.txt", endpoint, ingested)
    archive = _archive(root / "open-meteo" / "archive.json")
    markets = _markets(root / "kalshi-demo" / "markets-aug23-oct01.json")
    return labels, _compare(labels, preliminary, revised, archive, markets)


def _labels(
    path: Path,
    endpoint: str,
    ingested_at: datetime,
) -> tuple[tuple[CliLabel, ...], int, int]:
    by_day: dict[date, list[CliLabel]] = {}
    preliminary = 0
    for product in _products(path.read_text(encoding="utf-8", errors="replace")):
        parsed = _one(product, endpoint, ingested_at)
        if parsed is None:
            preliminary += 1
            continue
        by_day.setdefault(parsed.valid_on, []).append(parsed)
    chosen: list[CliLabel] = []
    revised = 0
    for day in sorted(by_day):
        ordered = sorted(by_day[day], key=lambda item: item.available_at)
        chosen.append(ordered[0])
        if any(item.high_f != ordered[0].high_f for item in ordered[1:]):
            revised += 1
    return tuple(chosen), preliminary, revised


def _one(product: str, endpoint: str, ingested_at: datetime) -> CliLabel | None:
    header = _WMO.search(product)
    if header is None or "CLIPHL" not in product:
        return None
    stamp = header.group(1)
    # The date is read twice: once to place the header, once inside the CLI parser.
    rough = _rough_date(product)
    if rough is None:
        return None
    available = _header_time(stamp, rough)
    stored = ingested_at if ingested_at >= available else available
    try:
        high = parse_cli_daily_high(
            product,
            station=_STATION,
            available_at=available,
            ingested_at=stored,
        )
    except RecordedBodyError:
        return None
    return CliLabel(
        available_at=high.available_at,
        source=_SOURCE,
        endpoint=endpoint,
        valid_on=high.valid_on,
        high_f=high.high_f,
        header=stamp,
    )


def _rough_date(product: str) -> date | None:
    """Any FOR date in the product, used only to place the header's day-of-month."""
    try:
        probe = parse_cli_daily_high(
            product,
            station=_STATION,
            available_at=datetime(2099, 1, 2, tzinfo=UTC),
            ingested_at=datetime(2099, 1, 2, tzinfo=UTC),
        )
    except RecordedBodyError:
        return None
    return probe.valid_on


def _header_time(stamp: str, valid_on: date) -> datetime:
    day = int(stamp[:2])
    hour = int(stamp[2:4])
    minute = int(stamp[4:6])
    found: datetime | None = None
    for offset in range(-1, 5):
        candidate = valid_on + timedelta(days=offset)
        if candidate.day != day:
            continue
        found = datetime(candidate.year, candidate.month, candidate.day, hour, minute, tzinfo=UTC)
        break
    if found is None:
        raise RecordedBodyError(f"WMO day {day} is not near {valid_on}")
    return found


def _products(text: str) -> tuple[str, ...]:
    chunks = [chunk for chunk in text.split("\x01") if "CLIPHL" in chunk]
    return tuple(chunks)


def _compare(
    labels: Sequence[CliLabel],
    preliminary: int,
    revised: int,
    archive: Mapping[date, Decimal],
    markets: Sequence[Mapping[str, object]],
) -> SettlementComparison:
    by_day = {label.valid_on: label for label in labels}
    both = [day for day in by_day if day in archive]
    exact = 0
    rounded = 0
    total = Decimal(0)
    for day in both:
        cli = by_day[day].high_f
        other = archive[day]
        total += abs(other - cli)
        if other != cli:
            exact += 1
        if other.quantize(Decimal(1), rounding=ROUND_HALF_UP) != cli:
            rounded += 1
    b80_n, b80_cli, b80_archive = _market_counts(markets, by_day, archive, b80_only=True)
    near_n, near_cli, near_archive = _market_counts(markets, by_day, archive, b80_only=False)
    mean = total / Decimal(len(both)) if both else Decimal(0)
    return SettlementComparison(
        final_labels=len(labels),
        preliminary_skipped=preliminary,
        revised_days=revised,
        archive_days=len(both),
        archive_exact_disagreements=exact,
        archive_rounded_disagreements=rounded,
        archive_mean_absolute_difference=mean,
        b80_markets=b80_n,
        b80_cli_disagreements=b80_cli,
        b80_archive_disagreements=b80_archive,
        nearby_markets=near_n,
        nearby_cli_disagreements=near_cli,
        nearby_archive_disagreements=near_archive,
        contract_source="The Weather Company",
    )


def _market_counts(
    markets: Sequence[Mapping[str, object]],
    labels: Mapping[date, CliLabel],
    archive: Mapping[date, Decimal],
    *,
    b80_only: bool,
) -> tuple[int, int, int]:
    counted = 0
    cli_bad = 0
    archive_bad = 0
    for market in markets:
        ticker = market.get("ticker")
        result = market.get("result")
        if not isinstance(ticker, str) or result not in ("yes", "no"):
            continue
        if b80_only and not ticker.endswith("-B80.5"):
            continue
        if not b80_only and not ticker.startswith("KXHIGHPHIL-"):
            continue
        valid_on = ticker_target_date(ticker)
        if valid_on is None or valid_on not in archive:
            continue
        label = labels.get(valid_on)
        if label is None:
            continue
        strike = _strike(market)
        if strike is None:
            continue
        counted += 1
        official = result == "yes"
        if strike.resolves_yes(label.high_f) != official:
            cli_bad += 1
        if strike.resolves_yes(archive[valid_on]) != official:
            archive_bad += 1
    return counted, cli_bad, archive_bad


def _strike(market: Mapping[str, object]) -> Strike | None:
    raw = market.get("strike_type")
    if not isinstance(raw, str):
        return None
    try:
        kind = StrikeType(raw)
    except ValueError:
        return None
    floor = _optional_decimal(market.get("floor_strike"))
    cap = _optional_decimal(market.get("cap_strike"))
    try:
        strike = Strike(strike_type=kind, floor=floor, cap=cap)
    except ValueError:
        return None
    if not strike.is_evaluable:
        return None
    return strike


def _archive(path: Path) -> dict[date, Decimal]:
    body = _mapping(_read(path), path.name)
    daily = _mapping(body.get("daily"), "daily")
    times = _seq(daily.get("time"), "time")
    values = _seq(daily.get("temperature_2m_max"), "temperature_2m_max")
    found: dict[date, Decimal] = {}
    for stamp, raw in zip(times, values, strict=True):
        found[date.fromisoformat(_text(stamp, "date"))] = _decimal(raw, "high")
    return found


def _markets(path: Path) -> tuple[Mapping[str, object], ...]:
    body = _mapping(_read(path), path.name)
    return tuple(_mapping(item, "market") for item in _seq(body.get("markets"), "markets"))


def _endpoint(manifest: Mapping[str, object]) -> str:
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        url = item.get("url")
        if item.get("path") == "iem/cliphl-afos.txt" and isinstance(url, str):
            return url
    raise ValueError("IEM manifest has no CLIPHL endpoint")


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


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return ensure_utc(parsed)


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


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return _decimal(value, "strike")
