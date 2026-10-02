"""Houston has no named station, so the frozen rules are not scored."""

from pathlib import Path

from entropytrade.weather.houston_listing import load_houston_listing

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "houston_listing.py"
)


def test_houston_is_not_scored() -> None:
    listed = load_houston_listing(ROOT)
    assert listed.series == "KXHIGHHOU"
    assert listed.title == "Highest temperature in Houston"
    assert listed.markets_listed == 0
    assert listed.sample_ticker == "KXHIGHHOU-26AUG23-B80.5"
    assert listed.sample_http_status == 404
    assert listed.sample_error_code == "not_found"
    assert listed.station_named is False
    assert listed.scored is False
    assert listed.promoted is False
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
