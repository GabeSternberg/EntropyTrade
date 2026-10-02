"""The CLI day with no prediction record, and the builder branch that skipped it."""

from dataclasses import fields
from datetime import UTC, date, datetime
from pathlib import Path

from entropytrade.weather.cli_observations import load_comparison
from entropytrade.weather.provenance import (
    SkippedPredictionDay,
    load_feature_manifest,
    load_prediction_records,
    load_skipped_prediction_days,
)

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_august_23_is_skipped_for_empty_climatology() -> None:
    labels, _comparison = load_comparison(ROOT)
    records = load_prediction_records(ROOT)
    skipped = load_skipped_prediction_days(ROOT)
    assert len(labels) == 40
    assert len(records) == 39
    assert len(skipped) == 1
    day = skipped[0]
    assert day.valid_on == date(2026, 8, 23)
    assert day.decision_time == datetime(2026, 8, 23, 15, tzinfo=UTC)
    assert day.label_available_at == datetime(2026, 8, 24, 5, 55, tzinfo=UTC)
    assert day.forecast_available_at == datetime(2026, 8, 23, tzinfo=UTC)
    assert day.forecast_available_at < day.label_available_at
    assert day.known_highs == 0
    assert day.reason == "no CLI high is available at the decision"
    assert day.valid_on not in {record.decision_time.date() for record in records}
    manifest = load_feature_manifest(ROOT)
    rows = manifest.get("rows")
    assert isinstance(rows, list)
    recorded = {row.get("valid_on") for row in rows if isinstance(row, dict)}
    assert day.valid_on.isoformat() not in recorded
    assert "probability" not in {item.name for item in fields(SkippedPredictionDay)}
