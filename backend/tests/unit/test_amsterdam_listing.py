"""Amsterdam's Celsius markets are not scored as the Fahrenheit bracket."""

from pathlib import Path

from entropytrade.weather.amsterdam_listing import load_amsterdam_listing

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "amsterdam_listing.py"
)


def test_amsterdam_celsius_markets_are_not_scored() -> None:
    listed = load_amsterdam_listing(ROOT)
    assert listed.series == "KXHIGHTEHAM"
    assert listed.markets_found == 0
    assert listed.markets_missing == 40
    assert listed.celsius_markets_listed == 6
    assert listed.bracket_applied is False
    assert listed.scored is False
    assert listed.promoted is False
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "score_rules" not in text
