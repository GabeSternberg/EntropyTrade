"""Later KXHIGH cities, with the registered thresholds left untouched.

Each ticker is another attempt at the same four rules. A missing series or
a missing B80.5 market stays missing. Train, then validation. The holdout
is not scored. A print is not a guaranteed fill. Nothing here is promoted.
This module does not open a socket.
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
from entropytrade.weather.revision_bracket import bracket_note, down_note
from entropytrade.weather.revision_records import records_note, skipped_note
from entropytrade.weather.revision_rule import revision_lines
from entropytrade.weather.walk_forward import _thirds, reject_holdout

_WINDOW_START = date(2026, 8, 23)
_WINDOW_END = date(2026, 10, 1)
_PRICE = Decimal(10000)
_COUNT = Decimal(100)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_NOT_SCORED = "not scored"
_NOT_WALKED = "not walked"


@dataclass(frozen=True)
class ScannedCity:
    """One ticker. ``promoted`` stays false. The holdout is not scored."""

    ticker: str
    scored: bool
    promoted: bool
    markets_found: int
    markets_missing: int
    hypotheses: int
    holdout_scored: bool
    walked: bool
    rules: tuple[RuleScore, ...]
    validation: tuple[RuleScore, ...]


def load_kxhigh_scan(root: Path) -> tuple[ScannedCity, ...]:
    """Read every stored scan ticker, in the stored order."""
    folder = root / "kxhigh-scan"
    order = _order(folder / "order.json")
    return tuple(_one_city(folder / ticker, ticker) for ticker in order)


def render_kxhigh_scan(root: Path) -> str:
    """The research note. Optimistic equity is not a fill."""
    lines = [
        "# KXHIGH scan",
        "",
        "Each ticker is another attempt at the same four rules. The bracket,",
        "the 0.40 print, the 80.5 midpoint, and the 15:00 UTC decision are",
        "unchanged. Train, then validation. The holdout is not scored.",
        "Optimistic trade-print equity is not a fill. Nothing is promoted.",
        "",
        "| Ticker | Markets found | Optimistic equity | "
        "Validation optimistic equity | Base and conservative |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(_row(city) for city in load_kxhigh_scan(root))
    lines.append("")
    lines.extend(revision_lines(root))
    lines.extend(bracket_note(root))
    lines.append("")
    lines.append(records_note(root))
    lines.append("")
    lines.append(skipped_note(root))
    lines.append("")
    lines.extend(down_note(root))
    lines.append("")
    return "\n".join(lines)


def _one_city(folder: Path, ticker: str) -> ScannedCity:
    manifest = _object(folder / "manifest.json")
    if manifest.get("series") != ticker:
        raise ValueError(f"{ticker} manifest names a different series")
    if manifest.get("promoted") is not False:
        raise ValueError(f"{ticker} is promoted")
    scored = manifest.get("scored")
    if scored is True:
        return _scored(folder, ticker, manifest)
    if scored is not False:
        raise ValueError(f"{ticker} does not say whether it was scored")
    found = _count(manifest.get("markets_found"), "markets_found")
    missing = _count(manifest.get("markets_missing"), "markets_missing")
    _require_unscored_markets(folder, found, missing)
    return ScannedCity(
        ticker=ticker,
        scored=False,
        promoted=False,
        markets_found=found,
        markets_missing=missing,
        hypotheses=0,
        holdout_scored=False,
        walked=False,
        rules=(),
        validation=(),
    )


def _scored(folder: Path, ticker: str, manifest: dict[str, object]) -> ScannedCity:
    _require_frozen(manifest, ticker)
    station = _text(manifest.get("station"), "station")
    office = _text(manifest.get("header_office"), "header_office")
    markets = _markets(folder / "markets.json")
    found = sum(1 for row in markets if row.get("http_status") == 200)
    missing = sum(1 for row in markets if row.get("http_status") == 404)
    if found + missing != len(markets):
        raise ValueError(f"{ticker} has an unexpected market status")
    if found != _count(manifest.get("markets_found"), "markets_found"):
        raise ValueError(f"{ticker} manifest does not match the market list")
    if missing != _count(manifest.get("markets_missing"), "markets_missing"):
        raise ValueError(f"{ticker} manifest does not match the missing markets")
    if found == 0:
        raise ValueError(f"{ticker} was scored without a listed market")
    for row in markets:
        if row.get("http_status") == 404 and "result" in row:
            raise ValueError(f"{ticker} gives a result to a missing market")
    prints = _prints(folder)
    if len(prints) != _count(manifest.get("print_count"), "print_count"):
        raise ValueError(f"{ticker} table does not match the print count")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    labels = _labels(folder / "cli.txt", station, office, ingested)
    built = _forecasts(folder / "previous-runs.json", labels, station)
    forecasts = {item.valid_from.date(): item for item in built}
    rules = score_rules(labels, forecasts, prints)
    _require_rules(rules, ticker)
    train, validation, holdout = _thirds(labels)
    reject_holdout(
        {label.valid_on for label in train} | {label.valid_on for label in validation},
        {label.valid_on for label in holdout},
    )
    train_rules = score_rules(train, forecasts, prints)
    validation_rules = score_rules(validation, forecasts, prints)
    _require_rules(train_rules, ticker)
    _require_rules(validation_rules, ticker)
    return ScannedCity(
        ticker=ticker,
        scored=True,
        promoted=False,
        markets_found=found,
        markets_missing=missing,
        hypotheses=len(rules),
        holdout_scored=False,
        walked=True,
        rules=rules,
        validation=validation_rules,
    )


def _require_frozen(manifest: dict[str, object], ticker: str) -> None:
    if manifest.get("joined_to_philadelphia_replay") is not False:
        raise ValueError(f"{ticker} is joined to the Philadelphia replay")
    if _text(manifest.get("bracket_floor"), "bracket_floor") != str(BRACKET_FLOOR):
        raise ValueError(f"{ticker} bracket floor was changed")
    if _text(manifest.get("bracket_cap"), "bracket_cap") != str(BRACKET_CAP):
        raise ValueError(f"{ticker} bracket cap was changed")
    if Decimal(_text(manifest.get("price_threshold"), "price_threshold")) != PRICE_THRESHOLD:
        raise ValueError(f"{ticker} price threshold was changed")
    if Decimal(_text(manifest.get("midpoint"), "midpoint")) != MIDPOINT:
        raise ValueError(f"{ticker} midpoint was changed")
    if _count(manifest.get("decision_hour_utc"), "decision_hour_utc") != 15:
        raise ValueError(f"{ticker} decision hour was changed")
    if manifest.get("fidelity") != "trade-print":
        raise ValueError(f"{ticker} fidelity was changed")


def _require_rules(rules: tuple[RuleScore, ...], ticker: str) -> None:
    if tuple(rule.name for rule in rules) != RULE_NAMES:
        raise ValueError(f"{ticker} did not score the registered rules")
    for rule in rules:
        if not rule.tried or rule.promoted:
            raise ValueError(f"{ticker} rules must be tried and not promoted")
        if rule.scenarios[0].guaranteed_fill:
            raise ValueError(f"{ticker} treats a print as a fill")
        if rule.scenarios[1].assumed_fills != 0 or rule.scenarios[2].assumed_fills != 0:
            raise ValueError(f"{ticker} base or conservative took a fill")
        if rule.scenarios[1].equity != Decimal("100.000000"):
            raise ValueError(f"{ticker} base equity moved")
        if rule.scenarios[2].equity != Decimal("100.000000"):
            raise ValueError(f"{ticker} conservative equity moved")


def _require_unscored_markets(folder: Path, found: int, missing: int) -> None:
    path = folder / "markets.json"
    if not path.exists():
        if found != 0 or missing != 0:
            raise ValueError("an unscored ticker claims markets it did not store")
        return
    markets = _markets(path)
    listed = sum(1 for row in markets if row.get("http_status") == 200)
    absent = sum(1 for row in markets if row.get("http_status") == 404)
    if listed != found or absent != missing or listed + absent != len(markets):
        raise ValueError("the unscored market list does not match the manifest")
    if any("result" in row and row.get("http_status") == 404 for row in markets):
        raise ValueError("a missing market has a result")


def _row(city: ScannedCity) -> str:
    optimistic = _equities(city.rules) if city.scored else _NOT_SCORED
    validation = _equities(city.validation) if city.walked else _NOT_WALKED
    base = "100.000000" if city.scored else _NOT_SCORED
    cells = (city.ticker, str(city.markets_found), optimistic, validation, base)
    return "| " + " | ".join(cells) + " |"


def _equities(rules: tuple[RuleScore, ...]) -> str:
    return ", ".join(format(rule.scenarios[0].equity, "f") for rule in rules)


def _order(path: Path) -> tuple[str, ...]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("the scan order is empty")
    tickers: list[str] = []
    for item in payload:
        if not isinstance(item, str) or item == "":
            raise ValueError("the scan order is not a list of tickers")
        tickers.append(item)
    if len(set(tickers)) != len(tickers):
        raise ValueError("the scan order repeats a ticker")
    return tuple(tickers)


def _markets(path: Path) -> tuple[dict[str, object], ...]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} is not a list")
    return tuple(_object_value(item, "market") for item in payload)


def _prints(folder: Path) -> tuple[TradePrint, ...]:
    database = folder / "prints.sqlite"
    found: list[TradePrint] = []
    with sqlite3.connect(database) as conn:
        endpoint = conn.execute("select url from endpoint").fetchone()
        if endpoint is None:
            raise ValueError("prints have no endpoint")
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


def _labels(path: Path, station: str, office: str, ingested_at: datetime) -> tuple[CliLabel, ...]:
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"{office}\s+(\d{{6}})")
    by_day: dict[date, list[CliLabel]] = {}
    for product in text.split("\x01"):
        if station not in product:
            continue
        label = _label(product, path.name, station, pattern, ingested_at)
        if label is None or not _WINDOW_START <= label.valid_on <= _WINDOW_END:
            continue
        by_day.setdefault(label.valid_on, []).append(label)
    chosen: list[CliLabel] = []
    for day in sorted(by_day):
        ordered = sorted(by_day[day], key=lambda item: item.available_at)
        chosen.append(ordered[0])
    if len(chosen) < 4:
        raise ValueError("the stored days do not fill train, validation, and holdout")
    return tuple(chosen)


def _label(
    product: str,
    endpoint: str,
    station: str,
    pattern: re.Pattern[str],
    ingested_at: datetime,
) -> CliLabel | None:
    header = pattern.search(product)
    rough = _rough_date(product, station)
    if header is None or rough is None:
        return None
    available = _header_time(header.group(1), rough)
    stored = ingested_at if ingested_at >= available else available
    try:
        high = parse_cli_daily_high(
            product,
            station=station,
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


def _rough_date(product: str, station: str) -> date | None:
    try:
        probe = parse_cli_daily_high(
            product,
            station=station,
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


def _forecasts(path: Path, labels: tuple[CliLabel, ...], station: str) -> tuple[Forecast, ...]:
    body = _object(path)
    hourly = body.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("forecast has no hourly object")
    times = hourly.get("time")
    values = hourly.get("temperature_2m_previous_day1")
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
        raise ValueError("forecast hours and values disagree")
    by_day: dict[date, list[Decimal]] = {}
    for stamp, raw in zip(times, values, strict=True):
        if raw is None:
            raise ValueError("forecast has an empty hour")
        hour = datetime.fromisoformat(_text(stamp, "hour")).replace(tzinfo=UTC)
        if not _WINDOW_START <= hour.date() <= _WINDOW_END:
            continue
        by_day.setdefault(hour.date(), []).append(Decimal(str(raw)))
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
                location_id=station,
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
