"""Forward locations: each configured station is bound by retained authentic evidence."""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

from entropytrade.operations.forward import station_bindings
from entropytrade.weather.collection import WeatherConfig
from entropytrade.weather.labels import STATIONS

REPO = Path(__file__).resolve().parents[3]
AUTHENTIC = (
    REPO / "data/local-operation-review/20261029-leased-source-final/listener-recovery/workspace"
)
# Pin the verified weather capture. This workspace also retains an interrupted cycle whose
# public directory has no manifest; filesystem iteration order cannot identify the fixture.
AUTHENTIC_CAPTURE = (
    AUTHENTIC
    / "shadow/f0995225-3eaa-43a4-8854-c1e01b8fc661/52c8a2b8-ae2b-4fb5-a9f3-4aacfcdbe276/public"
)
PORTAL = REPO / "data/weather-label-review/20261031/probe/primary-2026-10-29.json"
RETAINED_RULES = {
    "KXHIGHNY": REPO / "data/public/newyork/manifest.json",
    "KXHIGHTDAL": REPO / "data/public/dallas/manifest.json",
}


def config() -> WeatherConfig:
    return WeatherConfig.model_validate_json(
        (REPO / "configs/data/weather-forward.json").read_text()
    )


def test_every_forward_location_matches_the_retained_authentic_settlement_portal() -> None:
    portal = {
        r["station"]["cliId"]: r["station"] for r in json.loads(PORTAL.read_text())["results"]
    }
    locations = config().locations
    assert {p.series for p in locations} >= {"KXHIGHPHIL", "KXHIGHCHI", "KXHIGHNY", "KXHIGHTDAL"}
    assert len({p.series for p in locations}) == len({p.station for p in locations})
    for location in locations:
        cli, icao, timezone = STATIONS[location.station]
        assert location.station == "CLI" + cli
        assert location.timezone == timezone
        station = portal[cli]
        assert (station["icao"], station["timezone"], station["isDomestic"]) == (
            icao,
            timezone,
            True,
        )


def test_new_forward_locations_use_retained_rule_and_station_coordinate_receipts() -> None:
    by_series = {p.series: p for p in config().locations}
    for series, path in RETAINED_RULES.items():
        manifest = json.loads(path.read_text())
        location = by_series[series]
        assert manifest["series"] == series
        assert manifest["station"] == location.station
        assert f"({location.station})" in manifest["station_source"]
        assert manifest["coordinate_source"] == "https://api.weather.gov/stations/K" + (
            location.station.removeprefix("CLI")
        )
        # The station coordinates, rounded to the 4 decimals api.weather.gov /points accepts.
        assert (location.latitude, location.longitude) == (
            f"{Decimal(str(manifest['returned_latitude'])):.4f}",
            f"{Decimal(str(manifest['returned_longitude'])):.4f}",
        )


def test_forward_coordinates_have_at_most_four_decimals_for_nws_points() -> None:
    # api.weather.gov/points redirects (301) a point with more decimals; the bounded client
    # does not follow redirects, so every cycle would record an acquisition failure.
    # Run 42213565565 failed its only cycle that way with 40.78858/32.893456.
    for location in config().locations:
        for value in (location.latitude, location.longitude):
            assert value is not None
            exponent = Decimal(value).as_tuple().exponent
            assert isinstance(exponent, int)
            assert -4 <= exponent <= 0, value


def test_station_bindings_on_retained_authentic_capture() -> None:
    report = station_bindings(AUTHENTIC)
    assert report["status"] == "ok"
    assert report["capture_decision_time"] == "2026-10-29T18:07:42.760855+00:00"
    assert [(x["series"], x["status"], x["contracts"]) for x in report["locations"]] == [
        ("KXHIGHPHIL", "matched", 12),
        ("KXHIGHCHI", "matched", 12),
    ]
    assert report["locations"][0]["named_stations"] == {"CLIPHL": 12}
    assert all(x["label_compatible"] == 12 for x in report["locations"])


def _cycle(
    workspace: Path, name: str, decision: str, locations: list[dict[str, Any]], markets: list[Any]
) -> None:
    root = workspace / "shadow/monitor" / name / "public"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "family": "weather",
                "decision_time": decision,
                "weather_config": {"locations": locations},
            }
        )
    )
    (root / "markets.jsonl").write_text("".join(json.dumps({"market": m}) + "\n" for m in markets))


def _authentic_market(series: str) -> dict[str, Any]:
    line = next(
        line
        for path in sorted(AUTHENTIC.glob("shadow/*/*/public/markets.jsonl"))
        for line in path.read_text().splitlines()
        if json.loads(line)["market"]["series_ticker"] == series
    )
    market: dict[str, Any] = json.loads(line)["market"]
    return market


def test_station_bindings_report_mismatch_unnamed_missing_and_newest_capture(
    tmp_path: Path,
) -> None:
    assert station_bindings(tmp_path) == {"status": "no_capture", "locations": []}
    phl = _authentic_market("KXHIGHPHIL")
    locations = [
        {"series": "KXHIGHPHIL", "station": "CLIPHL", "timezone": "America/New_York"},
        # A wrong mapping: Philadelphia's rules name CLIPHL, never this station.
        {"series": "KXHIGHWRONG", "station": "CLINYC", "timezone": "America/New_York"},
        {"series": "KXHIGHNONE", "station": "CLIDFW", "timezone": "America/Chicago"},
        {"series": "KXHIGHEMPTY", "station": "CLIMDW", "timezone": "America/Chicago"},
        {"series": "KXHIGHTZ", "station": "CLIPHL", "timezone": "America/Chicago"},
    ]
    unnamed = {
        **phl,
        "series_ticker": "KXHIGHNONE",
        "rules": {
            **phl["rules"],
            "rules_primary": "Highest temperature in Dallas.",
            "rules_secondary": "",
        },
    }
    markets = [
        phl,
        {**phl, "series_ticker": "KXHIGHWRONG"},
        unnamed,
        {**phl, "series_ticker": "KXHIGHTZ"},
    ]
    _cycle(tmp_path, "old", "2026-10-29T00:00:00+00:00", locations[:1], [])
    _cycle(tmp_path, "new", "2026-10-30T00:00:00+00:00", locations, markets)
    report = station_bindings(tmp_path)
    assert report["capture"] == "shadow/monitor/new/public"
    assert report["status"] == "review"
    statuses = {x["series"]: x["status"] for x in report["locations"]}
    assert statuses == {
        "KXHIGHPHIL": "matched",
        "KXHIGHWRONG": "mismatch",
        "KXHIGHNONE": "unnamed",
        "KXHIGHEMPTY": "no_contracts",
        "KXHIGHTZ": "partial",  # rules name CLIPHL but the label source refuses that timezone
    }
    wrong = next(x for x in report["locations"] if x["series"] == "KXHIGHWRONG")
    assert wrong["named_stations"] == {"CLIPHL": 1}
    assert wrong["label_compatible"] == 0


def test_station_bindings_ignore_non_weather_and_unreadable_manifests(tmp_path: Path) -> None:
    assert json.loads((AUTHENTIC_CAPTURE / "manifest.json").read_text())["family"] == "weather"
    shutil.copytree(AUTHENTIC_CAPTURE.parent, tmp_path / "shadow/m/c", symlinks=False)
    bad = tmp_path / "shadow/m/broken/public"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text("{not json")
    btc = tmp_path / "shadow/m/btc/public"
    btc.mkdir(parents=True)
    (btc / "manifest.json").write_text(
        json.dumps({"family": "bitcoin", "decision_time": "2099-01-01T00:00:00+00:00"})
    )
    report = station_bindings(tmp_path)
    assert report["capture"] == "shadow/m/c/public"
    assert report["status"] == "ok"
