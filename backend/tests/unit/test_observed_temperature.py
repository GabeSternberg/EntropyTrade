"""The stored Philadelphia observed-temperature archive. No socket and no trade."""

import json
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.observed_temperature import (
    load_observed_temperature,
    observed_temperature_note,
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
    / "observed_temperature.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_observed_temperature_is_stored_and_not_traded() -> None:
    archive = load_observed_temperature(PUBLIC)
    assert archive.http_status == 200
    assert archive.field == "temperature_2m"
    assert archive.hours == 960
    assert archive.nulls == 0
    assert len(archive.times) == 960
    assert len(archive.values) == 960
    assert archive.first_time == "2026-08-24T00:00"
    assert archive.last_time == "2026-10-02T23:00"
    assert archive.first_value == Decimal("72.7")
    assert archive.last_value == Decimal("72.5")
    assert archive.unit == "°F"
    assert archive.requested_latitude == "39.87"
    assert archive.requested_longitude == "-75.23"
    assert archive.response_latitude == Decimal("39.89455")
    assert archive.response_longitude == Decimal("-75.18826")
    assert archive.timezone == "GMT"
    assert archive.has_issue_time is False
    assert archive.traded is False
    assert archive.promoted is False
    assert all(not item.startswith("2026-08-23") for item in archive.times)
    manifest_path = PUBLIC / "open-meteo" / "observed-temperature.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "start_date=2026-08-24" in manifest["url"]
    assert "end_date=2026-10-02" in manifest["url"]
    previous = (PUBLIC / "open-meteo" / "previous-runs.json").read_text(encoding="utf-8")
    precip = (PUBLIC / "open-meteo" / "precipitation-previous-day1.json").read_text(
        encoding="utf-8"
    )
    assert '"temperature_2m"' not in previous
    assert '"temperature_2m"' not in precip
    note = observed_temperature_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| recent observed temperature | no stored value |" in text
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
