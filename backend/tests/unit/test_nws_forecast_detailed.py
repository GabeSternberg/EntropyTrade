"""Distinct NWS forecast detailed texts. No socket and no rewritten words."""

import hashlib
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_detailed import (
    load_nws_forecast_detailed,
    nws_forecast_detailed_note,
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
    / "nws_forecast_detailed.py"
)
_DIGEST = "f38c156228247f1ca89659600535e8415bf5c095063d4e10c18dd68241bd8706"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "forecast-hourly" not in text
    assert "detailedForecast" in text
    assert "1.8" not in text


def test_detailed_forecasts_are_not_rewritten() -> None:
    found = load_nws_forecast_detailed(PUBLIC)
    assert found.periods == 14
    assert len(found.values) == 13
    assert found.values[0] == "Clear, with a low around 45."
    assert found.values[-1] == "Sunny, with a high near 71."
    digest = hashlib.sha256("\n".join(found.values).encode()).hexdigest()
    assert digest == _DIGEST
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_detailed_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "13 distinct values." in note
    assert "Clear, with a low around 45." in note
    assert "Sunny, with a high near 71." in note
    assert "The hourly body was not used." in note
    assert "A forecast was not rewritten into another word." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
