"""A downward revision uses the same 2 F and 0.40. The sign is not fit."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.trade_prints import TradePrint
from entropytrade.weather.cli_observations import CliLabel
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_bracket import (
    DOWN_NAME,
    StoredBracket,
    _fold,
    load_chicago_down,
    load_newyork_down,
    load_philadelphia_bracket,
    load_philadelphia_down,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_DAY = date(2026, 8, 23)


def test_philadelphia_down_keeps_the_frozen_thresholds() -> None:
    score = load_philadelphia_down(ROOT)
    upward = load_philadelphia_bracket(ROOT)
    assert score.name == DOWN_NAME
    assert score.place == "Philadelphia"
    assert score.hypotheses == 1
    assert score.scored is True
    assert score.promoted is False
    assert score.holdout_scored is False
    assert score.guaranteed_fill is False
    assert score.train_days == 20
    assert score.validation_days == 10
    assert score.holdout_days == 10
    assert score.train.fires == 13
    assert score.train.claim_hits == 0
    assert score.train.optimistic_fills == 3
    assert score.train.optimistic_equity == Decimal("99.760000")
    assert score.validation.fires == 5
    assert score.validation.claim_hits == 0
    assert score.validation.optimistic_fills == 1
    assert score.validation.optimistic_equity == Decimal("99.860000")
    for fold in (score.train, score.validation):
        assert fold.base_fills == 0
        assert fold.conservative_fills == 0
        assert fold.base_equity == Decimal("100.000000")
        assert fold.conservative_equity == Decimal("100.000000")
    assert upward.train.fires == 1
    assert upward.train.optimistic_equity == Decimal("99.770000")
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
    text = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "entropytrade"
        / "weather"
        / "revision_bracket.py"
    ).read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text


def test_chicago_down_keeps_the_frozen_thresholds() -> None:
    score = load_chicago_down(ROOT)
    assert score.name == DOWN_NAME
    assert score.place == "Chicago"
    assert score.hypotheses == 1
    assert score.promoted is False
    assert score.holdout_scored is False
    assert score.guaranteed_fill is False
    assert score.train_days == 20
    assert score.validation_days == 10
    assert score.holdout_days == 10
    assert score.train.fires == 3
    assert score.train.claim_hits == 1
    assert score.train.optimistic_fills == 1
    assert score.train.optimistic_equity == Decimal("100.750000")
    assert score.validation.fires == 4
    assert score.validation.claim_hits == 0
    assert score.validation.optimistic_fills == 0
    assert score.validation.optimistic_equity == Decimal("100.000000")
    for fold in (score.train, score.validation):
        assert fold.base_fills == 0
        assert fold.conservative_fills == 0
        assert fold.base_equity == Decimal("100.000000")
        assert fold.conservative_equity == Decimal("100.000000")
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_newyork_down_keeps_the_frozen_thresholds() -> None:
    score = load_newyork_down(ROOT)
    assert score.name == DOWN_NAME
    assert score.place == "New York"
    assert score.promoted is False
    assert score.holdout_scored is False
    assert score.train_days == 20
    assert score.validation_days == 10
    assert score.holdout_days == 10
    assert score.train.fires == 17
    assert score.train.claim_hits == 0
    assert score.train.optimistic_fills == 0
    assert score.train.optimistic_equity == Decimal("100.000000")
    assert score.validation.fires == 5
    assert score.validation.claim_hits == 0
    assert score.validation.optimistic_fills == 0
    assert score.validation.optimistic_equity == Decimal("100.000000")
    for fold in (score.train, score.validation):
        assert fold.base_fills == 0
        assert fold.conservative_fills == 0
        assert fold.base_equity == Decimal("100.000000")
        assert fold.conservative_equity == Decimal("100.000000")
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_down_fires_only_at_the_frozen_magnitude() -> None:
    label = CliLabel(
        available_at=datetime(2026, 8, 24, 5, 55, tzinfo=UTC),
        source="iem-nws-cli",
        endpoint="cliphl-afos.txt",
        valid_on=_DAY,
        high_f=Decimal(83),
        header="240555",
    )
    bracket = StoredBracket("KXHIGHPHIL-26AUG23-B82.5", _DAY, Decimal(82), Decimal(83))
    printed = TradePrint(
        trade_id="t",
        ticker=bracket.ticker,
        created_at=datetime(2026, 8, 23, 14, tzinfo=UTC),
        fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
        endpoint="https://api.elections.kalshi.com/trade-api/v2/markets/trades",
        yes_price=Decimal("0.2000"),
        count=Decimal(1),
    )
    tape = frozenset({bracket.ticker})
    books = {_DAY: (bracket,)}
    prints = {bracket.ticker: (printed,)}
    fired = _fold(
        (label,),
        books,
        tape,
        prints,
        {_DAY: Decimal("80.0")},
        {_DAY: Decimal("82.0")},
        "down",
    )
    assert fired.fires == 1
    quiet = _fold(
        (label,),
        books,
        tape,
        prints,
        {_DAY: Decimal("80.5")},
        {_DAY: Decimal("82.0")},
        "down",
    )
    assert quiet.fires == 0
    upward = _fold(
        (label,),
        books,
        tape,
        prints,
        {_DAY: Decimal("84.0")},
        {_DAY: Decimal("80.0")},
        "down",
    )
    assert upward.fires == 0
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
