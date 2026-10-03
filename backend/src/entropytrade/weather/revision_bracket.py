"""Revision >= 2°F, traded on the stored between-contract that contains it.

The 80-81 gate is not applied. ``2°F`` and ``0.40`` are not fit to equity.
If the containing contract is missing from the stored tape, or two stored
between-contracts contain the later max, there is no trade. A neighbor is
not substituted. A print is not a guaranteed fill. This module does not
open a socket.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.domain.numeric import parse_money
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.exchange.trade_prints import TradePrint, load_all_prints
from entropytrade.weather.austin_rules import _labels as _austin_labels
from entropytrade.weather.austin_rules import _prints as _austin_prints
from entropytrade.weather.chicago_rules import _labels as _chicago_labels
from entropytrade.weather.chicago_rules import _prints as _chicago_prints
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.dallas_rules import _labels as _dallas_labels
from entropytrade.weather.dallas_rules import _prints as _dallas_prints
from entropytrade.weather.informational_rules import BRACKET_CAP, BRACKET_FLOOR, PRICE_THRESHOLD
from entropytrade.weather.newyork_rules import _labels as _newyork_labels
from entropytrade.weather.newyork_rules import _prints as _newyork_prints
from entropytrade.weather.oklahomacity_rules import _labels as _oklahomacity_labels
from entropytrade.weather.oklahomacity_rules import _prints as _oklahomacity_prints
from entropytrade.weather.revision_rule import (
    DECISION_HOUR_UTC,
    REVISION_MINIMUM_F,
    RevisionFold,
    _clock,
    _decision,
    _maxes,
    _object,
    _require_call,
    _text,
)
from entropytrade.weather.walk_forward import _thirds, reject_holdout

RULE_NAME = "forecast_revision_bracket"
FIDELITY = "trade-print"
_ONE = Decimal(1)
_VINTAGES = Path("open-meteo/revision-vintages.json")
_CHICAGO = Path("chicago/revision-vintages.json")


@dataclass(frozen=True)
class StoredBracket:
    """One stored between-contract. Ends are inclusive."""

    ticker: str
    valid_on: date
    floor: Decimal
    cap: Decimal


@dataclass(frozen=True)
class BracketRevision:
    """One city. ``promoted`` stays false. The holdout is not scored."""

    name: str
    place: str
    hypotheses: int
    scored: bool
    promoted: bool
    fidelity: str
    guaranteed_fill: bool
    holdout_scored: bool
    train_days: int
    validation_days: int
    holdout_days: int
    train: RevisionFold
    validation: RevisionFold


def load_philadelphia_bracket(root: Path) -> BracketRevision:
    """Score Philadelphia. Thresholds stay at 2°F and 0.40."""
    _frozen()
    labels, _comparison = load_comparison(root)
    return _score_city(
        root / _VINTAGES,
        "Philadelphia",
        labels,
        _brackets(root / "kalshi-public"),
        _tape(root / "kalshi-public" / "trades" / "manifest.json"),
        load_all_prints(root),
    )


def load_chicago_bracket(root: Path) -> BracketRevision:
    """Score Chicago on the same rule. Thresholds stay at 2°F and 0.40."""
    folder = root / "chicago"
    manifest = _object(folder / "manifest.json")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    prints = _chicago_prints(folder)
    return _score_registered(
        folder,
        "Chicago",
        _chicago_labels(folder / "climdw-afos.txt", ingested),
        prints,
    )


def load_newyork_bracket(root: Path) -> BracketRevision:
    """Score New York on the same rule. Thresholds stay at 2°F and 0.40."""
    folder = root / "newyork"
    manifest = _object(folder / "manifest.json")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    prints = _newyork_prints(folder)
    return _score_registered(
        folder,
        "New York",
        _newyork_labels(folder / "clinyc-afos.txt", ingested),
        prints,
    )


def load_dallas_bracket(root: Path) -> BracketRevision:
    """Score Dallas on the same rule. Thresholds stay at 2°F and 0.40."""
    folder = root / "dallas"
    manifest = _object(folder / "manifest.json")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    prints = _dallas_prints(folder)
    return _score_registered(
        folder,
        "Dallas",
        _dallas_labels(folder / "clidfw-afos.txt", ingested),
        prints,
    )


def load_austin_bracket(root: Path) -> BracketRevision:
    """Score Austin on the same rule. Thresholds stay at 2°F and 0.40."""
    folder = root / "austin"
    manifest = _object(folder / "manifest.json")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    prints = _austin_prints(folder)
    return _score_registered(
        folder,
        "Austin",
        _austin_labels(folder / "cliaus-afos.txt", ingested),
        prints,
    )


def load_oklahomacity_bracket(root: Path) -> BracketRevision:
    """Score Oklahoma City on the same rule. Thresholds stay at 2°F and 0.40."""
    folder = root / "oklahomacity"
    manifest = _object(folder / "manifest.json")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    prints = _oklahomacity_prints(folder)
    return _score_registered(
        folder,
        "Oklahoma City",
        _oklahomacity_labels(folder / "cliokc-afos.txt", ingested),
        prints,
    )


def load_scan_bracket(root: Path, ticker: str) -> BracketRevision:
    """Score one stored scan city on the same rule. Thresholds stay put."""
    folder = root / "kxhigh-scan" / ticker
    manifest = _object(folder / "manifest.json")
    if manifest.get("series") != ticker or manifest.get("scored") is not True:
        raise ValueError(f"{ticker} is not a scored scan city")
    if manifest.get("promoted") is not False:
        raise ValueError(f"{ticker} is promoted")
    from entropytrade.weather.kxhigh_scan import _labels as scan_labels
    from entropytrade.weather.kxhigh_scan import _prints as scan_prints

    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    prints = scan_prints(folder)
    labels = scan_labels(
        folder / "cli.txt",
        _text(manifest.get("station"), "station"),
        _text(manifest.get("header_office"), "header_office"),
        ingested,
    )
    return _score_registered(
        folder,
        _text(manifest.get("place"), "place"),
        labels,
        prints,
    )


def bracket_note(root: Path) -> tuple[str, ...]:
    """Scan-note paragraphs. They do not invent a neighbor."""
    lines = ["", _sentence(load_philadelphia_bracket(root))]
    for loader, path in (
        (load_chicago_bracket, root / _CHICAGO),
        (load_newyork_bracket, root / "newyork" / "revision-vintages.json"),
        (load_austin_bracket, root / "austin" / "revision-vintages.json"),
        (load_oklahomacity_bracket, root / "oklahomacity" / "revision-vintages.json"),
        (load_dallas_bracket, root / "dallas" / "revision-vintages.json"),
    ):
        if path.exists():
            lines.extend(("", _sentence(loader(root))))
    for ticker in (
        "KXHIGHDEN",
        "KXHIGHTSDF",
        "KXHIGHTBOS",
        "KXHIGHTMIN",
        "KXHIGHTSFO",
        "KXHIGHTSAN",
        "KXHIGHTEWR",
        "KXHIGHTTTN",
    ):
        path = root / "kxhigh-scan" / ticker / "revision-vintages.json"
        if path.exists():
            lines.extend(("", _sentence(load_scan_bracket(root, ticker))))
    return tuple(lines)


def _score_city(
    path: Path,
    place: str,
    labels: tuple[CliLabel, ...],
    brackets: Mapping[date, tuple[StoredBracket, ...]],
    tape: frozenset[str],
    prints: tuple[TradePrint, ...],
) -> BracketRevision:
    later, earlier, clock = _maxes(_object(path))
    if clock != "rule":
        raise ValueError("the revision clock is not the stored rule")
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    train, validation, holdout = _thirds(ordered)
    reject_holdout(
        {label.valid_on for label in train} | {label.valid_on for label in validation},
        {label.valid_on for label in holdout},
    )
    by_ticker = _prints_by_ticker(prints)
    train_fold = _fold(train, brackets, tape, by_ticker, later, earlier)
    validation_fold = _fold(validation, brackets, tape, by_ticker, later, earlier)
    _require_flat(train_fold, place)
    _require_flat(validation_fold, place)
    return BracketRevision(
        name=RULE_NAME,
        place=place,
        hypotheses=1,
        scored=True,
        promoted=False,
        fidelity=FIDELITY,
        guaranteed_fill=False,
        holdout_scored=False,
        train_days=len(train),
        validation_days=len(validation),
        holdout_days=len(holdout),
        train=train_fold,
        validation=validation_fold,
    )


def _fold(
    labels: tuple[CliLabel, ...],
    brackets: Mapping[date, tuple[StoredBracket, ...]],
    tape: frozenset[str],
    by_ticker: Mapping[str, tuple[TradePrint, ...]],
    later: Mapping[date, Decimal],
    earlier: Mapping[date, Decimal],
) -> RevisionFold:
    fires = 0
    hits = 0
    pnl: list[Decimal] = []
    for label in labels:
        decision = _decision(label.valid_on)
        later_at, earlier_at = _clock(label.valid_on)
        if later_at > decision or earlier_at > decision:
            continue
        if later_at >= label.available_at or earlier_at >= label.available_at:
            continue
        later_max = later.get(label.valid_on)
        earlier_max = earlier.get(label.valid_on)
        if later_max is None or earlier_max is None:
            continue
        if later_max - earlier_max < REVISION_MINIMUM_F:
            continue
        fires += 1
        chosen = _choose(brackets.get(label.valid_on, ()), later_max, tape)
        if chosen is None:
            continue
        won = _contains(chosen, label.high_f)
        if won:
            hits += 1
        priced = [
            item.yes_price
            for item in by_ticker.get(chosen.ticker, ())
            if item.created_at <= decision
            and item.created_at < label.available_at
            and item.count > 0
            and Decimal(0) < item.yes_price <= PRICE_THRESHOLD
        ]
        if not priced:
            continue
        price = min(priced)
        pnl.append(_ONE - price if won else -price)
    flat = parse_money(Decimal(100))
    return RevisionFold(
        days=len(labels),
        fires=fires,
        claim_hits=hits,
        optimistic_fills=len(pnl),
        optimistic_equity=parse_money(sum(pnl, Decimal(100))),
        base_fills=0,
        base_equity=flat,
        conservative_fills=0,
        conservative_equity=flat,
        guaranteed_fill=False,
        promoted=False,
    )


def _choose(
    brackets: tuple[StoredBracket, ...],
    later_max: Decimal,
    tape: frozenset[str],
) -> StoredBracket | None:
    contained = tuple(item for item in brackets if _contains(item, later_max))
    if len(contained) != 1:
        return None
    chosen = contained[0]
    if chosen.ticker not in tape:
        return None
    return chosen


def _contains(bracket: StoredBracket, value: Decimal) -> bool:
    strike = Strike(strike_type=StrikeType.BETWEEN, floor=bracket.floor, cap=bracket.cap)
    return strike.resolves_yes(value)


def _brackets(folder: Path) -> dict[date, tuple[StoredBracket, ...]]:
    found: dict[str, StoredBracket] = {}
    for path in sorted(folder.glob("markets-*.json")):
        body = _read_object(path)
        markets = body.get("markets")
        if not isinstance(markets, list):
            raise ValueError(f"{path.name} has no market list")
        for raw in markets:
            if not isinstance(raw, dict):
                raise ValueError(f"{path.name} has a market that is not an object")
            ticker = raw.get("ticker")
            if not isinstance(ticker, str) or not ticker.startswith("KXHIGHPHIL-"):
                continue
            if raw.get("strike_type") != StrikeType.BETWEEN:
                continue
            valid_on = ticker_target_date(ticker)
            if valid_on is None:
                continue
            bracket = StoredBracket(
                ticker=ticker,
                valid_on=valid_on,
                floor=_number(raw.get("floor_strike"), ticker),
                cap=_number(raw.get("cap_strike"), ticker),
            )
            prior = found.get(ticker)
            if prior is not None and (prior.floor != bracket.floor or prior.cap != bracket.cap):
                raise ValueError(f"{ticker} has two stored brackets")
            found[ticker] = bracket
    grouped: dict[date, list[StoredBracket]] = {}
    for bracket in found.values():
        grouped.setdefault(bracket.valid_on, []).append(bracket)
    return {day: tuple(items) for day, items in grouped.items()}


def _score_registered(
    folder: Path,
    place: str,
    labels: tuple[CliLabel, ...],
    prints: tuple[TradePrint, ...],
) -> BracketRevision:
    _frozen()
    _require_call(folder / "revision-vintages.manifest.json")
    return _score_city(
        folder / "revision-vintages.json",
        place,
        labels,
        _registered_brackets(folder / "markets.json"),
        frozenset(item.ticker for item in prints),
        prints,
    )


def _registered_brackets(path: Path) -> dict[date, tuple[StoredBracket, ...]]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} is not a list")
    found: dict[str, StoredBracket] = {}
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError(f"{path.name} has a market that is not an object")
        ticker = raw.get("ticker")
        if not isinstance(ticker, str) or not ticker.endswith("-B80.5"):
            raise ValueError("a stored market is not the registered bracket")
        status = raw.get("http_status")
        if status == 404:
            continue
        if status != 200:
            raise ValueError(f"{ticker} has an unexpected status")
        valid_on = ticker_target_date(ticker)
        if valid_on is None:
            raise ValueError(f"{ticker} has no valid day")
        bracket = StoredBracket(
            ticker=ticker,
            valid_on=valid_on,
            floor=BRACKET_FLOOR,
            cap=BRACKET_CAP,
        )
        prior = found.get(ticker)
        if prior is not None and (prior.floor != bracket.floor or prior.cap != bracket.cap):
            raise ValueError(f"{ticker} has two stored brackets")
        found[ticker] = bracket
    grouped: dict[date, list[StoredBracket]] = {}
    for bracket in found.values():
        grouped.setdefault(bracket.valid_on, []).append(bracket)
    return {day: tuple(items) for day, items in grouped.items()}


def _tape(path: Path) -> frozenset[str]:
    body = _read_object(path)
    calls = body.get("calls")
    if not isinstance(calls, list):
        raise ValueError("the trade manifest has no calls")
    tickers: set[str] = set()
    for raw in calls:
        if not isinstance(raw, dict):
            continue
        ticker = raw.get("ticker")
        if isinstance(ticker, str) and ticker != "":
            tickers.add(ticker)
    if not tickers:
        raise ValueError("the stored tape has no tickers")
    return frozenset(tickers)


def _prints_by_ticker(
    prints: tuple[TradePrint, ...],
) -> dict[str, tuple[TradePrint, ...]]:
    grouped: dict[str, list[TradePrint]] = {}
    for item in prints:
        grouped.setdefault(item.ticker, []).append(item)
    return {ticker: tuple(items) for ticker, items in grouped.items()}


def _sentence(score: BracketRevision) -> str:
    if score.promoted or score.holdout_scored or score.name != RULE_NAME:
        raise ValueError("the bracket note must not invent a score")
    train = score.train
    validation = score.validation
    return " ".join(
        (
            f"{score.place} `{score.name}`.",
            f"Train fires: {train.fires}. Train fills: {train.optimistic_fills}.",
            f"Train optimistic equity: {format(train.optimistic_equity, 'f')}.",
            f"Validation fires: {validation.fires}.",
            f"Validation fills: {validation.optimistic_fills}.",
            f"Validation optimistic equity: {format(validation.optimistic_equity, 'f')}.",
            "Base and conservative equity: 100.000000.",
            "Nothing was promoted.",
        )
    )


def _require_flat(fold: RevisionFold, place: str) -> None:
    flat = Decimal("100.000000")
    if fold.guaranteed_fill or fold.promoted:
        raise ValueError(f"{place} treats a print as a fill")
    if fold.base_fills != 0 or fold.conservative_fills != 0:
        raise ValueError(f"{place} base or conservative took a fill")
    if fold.base_equity != flat or fold.conservative_equity != flat:
        raise ValueError(f"{place} base or conservative equity moved")


def _frozen() -> None:
    if Decimal(80) != BRACKET_FLOOR or Decimal(81) != BRACKET_CAP:
        raise ValueError("the registered bracket was changed")
    if Decimal("0.4000") != PRICE_THRESHOLD:
        raise ValueError("the price threshold was changed")
    if Decimal(2) != REVISION_MINIMUM_F:
        raise ValueError("the revision minimum was changed")
    if DECISION_HOUR_UTC != 15:
        raise ValueError("the decision hour was changed")


def _read_object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    return {str(key): value for key, value in payload.items()}


def _number(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
        raise ValueError(f"{label} has no strike")
    return Decimal(value)
