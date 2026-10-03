"""The containing between-contract is traded. 2 F and 0.40 stay put."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.trade_prints import TradePrint
from entropytrade.weather.cli_observations import CliLabel
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_bracket import (
    RULE_NAME,
    StoredBracket,
    _fold,
    bracket_note,
    load_chicago_bracket,
    load_philadelphia_bracket,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "revision_bracket.py"
)
_DAY = date(2026, 8, 23)


def test_philadelphia_bracket_equity_stays_unfitted() -> None:
    score = load_philadelphia_bracket(ROOT)
    assert score.name == RULE_NAME
    assert score.hypotheses == 1
    assert score.scored is True
    assert score.promoted is False
    assert score.holdout_scored is False
    assert score.guaranteed_fill is False
    assert score.train_days == 20
    assert score.validation_days == 10
    assert score.holdout_days == 10
    assert score.train.fires == 1
    assert score.train.claim_hits == 0
    assert score.train.optimistic_fills == 1
    assert score.train.optimistic_equity == Decimal("99.770000")
    assert score.validation.fires == 0
    assert score.validation.optimistic_fills == 0
    assert score.validation.optimistic_equity == Decimal("100.000000")
    for fold in (score.train, score.validation):
        assert fold.base_fills == 0
        assert fold.conservative_fills == 0
        assert fold.base_equity == Decimal("100.000000")
        assert fold.conservative_equity == Decimal("100.000000")
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    note = "\n".join(bracket_note(ROOT))
    assert "Philadelphia `forecast_revision_bracket`." in note
    assert "Train optimistic equity: 99.770000." in note
    assert "Nothing was promoted." in note
    assert "Chicago `forecast_revision_bracket`." in note


def test_chicago_bracket_keeps_the_same_thresholds() -> None:
    score = load_chicago_bracket(ROOT)
    assert score.place == "Chicago"
    assert score.hypotheses == 1
    assert score.scored is True
    assert score.promoted is False
    assert score.holdout_scored is False
    assert score.guaranteed_fill is False
    assert score.train_days == 20
    assert score.validation_days == 10
    assert score.holdout_days == 10
    assert score.train.fires == 7
    assert score.train.claim_hits == 0
    assert score.train.optimistic_fills == 0
    assert score.train.optimistic_equity == Decimal("100.000000")
    assert score.validation.fires == 3
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


def test_a_missing_or_shared_bracket_is_not_traded() -> None:
    label = CliLabel(
        available_at=datetime(2026, 8, 24, 5, 55, tzinfo=UTC),
        source="iem-nws-cli",
        endpoint="cliphl-afos.txt",
        valid_on=_DAY,
        high_f=Decimal(83),
        header="240555",
    )
    printed = TradePrint(
        trade_id="t",
        ticker="KXHIGHPHIL-26AUG23-B82.5",
        created_at=datetime(2026, 8, 23, 14, tzinfo=UTC),
        fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
        endpoint="https://api.elections.kalshi.com/trade-api/v2/markets/trades",
        yes_price=Decimal("0.2000"),
        count=Decimal(1),
    )
    low = StoredBracket("KXHIGHPHIL-26AUG23-B80.5", _DAY, Decimal(80), Decimal(81))
    high = StoredBracket("KXHIGHPHIL-26AUG23-B82.5", _DAY, Decimal(82), Decimal(83))
    tape = frozenset({high.ticker})
    later = {_DAY: Decimal("82.6")}
    earlier = {_DAY: Decimal("80.0")}
    traded = _fold((label,), {_DAY: (low, high)}, tape, {high.ticker: (printed,)}, later, earlier)
    assert traded.fires == 1
    assert traded.claim_hits == 1
    assert traded.optimistic_fills == 1
    assert traded.optimistic_equity == Decimal("100.800000")
    assert traded.base_equity == Decimal("100.000000")
    wide = StoredBracket("KXHIGHPHIL-26AUG23-B81.5", _DAY, Decimal(81), Decimal(84))
    shared = _fold(
        (label,),
        {_DAY: (low, high, wide)},
        tape,
        {high.ticker: (printed,)},
        {_DAY: Decimal(82)},
        earlier,
    )
    assert shared.fires == 1
    assert shared.optimistic_fills == 0
    assert shared.optimistic_equity == Decimal("100.000000")
    absent = _fold(
        (label,),
        {_DAY: (low, high)},
        frozenset(),
        {high.ticker: (printed,)},
        later,
        earlier,
    )
    assert absent.fires == 1
    assert absent.optimistic_fills == 0
    quiet = _fold(
        (label,),
        {_DAY: (low, high)},
        tape,
        {high.ticker: (printed,)},
        {_DAY: Decimal("82.6")},
        {_DAY: Decimal("81.0")},
    )
    assert quiet.fires == 0
    assert quiet.optimistic_fills == 0
