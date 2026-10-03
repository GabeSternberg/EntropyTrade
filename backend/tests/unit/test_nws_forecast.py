"""The stored NWS points and forecast bodies. No socket and no trade."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast import load_nws_forecast, nws_forecast_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_forecast.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_nws_forecast_is_stored_and_not_traded() -> None:
    found = load_nws_forecast(PUBLIC)
    assert found.points_status == 200
    assert found.forecast_status == 200
    assert found.forecast_url == "https://api.weather.gov/gridpoints/PHI/48,75/forecast"
    assert found.grid_id == "PHI"
    assert found.grid_x == 48
    assert found.grid_y == 75
    assert found.periods == 14
    assert found.first_start == "2026-10-02T19:00:00-04:00"
    assert found.first_temperature == Decimal(61)
    assert found.temperature_unit == "F"
    assert found.last_start == "2026-10-09T06:00:00-04:00"
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "It was not aligned to the CLI decision clock." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
