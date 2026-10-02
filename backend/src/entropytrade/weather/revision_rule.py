"""Forecast revision from two stored previous-runs fields. No socket.

``run`` is rejected, so the 03:00 and 15:00 vintages are not available. The
later field is ``temperature_2m_previous_day1`` and the earlier field is
``temperature_2m_previous_day2``. If the payload has no issue time,
``available_at`` is 00:00 UTC on the valid day for the later field and 00:00
UTC the day before for the earlier field. That clock is a rule. A print is
not a guaranteed fill. Nothing here is promoted.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike
from entropytrade.domain.numeric import parse_money
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.exchange.trade_prints import TradePrint, load_trade_tape
from entropytrade.weather.chicago_rules import _labels, _prints
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    PRICE_THRESHOLD,
)
from entropytrade.weather.walk_forward import _thirds, reject_holdout

RULE_NAME = "forecast_revision_up"
FIDELITY = "trade-print"
DECISION_HOUR_UTC = 15
REVISION_MINIMUM_F = Decimal(2)
LATER_FIELD = "temperature_2m_previous_day1"
EARLIER_FIELD = "temperature_2m_previous_day2"
_ONE = Decimal(1)
_STRIKE = Strike(strike_type=StrikeType.BETWEEN, floor=BRACKET_FLOOR, cap=BRACKET_CAP)
_ISSUE_KEYS = frozenset(
    {"issue_time", "available_at", "run_time", "initialization_time", "model_run"}
)
_PHILADELPHIA = Path("open-meteo/revision-vintages.json")
_PHILADELPHIA_CALL = Path("open-meteo/revision-vintages.manifest.json")
_CHICAGO = Path("chicago/revision-vintages.json")
_CHICAGO_CALL = Path("chicago/revision-vintages.manifest.json")


@dataclass(frozen=True)
class RevisionFold:
    """One walk-forward fold. Base and conservative do not fill."""

    days: int
    fires: int
    claim_hits: int
    optimistic_fills: int
    optimistic_equity: Decimal
    base_fills: int
    base_equity: Decimal
    conservative_fills: int
    conservative_equity: Decimal
    guaranteed_fill: bool
    promoted: bool


@dataclass(frozen=True)
class RevisionScore:
    """One city. ``promoted`` stays false. The holdout is not scored."""

    name: str
    place: str
    hypotheses: int
    scored: bool
    promoted: bool
    clock: str
    fidelity: str
    guaranteed_fill: bool
    holdout_scored: bool
    train_days: int
    validation_days: int
    holdout_days: int
    train: RevisionFold
    validation: RevisionFold


def load_philadelphia_revision(root: Path) -> RevisionScore:
    """Score the stored Philadelphia fields. Thresholds are not fit to equity."""
    _frozen()
    _require_call(root / _PHILADELPHIA_CALL)
    labels, _comparison = load_comparison(root)
    prints = load_trade_tape(root).b805_prints
    return _score_city(root / _PHILADELPHIA, "Philadelphia", labels, prints)


def load_chicago_revision(root: Path) -> RevisionScore:
    """Score the stored Chicago fields with the same thresholds."""
    _frozen()
    _require_call(root / _CHICAGO_CALL)
    folder = root / "chicago"
    manifest = _object(folder / "manifest.json")
    ingested = datetime.fromisoformat(_text(manifest.get("finished_at"), "finished_at"))
    labels = _labels(folder / "climdw-afos.txt", ingested)
    prints = tuple(item for item in _prints(folder) if item.ticker.endswith("-B80.5"))
    return _score_city(root / _CHICAGO, "Chicago", labels, prints)


def revision_lines(root: Path) -> tuple[str, ...]:
    """The scan note's revision section. It does not invent a vintage."""
    philadelphia = load_philadelphia_revision(root)
    lines = [
        "## Revision",
        "",
        "The 03:00 and 15:00 vintages are not available, because `run` is",
        "rejected. The later field is `temperature_2m_previous_day1` and the",
        "earlier field is `temperature_2m_previous_day2`. `available_at` is a",
        "rule: 00:00 UTC on the valid day for the later field, and 00:00 UTC",
        "the day before for the earlier field. A print is not a fill. Nothing",
        "was promoted.",
        "",
        _place_lines(philadelphia),
    ]
    if (root / _CHICAGO).exists():
        lines.extend(("", _place_lines(load_chicago_revision(root))))
    return tuple(lines)


def _score_city(
    path: Path,
    place: str,
    labels: tuple[CliLabel, ...],
    prints: tuple[TradePrint, ...],
) -> RevisionScore:
    later, earlier, clock = _maxes(_object(path))
    if clock != "rule":
        raise ValueError("an issue time was present and was not the stored rule")
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    train, validation, holdout = _thirds(ordered)
    reject_holdout(
        {label.valid_on for label in train} | {label.valid_on for label in validation},
        {label.valid_on for label in holdout},
    )
    train_fold = _fold(train, prints, later, earlier)
    validation_fold = _fold(validation, prints, later, earlier)
    _require_flat(train_fold, place)
    _require_flat(validation_fold, place)
    return RevisionScore(
        name=RULE_NAME,
        place=place,
        hypotheses=1,
        scored=True,
        promoted=False,
        clock=clock,
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
    prints: tuple[TradePrint, ...],
    later: dict[date, Decimal],
    earlier: dict[date, Decimal],
) -> RevisionFold:
    by_day = _prints_by_day(prints)
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
        if not _STRIKE.resolves_yes(later_max):
            continue
        fires += 1
        won = _STRIKE.resolves_yes(label.high_f)
        if won:
            hits += 1
        day_prints = tuple(
            item
            for item in by_day.get(label.valid_on, ())
            if item.created_at <= decision
            and item.created_at < label.available_at
            and item.count > 0
        )
        priced = [
            item.yes_price for item in day_prints if Decimal(0) < item.yes_price <= PRICE_THRESHOLD
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


def _maxes(body: dict[str, object]) -> tuple[dict[date, Decimal], dict[date, Decimal], str]:
    if _issue_time(body):
        raise ValueError("the payload has an issue time this rule does not read")
    hourly = body.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("revision forecast has no hourly object")
    return _daily(hourly, LATER_FIELD), _daily(hourly, EARLIER_FIELD), "rule"


def _daily(hourly: dict[str, object], field: str) -> dict[date, Decimal]:
    times = hourly.get("time")
    values = hourly.get(field)
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
        raise ValueError(f"{field} is missing")
    grouped: dict[date, list[Decimal]] = {}
    broken: set[date] = set()
    for stamp, raw in zip(times, values, strict=True):
        hour = datetime.fromisoformat(_text(stamp, "hour")).replace(tzinfo=UTC)
        if raw is None:
            broken.add(hour.date())
            continue
        if isinstance(raw, bool) or not isinstance(raw, Decimal | int):
            raise ValueError(f"{field} has a non-numeric hour")
        grouped.setdefault(hour.date(), []).append(Decimal(raw))
    return {
        day: max(samples)
        for day, samples in grouped.items()
        if day not in broken and len(samples) == 24
    }


def _clock(valid_on: date) -> tuple[datetime, datetime]:
    later = datetime(valid_on.year, valid_on.month, valid_on.day, tzinfo=UTC)
    return later, later - timedelta(days=1)


def _decision(valid_on: date) -> datetime:
    return datetime(valid_on.year, valid_on.month, valid_on.day, DECISION_HOUR_UTC, tzinfo=UTC)


def _prints_by_day(prints: tuple[TradePrint, ...]) -> dict[date, tuple[TradePrint, ...]]:
    grouped: dict[date, list[TradePrint]] = {}
    for item in prints:
        valid_on = ticker_target_date(item.ticker)
        if valid_on is None:
            continue
        grouped.setdefault(valid_on, []).append(item)
    return {day: tuple(items) for day, items in grouped.items()}


def _issue_time(body: dict[str, object]) -> bool:
    keys = set(body)
    hourly = body.get("hourly")
    if isinstance(hourly, dict):
        keys.update(hourly)
    return bool(keys & _ISSUE_KEYS)


def _require_call(path: Path) -> None:
    call = _object(path)
    url = _text(call.get("url"), "url")
    if "run=" in url or not url.startswith("https://previous-runs-api.open-meteo.com/"):
        raise ValueError("the revision call used a rejected parameter")
    if call.get("http_status") != 200 or call.get("clock") != "rule":
        raise ValueError("the revision call is not the stored rule clock")
    if call.get("later") != LATER_FIELD or call.get("earlier") != EARLIER_FIELD:
        raise ValueError("the revision fields were changed")
    if call.get("promoted") is not False:
        raise ValueError("the revision was promoted")


def _require_flat(fold: RevisionFold, place: str) -> None:
    if fold.guaranteed_fill or fold.promoted:
        raise ValueError(f"{place} treats a print as a fill")
    if fold.base_fills != 0 or fold.conservative_fills != 0:
        raise ValueError(f"{place} base or conservative took a fill")
    flat = Decimal("100.000000")
    if fold.base_equity != flat or fold.conservative_equity != flat:
        raise ValueError(f"{place} base or conservative equity moved")


def _place_lines(score: RevisionScore) -> str:
    if score.promoted or score.holdout_scored or score.clock != "rule":
        raise ValueError("the revision section must not invent a score")
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


def _frozen() -> None:
    if Decimal(80) != BRACKET_FLOOR or Decimal(81) != BRACKET_CAP:
        raise ValueError("the bracket was changed")
    if Decimal("0.4000") != PRICE_THRESHOLD:
        raise ValueError("the price threshold was changed")
    if Decimal(2) != REVISION_MINIMUM_F:
        raise ValueError("the revision minimum was changed")
    if DECISION_HOUR_UTC != 15:
        raise ValueError("the decision hour was changed")


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    mapped: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"{path.name} has a non-string key")
        mapped[key] = item
    return mapped


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is missing")
    return value
