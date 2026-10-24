"""Metadata family behavior: source isolation, missing data and archive rejection."""

import json
import shutil
import socket
from pathlib import Path

import pytest

from entropytrade.weather.nws_metadata import NwsMetadataField, NwsSource, read_nws_metadata

PUBLIC = Path(__file__).resolve().parents[3] / "data" / "public"
FIELDS: tuple[NwsMetadataField, ...] = (
    "generatedAt",
    "updateTime",
    "validTimes",
    "forecastGenerator",
    "units",
)


@pytest.fixture
def archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def refuse_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("recorded metadata must never open a socket")

    monkeypatch.setattr(socket, "socket", refuse_network)
    shutil.copytree(PUBLIC / "nws", tmp_path / "nws")
    return tmp_path


def _body(root: Path, source: NwsSource) -> Path:
    name = "forecast-hourly-phi-48-75.json" if source == "hourly" else "forecast-phi-48-75.json"
    return root / "nws" / name


@pytest.mark.parametrize("source", ["forecast", "hourly"])
def test_metadata_preserves_strings_and_uses_only_its_source(
    archive: Path, source: NwsSource
) -> None:
    # The other forecast document is deliberately unusable.
    other: NwsSource = "hourly" if source == "forecast" else "forecast"
    _body(archive, other).write_text("invalid JSON", encoding="utf-8")
    path = _body(archive, source)
    body = json.loads(path.read_text(encoding="utf-8"))
    for field in FIELDS:
        body["properties"][field] = "  source text, not a parsed clock  "
    path.write_text(json.dumps(body), encoding="utf-8")
    for field in FIELDS:
        assert read_nws_metadata(archive, source=source, field=field) == (
            "  source text, not a parsed clock  ",
            None,
        )


@pytest.mark.parametrize("source", ["forecast", "hourly"])
def test_missing_and_malformed_metadata_is_never_invented(archive: Path, source: NwsSource) -> None:
    path = _body(archive, source)
    body = json.loads(path.read_text(encoding="utf-8"))
    raw_values: tuple[object, ...] = (None, "", False, 123, {}, [])
    for raw in raw_values:
        for field in FIELDS:
            body["properties"][field] = raw
        path.write_text(json.dumps(body), encoding="utf-8")
        for field in FIELDS:
            if raw is None or raw == "":
                assert read_nws_metadata(archive, source=source, field=field) == (
                    None,
                    f"missing {field}",
                )
            elif field == "units":
                assert read_nws_metadata(archive, source=source, field=field) == (
                    None,
                    "units is not a string",
                )
            else:
                with pytest.raises(ValueError, match=f"{field} is not text"):
                    read_nws_metadata(archive, source=source, field=field)
    for field in FIELDS:
        body["properties"].pop(field)
    path.write_text(json.dumps(body), encoding="utf-8")
    for field in FIELDS:
        assert read_nws_metadata(archive, source=source, field=field) == (None, f"missing {field}")


@pytest.mark.parametrize("source", ["forecast", "hourly"])
def test_metadata_refuses_invalid_archive_provenance(archive: Path, source: NwsSource) -> None:
    name = "hourly.manifest.json" if source == "hourly" else "forecast.manifest.json"
    path = archive / "nws" / name
    original = json.loads(path.read_text(encoding="utf-8"))
    changes = ({"traded": True}, {"promoted": True})
    status_key = "http_status" if source == "hourly" else "forecast_status"
    url_key = "url" if source == "hourly" else "forecast_url"
    for change in (*changes, {status_key: 500}, {url_key: "https://example.com/changed"}):
        path.write_text(json.dumps(original | change), encoding="utf-8")
        with pytest.raises(ValueError, match="NWS"):
            read_nws_metadata(archive, source=source, field="generatedAt")
