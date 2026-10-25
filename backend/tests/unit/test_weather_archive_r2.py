"""Forward capture clocks, durable vintages, failures and operational polling."""

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from entropytrade.data.schema import Observation
from entropytrade.data.sources import file_hash
from entropytrade.storage.forecast_archive import ForecastArchive
from entropytrade.weather.collection import WeatherConfig, poll_weather
from entropytrade.weather.forecast import fahrenheit, parse_forecast
from tests.r2_support import LOCATION, open_meteo_body

DAY = date(2025, 2, 1)
RECEIPT = datetime(2025, 1, 31, 19, tzinfo=UTC)


def test_valid_time_is_never_invented_issue_or_publication() -> None:
    vintage = parse_forecast(open_meteo_body(DAY), provider="open-meteo", location=LOCATION)
    assert vintage.issued_at is None
    assert vintage.published_at is None
    assert vintage.points[0].valid_at == datetime(2025, 2, 1, tzinfo=UTC)
    assert vintage.points[0].value == Decimal(70)


def test_nws_update_generation_and_receipt_are_distinct(tmp_path: Path) -> None:
    body = json.dumps(
        {
            "geometry": {},
            "properties": {
                "updateTime": "2025-01-31T17:00:00+00:00",
                "generatedAt": "2025-01-31T18:00:00+00:00",
                "periods": [
                    {
                        "startTime": "2025-02-01T00:00:00-05:00",
                        "temperature": 10,
                        "temperatureUnit": "C",
                    }
                ],
            },
        }
    ).encode()
    archive = ForecastArchive(tmp_path / "weather.sqlite")
    try:
        identity = archive.capture(
            body=body,
            url="fixture:nws",
            status=200,
            received_at=RECEIPT,
            provider="nws",
            location=LOCATION,
        )
        assert identity is not None
        observed = archive.observations()[0]
        assert observed.value == Decimal(50)
        assert observed.valid_at == datetime(2025, 2, 1, 5, tzinfo=UTC)
        assert observed.published_at == RECEIPT - timedelta(hours=2)
        assert observed.issued_at is None
        assert observed.available_at == RECEIPT
        assert not observed.known_at(RECEIPT - timedelta(seconds=1))
        # Product regeneration alone does not claim a new model initialization.
        changed = body.replace(b"18:00:00", b"18:30:00")
        again = archive.capture(
            body=changed,
            url="fixture:nws",
            status=200,
            received_at=RECEIPT + timedelta(hours=1),
            provider="nws",
            location=LOCATION,
        )
        assert again == identity
    finally:
        archive.close()


def test_restart_repeated_sightings_revisions_and_raw_export(tmp_path: Path) -> None:
    path = tmp_path / "archive.sqlite"
    original: str | None = None
    for index in range(2):
        archive = ForecastArchive(path)
        try:
            identity = archive.capture(
                body=open_meteo_body(DAY, generated=index),
                url="fixture:forecast",
                status=200,
                received_at=RECEIPT + timedelta(hours=index),
                provider="open-meteo",
                location=LOCATION,
            )
            assert identity is not None
            if index == 0:
                original = identity
            else:
                assert identity == original
                revised = archive.capture(
                    body=open_meteo_body(DAY, temperature=73),
                    url="fixture:forecast",
                    status=200,
                    received_at=RECEIPT + timedelta(hours=2),
                    provider="open-meteo",
                    location=LOCATION,
                )
                assert revised != original
        finally:
            archive.close()
    archive = ForecastArchive(path, read_only=True)
    try:
        found, summary = archive.snapshot()
        assert summary["vintages"] == 2
        assert summary["receipts"] == 3
        assert len(found) == 96
        assert found[0].available_at == RECEIPT
        assert len([o for o in found if o.known_at(RECEIPT)]) == 48
        archive.export(tmp_path / "export")
    finally:
        archive.close()
    exported = [
        Observation.model_validate_json(line)
        for line in (tmp_path / "export/observations.jsonl").read_text().splitlines()
    ]
    for o in exported:
        assert file_hash(tmp_path / "export" / o.raw_ref) == o.raw_hash
    assert len(list((tmp_path / "export/raw").iterdir())) == 2


def test_failed_or_incomplete_capture_retains_raw_without_fake_forecast(tmp_path: Path) -> None:
    archive = ForecastArchive(tmp_path / "weather.sqlite")
    try:
        for body, status in ((b"bad JSON", 200), (b"rate limited", 429)):
            assert (
                archive.capture(
                    body=body,
                    url="fixture:forecast",
                    status=status,
                    received_at=RECEIPT,
                    provider="open-meteo",
                    location=LOCATION,
                )
                is None
            )
        assert archive.observations() == []
        assert archive.snapshot()[1]["failures"] == 2
        assert archive.count("http_receipts") == 2
    finally:
        archive.close()


@pytest.mark.parametrize(("value", "unit"), [(None, "F"), (True, "F"), ("NaN", "F"), (1, "K")])
def test_temperature_rejects_unknown_units_and_missing(value: object, unit: str) -> None:
    with pytest.raises(ValueError, match="temperature"):
        fahrenheit(value, unit)


def test_mock_http_polling_recovers_and_persists_across_restart(tmp_path: Path) -> None:
    calls = 0
    emitted: list[str] = []

    def response(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.host == "api.open-meteo.com"
        if calls == 1:
            return httpx.Response(503, content=b"retry")
        return httpx.Response(200, content=open_meteo_body(DAY))

    for _ in range(2):
        archive = ForecastArchive(tmp_path / "poll.sqlite")
        try:
            asyncio.run(
                poll_weather(
                    config=WeatherConfig(
                        locations=(LOCATION,), providers=("open-meteo",), attempts=2
                    ),
                    archive=archive,
                    stop=asyncio.Event(),
                    once=True,
                    transport=httpx.MockTransport(response),
                    emit=emitted.append,
                )
            )
            assert archive.snapshot()[1]["vintages"] == 1
        finally:
            archive.close()
    assert calls == 3
    assert all(json.loads(line)["captured"] for line in emitted)


def test_invalid_nws_discovery_is_observable_and_does_not_crash(tmp_path: Path) -> None:
    archive = ForecastArchive(tmp_path / "poll.sqlite")
    emitted: list[str] = []
    try:
        asyncio.run(
            poll_weather(
                config=WeatherConfig(locations=(LOCATION,), providers=("nws",)),
                archive=archive,
                stop=asyncio.Event(),
                once=True,
                emit=emitted.append,
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
            )
        )
        assert json.loads(emitted[0])["captured"] is False
        assert archive.count("http_receipts") == 1
    finally:
        archive.close()


def test_committed_weather_capture_survives_abrupt_process_exit(tmp_path: Path) -> None:
    import subprocess
    import sys

    database = tmp_path / "crash.sqlite"
    script = """
import os
import sys
sys.path.insert(0, "backend")
from pathlib import Path
from datetime import UTC, datetime, date
from tests.r2_support import LOCATION, open_meteo_body
from entropytrade.storage.forecast_archive import ForecastArchive
archive = ForecastArchive(Path(__import__('sys').argv[1]))
archive.capture(body=open_meteo_body(date(2025, 2, 1)), url="fixture:forecast", status=200,
                received_at=datetime(2025, 1, 31, 19, tzinfo=UTC),
                provider="open-meteo", location=LOCATION)
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script, str(database)], check=True)  # noqa: S603
    archive = ForecastArchive(database)
    try:
        observations, summary = archive.snapshot()
        assert summary["vintages"] == 1
        assert len(observations) == 48
        assert observations[0].available_at == RECEIPT
    finally:
        archive.close()
