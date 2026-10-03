"""NWS forecast daytime counts. No socket and no trading session."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_daytime import (
    load_nws_forecast_daytime,
    nws_forecast_daytime_note,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "entropytrade"
    / "weather"
    / "nws_forecast_daytime.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "isDaytime" in text


def test_forecast_daytime_is_not_a_trading_session() -> None:
    found = load_nws_forecast_daytime(PUBLIC)
    assert found.periods == 14
    assert found.daytime == 7
    assert found.nighttime == 7
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_daytime_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "7 daytime periods and 7 nighttime periods." in note
    assert "The hourly body was not used." in note
    assert "Daytime was not treated as a trading session." in note
    assert "The counts were not compared to 0.40." in note
    assert "They are not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
