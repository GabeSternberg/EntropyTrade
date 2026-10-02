"""Feature manifest and prediction records for the rescore. No socket."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.provenance import load_feature_manifest, load_prediction_records

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_prediction_records_match_the_manifest_and_do_not_trade() -> None:
    manifest = load_feature_manifest(ROOT)
    records = load_prediction_records(ROOT)
    assert manifest["version"] == "cli-rescore-features-v1"
    assert len(records) == 39
    assert all(record.probability_yes == Decimal(0) for record in records)
    assert all(record.market_yes_bid is None for record in records)
    assert all(record.market_yes_ask is None for record in records)
    assert all(record.net_edge_estimate is None for record in records)
    assert all(record.source_data_manifest_hash == manifest["manifest_hash"] for record in records)
    tickers = {record.market_ticker for record in records}
    assert any(ticker.endswith("-B80.5") for ticker in tickers)
    assert "KXHIGHPHIL" in tickers
    assert all(record.decision_time.hour == 15 for record in records)


def test_provenance_does_not_fetch() -> None:
    text = (
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("src/entropytrade/weather/provenance.py")
        .read_text(encoding="utf-8")
    )
    for name in ("import urllib", "import httpx", "import socket"):
        assert name not in text
