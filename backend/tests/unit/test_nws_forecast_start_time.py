"""Distinct NWS forecast start times. No socket and no computed duration."""

import hashlib
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_forecast_start_time import (
    load_nws_forecast_start_time,
    nws_forecast_start_time_note,
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
    / "nws_forecast_start_time.py"
)
_DIGEST = "b5de2492c0243c49984505b3818b211ac42e8086665a8866dd3acd4cf331087e"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "import datetime" not in text
    assert "timedelta" not in text
    assert "forecast-hourly" not in text
    assert "endTime" not in text
    assert 'period.get("startTime")' in text


def test_forecast_start_times_are_not_a_duration() -> None:
    found = load_nws_forecast_start_time(PUBLIC)
    assert found.periods == 14
    assert len(found.values) == 14
    assert found.values[0] == "2026-10-02T19:00:00-04:00"
    assert found.values[-1] == "2026-10-09T06:00:00-04:00"
    digest = hashlib.sha256("\n".join(found.values).encode()).hexdigest()
    assert digest == _DIGEST
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_forecast_start_time_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "14 distinct values." in note
    assert "The hourly body was not used." in note
    assert "A duration was not computed." in note
    assert "A string was not rewritten." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It was not aligned to the CLI decision clock." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
