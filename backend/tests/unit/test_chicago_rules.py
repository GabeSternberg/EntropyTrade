"""Chicago uses the registered thresholds. A print is not a guaranteed fill."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.chicago_rules import load_chicago_score
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    MIDPOINT,
    PRICE_THRESHOLD,
    load_rule_scores,
)
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "chicago_rules.py"
)


def test_the_thresholds_are_the_philadelphia_ones() -> None:
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("80.5") == MIDPOINT
    assert Decimal("0.4000") == PRICE_THRESHOLD
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text


def test_chicago_rules_are_tried_and_not_promoted() -> None:
    scored = load_chicago_score(ROOT)
    assert scored.series == "KXHIGHCHI"
    assert scored.station == "CLIMDW"
    assert scored.label_days == 40
    assert scored.forecast_days == 40
    assert scored.print_count == 14675
    assert scored.markets_found == 11
    assert scored.markets_missing == 29
    assert scored.hypotheses == 4
    assert scored.fidelity == "trade-print"
    assert scored.promoted is False
    by_name = {rule.name: rule for rule in scored.rules}
    inside = by_name["forecast_inside"]
    above = by_name["forecast_above"]
    below = by_name["forecast_below"]
    gap = by_name["forecast_gap"]
    assert inside.fires == 2
    assert inside.claim_hits == 1
    assert inside.scenarios[0].assumed_fills == 1
    assert inside.scenarios[0].equity == Decimal("100.750000")
    assert above.fires == 17
    assert above.claim_hits == 12
    assert above.scenarios[0].assumed_fills == 2
    assert above.scenarios[0].equity == Decimal("99.400000")
    assert below.fires == 21
    assert below.claim_hits == 18
    assert below.scenarios[0].assumed_fills == 1
    assert below.scenarios[0].equity == Decimal("99.660000")
    assert gap.fires == 19
    assert gap.claim_hits == 5
    assert gap.scenarios[0].assumed_fills == 7
    assert gap.scenarios[0].equity == Decimal("102.430000")
    for rule in scored.rules:
        assert rule.tried is True
        assert rule.promoted is False
        assert rule.scenarios[0].guaranteed_fill is False
        assert rule.scenarios[1].assumed_fills == 0
        assert rule.scenarios[1].equity == Decimal("100.000000")
        assert rule.scenarios[2].assumed_fills == 0
        assert rule.scenarios[2].equity == Decimal("100.000000")
    philadelphias = {rule.name: rule for rule in load_rule_scores(ROOT)}
    assert philadelphias["forecast_gap"].scenarios[0].assumed_fills == 3
    assert philadelphias["forecast_gap"].scenarios[0].equity == Decimal("99.900000")
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
