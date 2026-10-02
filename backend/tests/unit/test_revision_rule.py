"""The revision uses two stored fields. A print is not a fill."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from entropytrade.exchange.trade_prints import TradePrint
from entropytrade.weather.cli_observations import CliLabel
from entropytrade.weather.informational_rules import BRACKET_CAP, BRACKET_FLOOR, PRICE_THRESHOLD
from entropytrade.weather.revision_rule import (
    DECISION_HOUR_UTC,
    REVISION_MINIMUM_F,
    _fold,
    load_philadelphia_revision,
    revision_lines,
)

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "revision_rule.py"
)
_CALL = ROOT / "open-meteo" / "revision-vintages.manifest.json"


def test_philadelphia_revision_does_not_fill() -> None:
    score = load_philadelphia_revision(ROOT)
    assert score.name == "forecast_revision_up"
    assert score.place == "Philadelphia"
    assert score.hypotheses == 1
    assert score.scored is True
    assert score.promoted is False
    assert score.clock == "rule"
    assert score.fidelity == "trade-print"
    assert score.guaranteed_fill is False
    assert score.holdout_scored is False
    assert score.train_days == 20
    assert score.validation_days == 10
    assert score.holdout_days == 10
    for fold in (score.train, score.validation):
        assert fold.fires == 0
        assert fold.claim_hits == 0
        assert fold.optimistic_fills == 0
        assert fold.optimistic_equity == Decimal("100.000000")
        assert fold.base_fills == 0
        assert fold.conservative_fills == 0
        assert fold.base_equity == Decimal("100.000000")
        assert fold.conservative_equity == Decimal("100.000000")
        assert fold.guaranteed_fill is False
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("0.4000") == PRICE_THRESHOLD
    assert Decimal(2) == REVISION_MINIMUM_F
    assert DECISION_HOUR_UTC == 15
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "run=" not in _CALL.read_text(encoding="utf-8")
    note = "\n".join(revision_lines(ROOT))
    assert "Nothing was promoted." in note
    assert "Philadelphia `forecast_revision_up`." in note
    assert "Validation optimistic equity: 100.000000." in note


def test_revision_fires_only_on_the_frozen_pair() -> None:
    day = date(2026, 8, 23)
    label = CliLabel(
        available_at=datetime(2026, 8, 24, 5, 55, tzinfo=UTC),
        source="iem-nws-cli",
        endpoint="cliphl-afos.txt",
        valid_on=day,
        high_f=Decimal("80.5"),
        header="240555",
    )
    printed = TradePrint(
        trade_id="t",
        ticker="KXHIGHPHIL-26AUG23-B80.5",
        created_at=datetime(2026, 8, 23, 14, tzinfo=UTC),
        fetched_at=datetime(2026, 8, 24, tzinfo=UTC),
        endpoint="https://api.elections.kalshi.com/trade-api/v2/markets/trades",
        yes_price=Decimal("0.2000"),
        count=Decimal(1),
    )
    fired = _fold((label,), (printed,), {day: Decimal("80.5")}, {day: Decimal("78.0")})
    assert fired.fires == 1
    assert fired.claim_hits == 1
    assert fired.optimistic_fills == 1
    assert fired.optimistic_equity == Decimal("100.800000")
    assert fired.base_fills == 0
    assert fired.base_equity == Decimal("100.000000")
    quiet = _fold((label,), (printed,), {day: Decimal("80.5")}, {day: Decimal("78.6")})
    assert quiet.fires == 0
    assert quiet.optimistic_fills == 0
    outside = _fold((label,), (printed,), {day: Decimal(82)}, {day: Decimal(79)})
    assert outside.fires == 0
    missing = _fold((label,), (printed,), {day: Decimal("80.5")}, {})
    assert missing.fires == 0
    assert missing.optimistic_equity == Decimal("100.000000")
