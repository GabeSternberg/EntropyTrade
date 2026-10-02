"""Mexico City has no named station, so the frozen rules are not scored."""

from pathlib import Path

from entropytrade.weather.mexicocity_listing import load_mexico_city_listing

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "mexicocity_listing.py"
)


def test_mexico_city_is_not_scored() -> None:
    listed = load_mexico_city_listing(ROOT)
    assert listed.series == "KXHIGHTMMMX"
    assert listed.title == "Daily high temp Mexico City"
    assert listed.markets_listed == 0
    assert listed.events_listed == 0
    assert listed.sample_ticker == "KXHIGHTMMMX-26AUG23-B80.5"
    assert listed.sample_http_status == 404
    assert listed.sample_error_code == "not_found"
    assert listed.station_named is False
    assert listed.scored is False
    assert listed.promoted is False
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
