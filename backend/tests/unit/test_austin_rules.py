"""Austin uses the registered thresholds. A missing strike stays missing."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.austin_rules import load_austin_score
from entropytrade.weather.chicago_rules import load_chicago_score
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    MIDPOINT,
    PRICE_THRESHOLD,
    load_rule_scores,
)
from entropytrade.weather.newyork_rules import load_newyork_score
from entropytrade.weather.settlement_score import load_aligned_score

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "austin_rules.py"
)


def test_austin_thresholds_stay_frozen() -> None:
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("80.5") == MIDPOINT
    assert Decimal("0.4000") == PRICE_THRESHOLD
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text


def test_austin_rules_are_tried_and_not_promoted() -> None:
    scored = load_austin_score(ROOT)
    assert scored.series == "KXHIGHAUS"
    assert scored.station == "CLIAUS"
    assert scored.label_days == 40
    assert scored.forecast_days == 40
    assert scored.print_count == 0
    assert scored.markets_found == 0
    assert scored.markets_missing == 40
    assert scored.hypotheses == 4
    assert scored.fidelity == "trade-print"
    assert scored.promoted is False
    by_name = {rule.name: rule for rule in scored.rules}
    inside = by_name["forecast_inside"]
    above = by_name["forecast_above"]
    below = by_name["forecast_below"]
    gap = by_name["forecast_gap"]
    assert inside.fires == 0
    assert inside.claim_hits == 0
    assert inside.scenarios[0].assumed_fills == 0
    assert inside.scenarios[0].equity == Decimal("100.000000")
    assert above.fires == 40
    assert above.claim_hits == 40
    assert above.scenarios[0].assumed_fills == 0
    assert above.scenarios[0].equity == Decimal("100.000000")
    assert below.fires == 0
    assert below.claim_hits == 0
    assert below.scenarios[0].assumed_fills == 0
    assert below.scenarios[0].equity == Decimal("100.000000")
    assert gap.fires == 40
    assert gap.claim_hits == 0
    assert gap.scenarios[0].assumed_fills == 0
    assert gap.scenarios[0].equity == Decimal("100.000000")
    for rule in scored.rules:
        assert rule.tried is True
        assert rule.promoted is False
        assert rule.scenarios[0].guaranteed_fill is False
        assert rule.scenarios[1].assumed_fills == 0
        assert rule.scenarios[1].equity == Decimal("100.000000")
        assert rule.scenarios[2].assumed_fills == 0
        assert rule.scenarios[2].equity == Decimal("100.000000")
    philadelphias = {rule.name: rule for rule in load_rule_scores(ROOT)}
    assert philadelphias["forecast_gap"].scenarios[0].equity == Decimal("99.900000")
    chicago = {rule.name: rule for rule in load_chicago_score(ROOT).rules}
    assert chicago["forecast_gap"].scenarios[0].equity == Decimal("102.430000")
    newyork = {rule.name: rule for rule in load_newyork_score(ROOT).rules}
    assert newyork["forecast_gap"].scenarios[0].equity == Decimal("100.450000")
    replay = load_aligned_score(ROOT)
    assert replay.replay_equity == Decimal("100.000000")
