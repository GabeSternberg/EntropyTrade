"""Feature manifest and prediction records for the rescore. No socket."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.exchange.trade_prints import load_trade_tape
from entropytrade.weather.cli_observations import load_comparison
from entropytrade.weather.provenance import (
    known_highs,
    load_feature_manifest,
    load_prediction_records,
    refuse_late_label,
)

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_prediction_records_match_the_manifest_and_do_not_trade() -> None:
    manifest = load_feature_manifest(ROOT)
    records = load_prediction_records(ROOT)
    assert manifest["version"] == "cli-rescore-features-v2"
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


def test_a_label_after_the_decision_cannot_be_included() -> None:
    decision = datetime(2026, 8, 25, 15, tzinfo=UTC)
    with pytest.raises(ValueError, match="available_at"):
        refuse_late_label(decision + timedelta(hours=1), decision)
    labels, _comparison = load_comparison(ROOT)
    records = load_prediction_records(ROOT)
    rows = {_text(row.get("valid_on")): row for row in _rows(load_feature_manifest(ROOT))}
    tape = load_trade_tape(ROOT)
    late_prints = 0
    for record in records:
        known = known_highs(labels, record.decision_time)
        assert all(stamp <= record.decision_time for stamp, _high in known)
        same_day = [label for label in labels if label.valid_on == record.decision_time.date()]
        assert len(same_day) == 1
        assert same_day[0].available_at > record.decision_time
        assert all(stamp != same_day[0].available_at for stamp, _high in known)
        day_prints = [
            item
            for item in tape.b805_prints
            if ticker_target_date(item.ticker) == record.decision_time.date() and item.count > 0
        ]
        known_prints = sum(1 for item in day_prints if item.created_at <= record.decision_time)
        late_prints += sum(1 for item in day_prints if item.created_at > record.decision_time)
        row = rows[record.decision_time.date().isoformat()]
        assert row.get("prints_at_decision") == known_prints
    assert late_prints > 0


def _rows(manifest: object) -> tuple[dict[str, object], ...]:
    if not isinstance(manifest, dict):
        raise AssertionError("manifest is not an object")
    rows = manifest.get("rows")
    assert isinstance(rows, list)
    return tuple(item for item in rows if isinstance(item, dict))


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


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
