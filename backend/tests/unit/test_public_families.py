"""Controlled public-wire acquisition; these fixtures are never empirical market evidence."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from entropytrade.domain.time import SimulatedClock
from entropytrade.families.public import BoundedTransport, forward_data
from entropytrade.families.weather_capture import capture_public
from entropytrade.weather.collection import WeatherConfig
from tests.exchange.test_gateway_http import _market_body

WHEN = datetime(2026, 10, 25, 15, tzinfo=UTC)
REPO = Path(__file__).resolve().parents[3]


def weather() -> WeatherConfig:
    return WeatherConfig.model_validate_json(
        (REPO / "configs/data/weather-forward.json").read_text()
    )


def listing(request: httpx.Request) -> httpx.Response:
    assert request.method == "GET"
    assert not any("kalshi-access" in key or "authorization" in key for key in request.headers)
    assert request.url.params["series_ticker"] == "KXBTC"
    assert request.url.params["status"] == "open"
    body = _market_body()
    second = "cursor" in request.url.params
    body.update(
        ticker="KXBTC-26OCT25-T" + ("100001" if second else "100000"),
        event_ticker="KXBTC-26OCT25",
        title="CONTROLLED Bitcoin test contract",
        open_time="2026-10-24T00:00:00Z",
        close_time="2026-10-26T00:00:00Z",
        latest_expiration_time="2026-10-26T01:00:00Z",
        floor_strike="100000",
        rules_primary=(
            "If the Bitcoin reference value is above the strike according to CF Benchmarks."
        ),
    )
    return httpx.Response(200, json={"markets": [body], "cursor": "" if second else "page2"})


def spot(request: httpx.Request) -> httpx.Response:
    assert str(request.url) == "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
    assert "authorization" not in request.headers
    return httpx.Response(200, json={"price": "101234.56", "time": WHEN.isoformat()})


def test_bitcoin_public_capture_reuses_shared_samples_without_outcomes_or_liquidity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "capture"
    data = asyncio.run(
        capture_public(
            root,
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(listing),
            source_transport=httpx.MockTransport(spot),
        )
    )
    assert (
        data.data_kind == "real"
    )  # Wire fixture exercises the real-data adapter, not performance.
    assert len(data.samples) == 2
    assert len({sample.event_id for sample in data.samples}) == 1
    assert data.samples[0].features["spot_minus_floor_usd"] == Decimal("1234.56")
    assert all(s.features_available_at == WHEN and not s.rules_known for s in data.samples)
    assert all(
        s.outcome is None and s.book is None and s.fidelity == "missing" for s in data.samples
    )
    contract = data.provenance["contracts"][0]
    assert contract["settlement_sources"] == []
    assert contract["settlement_basis"] == "unresolved"
    assert contract["authority_mentions"] == [
        {
            "name": "CF Benchmarks",
            "text": "CF Benchmarks",
            "rule_field": "rules_primary",
            "status": "unverified_mention",
        }
    ]
    assert "Coinbase" in data.provenance["limitations"][-1]
    assert data.provenance["capture"]["universe_complete"]
    assert not data.provenance["capture"]["history_complete"]
    assert forward_data(root) == data
    path = next((root / "raw").glob("*.json"))
    path.write_text("{}")
    with pytest.raises(ValueError, match="checksum mismatch"):
        forward_data(root)


@pytest.mark.parametrize(
    ("primary", "secondary"),
    [
        ("Resolution terms unavailable.", ""),
        ("Bitcoin above $100,000 at close.", ""),
        ("CF Benchmarks determines the Bitcoin reference value.", ""),
        ("Bitcoin above the strike according to CF Benchmarks.", ""),
        ("CF Benchmarks is not the settlement source; see additional terms.", ""),
        ("Do not use CF Benchmarks for settlement.", ""),
        ("Settlement may use CF Benchmarks or another index.", ""),
        ("CF Benchmarks is discussed as an alternative, not an authority.", ""),
        ("The authority is unresolved.", "Do not use cf benchmarks."),
        ("Bitcoin above $100,000 at 4pm.", "CF Benchmarks; averaging interval unspecified."),
        (
            "CF Benchmarks BRTI averaged over the last 60 seconds before 4pm New York time.",
            "YES if strictly above $100,000; rounding and fallback terms are unspecified.",
        ),
    ],
)
def test_ambiguous_bitcoin_rules_never_open_resolution_gate(
    tmp_path: Path, primary: str, secondary: str
) -> None:
    def ambiguous(request: httpx.Request) -> httpx.Response:
        payload = json.loads(listing(request).content)
        for market in payload["markets"]:
            market.update(rules_primary=primary, rules_secondary=secondary)
        return httpx.Response(200, json=payload)

    root = tmp_path / "capture"
    data = asyncio.run(
        capture_public(
            root,
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(ambiguous),
            source_transport=httpx.MockTransport(spot),
        )
    )
    assert len(data.samples) == 2
    assert all(not sample.rules_known and sample.outcome is None for sample in data.samples)
    assert all(not contract["rules_known"] for contract in data.provenance["contracts"])
    assert all(contract["settlement_sources"] == [] for contract in data.provenance["contracts"])
    assert all(
        contract["settlement_basis"] == "unresolved" for contract in data.provenance["contracts"]
    )
    for contract in data.provenance["contracts"]:
        mentions = contract["authority_mentions"]
        assert len(mentions) == int("cf benchmarks" in (primary + secondary).casefold())
        for mention in mentions:
            assert mention["status"] == "unverified_mention"
            assert mention["text"] in contract[mention["rule_field"]]
    for line in (root / "markets.jsonl").read_text().splitlines():
        rules = json.loads(line)["market"]["rules"]
        assert rules["settlement_sources"] == []
        assert rules["settlement_basis"] == "unresolved"
        assert rules["settlement_target_date"] is None
    assert all(contract["rules_primary"] == primary for contract in data.provenance["contracts"])
    assert all(
        contract["rules_secondary"] == secondary for contract in data.provenance["contracts"]
    )
    assert forward_data(root) == data


def test_bitcoin_authority_names_cannot_be_assembled_across_rule_fields(tmp_path: Path) -> None:
    def split_name(request: httpx.Request) -> httpx.Response:
        payload = json.loads(listing(request).content)
        for market in payload["markets"]:
            market.update(rules_primary="Authority CF", rules_secondary=" Benchmarks unknown.")
        return httpx.Response(200, json=payload)

    data = asyncio.run(
        capture_public(
            tmp_path / "capture",
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(split_name),
            source_transport=httpx.MockTransport(spot),
        )
    )
    assert data.samples
    assert all(not sample.rules_known for sample in data.samples)
    assert all(
        contract["authority_mentions"] == []
        and contract["settlement_sources"] == []
        and contract["settlement_basis"] == "unresolved"
        for contract in data.provenance["contracts"]
    )


@pytest.mark.parametrize("offset", [-3600, 3600])
def test_stale_or_future_spot_never_becomes_a_feature(tmp_path: Path, offset: int) -> None:
    def source(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "price": "101234.56",
                "time": (WHEN + timedelta(seconds=offset)).isoformat(),
            },
        )

    data = asyncio.run(
        capture_public(
            tmp_path / "capture",
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(listing),
            source_transport=httpx.MockTransport(source),
        )
    )
    assert data.samples
    assert all(s.features["spot_usd"] is None for s in data.samples)
    assert not any(s.eligible for s in data.samples)
    assert not any(s.outcome for s in data.samples)


def test_failed_public_feeds_preserve_receipts_and_insufficiency_without_fixture_fallback(
    tmp_path: Path,
) -> None:
    def unavailable(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "controlled outage"})

    data = asyncio.run(
        capture_public(
            tmp_path / "capture",
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(unavailable),
            source_transport=httpx.MockTransport(unavailable),
        )
    )
    assert not data.samples
    capture = data.provenance["capture"]
    assert len(capture["failures"]) == 2
    assert all(failure["failed_at"] == WHEN.isoformat() for failure in capture["failures"])
    assert capture["started_at"] == capture["decision_time"] == WHEN.isoformat()
    assert len(capture["receipts"]) == 2
    assert capture["truncated_universe"]
    assert not capture["universe_complete"]
    assert capture["observations"] == 0
    assert data.provenance["source_kinds"] == []


def test_public_transport_rejects_writes_auth_redirect_hosts_and_excess_bytes() -> None:
    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=BoundedTransport(httpx.MockTransport(spot))
        ) as client:
            for method, url, headers, reason in (
                (
                    "POST",
                    "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
                    {},
                    "request budget exceeded",
                ),
                (
                    "GET",
                    "http://api.exchange.coinbase.com/products/BTC-USD/ticker",
                    {},
                    "destination/authentication denied",
                ),
                ("GET", "https://attacker.invalid/", {}, "destination/authentication denied"),
                (
                    "GET",
                    "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
                    {"Authorization": "test"},
                    "destination/authentication denied",
                ),
            ):
                with pytest.raises(ValueError, match=reason):
                    await client.request(method, url, headers=headers)
        oversized = httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 2_000_001))
        async with httpx.AsyncClient(transport=BoundedTransport(oversized)) as client:
            with pytest.raises(ValueError, match="byte budget"):
                await client.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")

    asyncio.run(exercise())


def test_manifest_and_raw_references_are_both_verified(tmp_path: Path) -> None:
    root = tmp_path / "capture"
    asyncio.run(
        capture_public(
            root,
            family="bitcoin",
            weather=weather(),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(listing),
            source_transport=httpx.MockTransport(spot),
        )
    )
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["decision_time"] = "2020-01-01T00:00:00+00:00"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest identity mismatch"):
        forward_data(root)


def test_weather_reuses_complete_local_day_and_exported_forecast_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("entropytrade.weather.collection.utc_now", lambda: WHEN)
    monkeypatch.setattr("entropytrade.storage.forecast_archive.utc_now", lambda: WHEN)

    def markets(request: httpx.Request) -> httpx.Response:
        assert request.url.params["series_ticker"] == "KXHIGHPHIL"
        body = _market_body()
        body.update(
            ticker="KXHIGHPHIL-26OCT25-T89",
            event_ticker="KXHIGHPHIL-26OCT25",
            open_time="2026-10-24T00:00:00Z",
            close_time="2026-10-26T04:00:00Z",
            latest_expiration_time="2026-10-26T05:00:00Z",
        )
        return httpx.Response(200, json={"markets": [body], "cursor": ""})

    def forecast(_: httpx.Request) -> httpx.Response:
        start = WHEN.replace(hour=0)
        return httpx.Response(
            200,
            json={
                "utc_offset_seconds": 0,
                "latitude": 39.87,
                "longitude": -75.23,
                "hourly_units": {"temperature_2m": "°F"},
                "hourly": {
                    "time": [(start + timedelta(hours=h)).isoformat() for h in range(72)],
                    "temperature_2m": [70 for _ in range(72)],
                },
            },
        )

    config = weather().revalidated(locations=weather().locations[:1], providers=("open-meteo",))
    root = tmp_path / "weather"
    data = asyncio.run(
        capture_public(
            root,
            family="weather",
            weather=config,
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(markets),
            source_transport=httpx.MockTransport(forecast),
        )
    )
    assert data.samples
    assert data.samples[0].features["forecast_high_f"] == 70
    assert not data.samples[0].outcome
    assert data.samples[0].book is None
    assert data.provenance["contracts"][0]["settlement_sources"][0]["name"] == "The Weather Company"
    assert forward_data(root) == data
    # Observations cite the capture's own exact response bytes; no duplicate body copies or
    # archive database are retained, and the receipt ledger keeps each receipt's provenance.
    assert not (root / "weather.sqlite").exists()
    assert not (root / "weather/raw").exists()
    assert not (root / "weather/observations.jsonl").exists()
    capture = json.loads((root / "capture.json").read_text())
    retained = {r["raw_ref"]: r for r in capture["receipts"]}
    ledger = json.loads((root / "weather/receipts.json").read_text())
    assert ledger["schema"] == "entropytrade-weather-receipts-v1"
    (receipt,) = ledger["receipts"]
    assert receipt["vintage_id"]
    assert receipt["failure"] is None
    assert retained[receipt["raw_ref"]]["hash"] == receipt["sha256"]
    assert retained[receipt["raw_ref"]]["path"] == receipt["url"]
    observations = [
        json.loads(line) for line in (root / "observations.jsonl").read_text().splitlines()
    ]
    assert {o["raw_ref"] for o in observations} == {receipt["raw_ref"]}
    assert {o["raw_hash"] for o in observations} == {receipt["sha256"]}


@pytest.mark.parametrize("failure", ["connect", "http"])
def test_partial_weather_capture_exposes_clocked_failures_and_actual_response_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setattr("entropytrade.weather.collection.utc_now", lambda: WHEN)
    monkeypatch.setattr("entropytrade.storage.forecast_archive.utc_now", lambda: WHEN)

    def markets(_: httpx.Request) -> httpx.Response:
        body = _market_body()
        body.update(
            ticker="KXHIGHPHIL-26OCT25-T89",
            event_ticker="KXHIGHPHIL-26OCT25",
            open_time="2026-10-24T00:00:00Z",
            close_time="2026-10-26T04:00:00Z",
            latest_expiration_time="2026-10-26T05:00:00Z",
        )
        return httpx.Response(200, json={"markets": [body], "cursor": ""})

    def source(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.weather.gov":
            if failure == "connect":
                raise httpx.ConnectError("controlled unavailability", request=request)
            return httpx.Response(503, content=b"Controlled NWS failure response")
        start = WHEN.replace(hour=0)
        return httpx.Response(
            200,
            json={
                "utc_offset_seconds": 0,
                "latitude": 39.87,
                "longitude": -75.23,
                "hourly_units": {"temperature_2m": "°F"},
                "hourly": {
                    "time": [(start + timedelta(hours=h)).isoformat() for h in range(72)],
                    "temperature_2m": [70 for _ in range(72)],
                },
            },
        )

    root = tmp_path / "capture"
    data = asyncio.run(
        capture_public(
            root,
            family="weather",
            weather=weather().revalidated(locations=weather().locations[:1]),
            clock=SimulatedClock(WHEN),
            kalshi_transport=httpx.MockTransport(markets),
            source_transport=httpx.MockTransport(source),
        )
    )
    assert data.samples[0].features["forecast_high_f"] == 70
    capture = data.provenance["capture"]
    assert not capture["universe_complete"]
    assert capture["truncated_universe"]
    assert all(f["failed_at"] == WHEN.isoformat() for f in capture["failures"])
    assert any(
        f["failure"] == ("ConnectError" if failure == "connect" else "HTTP503")
        and "api.weather.gov/points/" in f["source"]
        for f in capture["failures"]
    )
    receipts = capture["receipts"]
    assert all(r["received_at"] == WHEN.isoformat() for r in receipts)
    assert any("api.open-meteo.com" in r["path"] and r["status"] == 200 for r in receipts)
    nws = [r for r in receipts if "api.weather.gov" in r["path"]]
    if failure == "http":
        assert len(nws) == 1
        assert nws[0]["status"] == 503
        assert (root / nws[0]["raw_ref"]).read_bytes() == b"Controlled NWS failure response"
    else:
        assert not nws  # No response exists for a failed connection.
    # Every archived forecast receipt resolves to its exact retained response bytes.
    ledger = json.loads((root / "weather/receipts.json").read_text())["receipts"]
    assert ledger
    for row in ledger:
        assert row["raw_ref"] in {r["raw_ref"] for r in receipts}
        assert row["sha256"] == next(r["hash"] for r in receipts if r["raw_ref"] == row["raw_ref"])
        assert row["vintage_id"] is None or row["failure"] is None
    if failure == "http":
        (nws_row,) = [row for row in ledger if row["status"] == 503]
        assert nws_row["raw_ref"] == nws[0]["raw_ref"]
    assert forward_data(root) == data


def test_forward_data_module_is_frozen_for_retained_shadow_cycles() -> None:
    # forward_data binds every capture's feature_version to this module's file hash, and
    # verified_inputs refuses a retained shadow cycle whose saved version no longer matches.
    # Editing families/public.py would therefore invalidate every retained authentic cycle
    # (including a running forward chain). Put new capture code in families/weather_capture.py.
    from entropytrade.data.sources import file_hash
    from entropytrade.families import public

    assert file_hash(Path(public.__file__)) == (
        "sha256:3aa89015f7f3e6354d085a718f97e6e0fd0a58643cea023a08855f644007dd05"
    ), "families/public.py changed: retained shadow cycles would fail verification"
