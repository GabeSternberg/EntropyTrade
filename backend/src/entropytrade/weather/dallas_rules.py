"""Dallas daily-high rules, with Philadelphia's thresholds left untouched.

The contract names station CLIDFW. The AFOS header office is KFWD. The
forecast request was frozen at the NWS Dallas/Fort Worth coordinates
before the score. The bracket, the 0.40 print, the 80.5 midpoint, and the
15:00 UTC decision are the ones already registered for Philadelphia. A
missing B80.5 market stays missing. A print is not a guaranteed fill.
Nothing here is promoted. This module does not open a socket.
"""

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.observations import Forecast
from entropytrade.exchange.historical_trades import _decode_time
from entropytrade.exchange.trade_prints import TradePrint
from entropytrade.weather.cli_observations import CliLabel
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    MIDPOINT,
    PRICE_THRESHOLD,
    RULE_NAMES,
    RuleScore,
    score_rules,
)
from entropytrade.weather.recorded import RecordedBodyError, parse_cli_daily_high

_STATION = "CLIDFW"
_OFFICE = "KFWD"
_SERIES = "KXHIGHTDAL"
_WMO = re.compile(rf"{_OFFICE}\s+(\d{{6}})")
_WINDOW_START = date(2026, 8, 23)
_WINDOW_END = date(2026, 10, 1)
_PRICE = Decimal(10000)
_COUNT = Decimal(100)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class DallasScore:
    """The registered rules on the Dallas window. Not a promotion."""

    series: str
    station: str
    label_days: int
    forecast_days: int
    print_count: int
    markets_found: int
    markets_missing: int
    hypotheses: int
    fidelity: str
    promoted: bool
    rules: tuple[RuleScore, ...]


def load_dallas_score(root: Path) -> DallasScore:
    """Score the stored Dallas rows. Thresholds come from the registered rules."""
    labels, forecasts, prints, found, missing = _inputs(root)
    rules = score_rules(labels, forecasts, prints)
    if tuple(rule.name for rule in rules) != RULE_NAMES:
        raise ValueError("Dallas did not score the registered rules")
    if any(not rule.tried or rule.promoted for rule in rules):
        raise ValueError("Dallas rules must be tried and not promoted")
    return DallasScore(
        series=_SERIES,
        station=_STATION,
        label_days=len(labels),
        forecast_days=len(forecasts),
        print_count=len(prints),
        markets_found=found,
        markets_missing=missing,
        hypotheses=len(rules),
        fidelity="trade-print",
        promoted=False,
        rules=rules,
    )


def _inputs(
    root: Path,
) -> tuple[tuple[CliLabel, ...], dict[date, Forecast], tuple[TradePrint, ...], int, int]:
    folder = root / "dallas"
    manifest = _object(folder / "manifest.json")
    _require_frozen(manifest)
    markets = _markets(folder / "markets.json")
    found = sum(1 for row in markets if row["http_status"] == 200)
    missing = sum(1 for row in markets if row["http_status"] == 404)
    if found + missing != len(markets):
        raise ValueError("an Dallas market has an unexpected status")
    if found != _count(manifest.get("markets_found"), "markets_found"):
        raise ValueError("the Dallas manifest does not match the market list")
    if missing != _count(manifest.get("markets_missing"), "markets_missing"):
        raise ValueError("the Dallas manifest does not match the missing markets")
    for row in markets:
        if row["http_status"] == 404 and "result" in row:
            raise ValueError("a missing Dallas market has a result")
    prints = _prints(folder)
    if len(prints) != _count(manifest.get("print_count"), "print_count"):
        raise ValueError("the Dallas table does not match the print count")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    labels = _labels(folder / "clidfw-afos.txt", ingested)
    built = _forecasts(folder / "previous-runs.json", labels)
    forecasts = {item.valid_from.date(): item for item in built}
    return labels, forecasts, prints, found, missing


def _require_frozen(manifest: dict[str, object]) -> None:
    if manifest.get("series") != _SERIES or manifest.get("station") != _STATION:
        raise ValueError("Dallas manifest names a different series or station")
    if manifest.get("header_office") != _OFFICE:
        raise ValueError("Dallas manifest names a different header office")
    if manifest.get("joined_to_philadelphia_replay") is not False:
        raise ValueError("Dallas rows must stay out of the Philadelphia replay")
    if manifest.get("promoted") is not False:
        raise ValueError("Dallas rules are not promoted")
    if _text(manifest.get("bracket_floor"), "bracket_floor") != str(BRACKET_FLOOR):
        raise ValueError("Dallas bracket floor was changed")
    if _text(manifest.get("bracket_cap"), "bracket_cap") != str(BRACKET_CAP):
        raise ValueError("Dallas bracket cap was changed")
    if Decimal(_text(manifest.get("price_threshold"), "price_threshold")) != PRICE_THRESHOLD:
        raise ValueError("Dallas price threshold was changed")
    if Decimal(_text(manifest.get("midpoint"), "midpoint")) != MIDPOINT:
        raise ValueError("Dallas midpoint was changed")
    if _count(manifest.get("decision_hour_utc"), "decision_hour_utc") != 15:
        raise ValueError("Dallas decision hour was changed")
    if _text(manifest.get("requested_latitude"), "requested_latitude") != "32.89743":
        raise ValueError("Dallas forecast latitude was changed after the freeze")
    if _text(manifest.get("requested_longitude"), "requested_longitude") != "-97.02196":
        raise ValueError("Dallas forecast longitude was changed after the freeze")


def _markets(path: Path) -> tuple[dict[str, object], ...]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Dallas markets are not a list")
    return tuple(_object_value(item, "market") for item in payload)


def _prints(folder: Path) -> tuple[TradePrint, ...]:
    database = folder / "prints.sqlite"
    found: list[TradePrint] = []
    with sqlite3.connect(database) as conn:
        endpoint = conn.execute("select url from endpoint").fetchone()
        if endpoint is None:
            raise ValueError("Dallas prints have no endpoint")
        query = "select ticker, created_us, yes_price, count, trade_id from prints"
        for ticker, created_us, price, count, trade_id in conn.execute(query):
            found.append(
                TradePrint(
                    trade_id=str(trade_id),
                    ticker=str(ticker),
                    created_at=_decode_time(int(created_us)),
                    fetched_at=_EPOCH,
                    endpoint=str(endpoint[0]),
                    yes_price=Decimal(int(price)) / _PRICE,
                    count=Decimal(int(count)) / _COUNT,
                )
            )
    return tuple(found)


def _labels(path: Path, ingested_at: datetime) -> tuple[CliLabel, ...]:
    text = path.read_text(encoding="utf-8", errors="replace")
    by_day: dict[date, list[CliLabel]] = {}
    for product in text.split("\x01"):
        if _STATION not in product:
            continue
        label = _one(product, path.name, ingested_at)
        if label is None or not _WINDOW_START <= label.valid_on <= _WINDOW_END:
            continue
        by_day.setdefault(label.valid_on, []).append(label)
    chosen: list[CliLabel] = []
    for day in sorted(by_day):
        ordered = sorted(by_day[day], key=lambda item: item.available_at)
        chosen.append(ordered[0])
    return tuple(chosen)


def _one(product: str, endpoint: str, ingested_at: datetime) -> CliLabel | None:
    header = _WMO.search(product)
    rough = _rough_date(product)
    if header is None or rough is None:
        return None
    available = _header_time(header.group(1), rough)
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
        source="iem-nws-cli",
        endpoint=endpoint,
        valid_on=high.valid_on,
        high_f=high.high_f,
        header=header.group(1),
    )


def _rough_date(product: str) -> date | None:
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


def _forecasts(path: Path, labels: tuple[CliLabel, ...]) -> tuple[Forecast, ...]:
    body = _object(path)
    hourly = body.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Dallas forecast has no hourly object")
    times = hourly.get("time")
    values = hourly.get("temperature_2m_previous_day1")
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
        raise ValueError("Dallas forecast hours and values disagree")
    by_day: dict[date, list[Decimal]] = {}
    for stamp, raw in zip(times, values, strict=True):
        if raw is None:
            raise ValueError("Dallas forecast has an empty hour")
        hour = datetime.fromisoformat(_text(stamp, "hour")).replace(tzinfo=UTC)
        if not _WINDOW_START <= hour.date() <= _WINDOW_END:
            continue
        by_day.setdefault(hour.date(), []).append(Decimal(str(raw)))
    if not labels:
        raise ValueError("Dallas has no CLI labels")
    ingested = max(label.available_at for label in labels)
    forecasts: list[Forecast] = []
    for valid_on, samples in sorted(by_day.items()):
        available = datetime(valid_on.year, valid_on.month, valid_on.day, tzinfo=UTC)
        run_time = available - timedelta(days=1)
        forecasts.append(
            Forecast(
                source_id="open-meteo-previous-day1",
                event_time=run_time,
                available_at=available,
                ingested_at=ingested,
                provider="open-meteo",
                model="previous_day1",
                run_time=run_time,
                location_id=_STATION,
                variable="daily_high_f",
                valid_from=available,
                valid_to=available.replace(hour=23, minute=59),
                value=max(samples),
                unit="degF",
            )
        )
    return tuple(forecasts)


def _object(path: Path) -> dict[str, object]:
    return _object_value(json.loads(path.read_text(encoding="utf-8")), path.name)


def _object_value(value: object, what: str) -> dict[str, object]:
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


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is not a count")
    return value
