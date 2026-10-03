"""The feature note quotes stored columns and does not fill in spec features."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.feature_coverage import (
    load_feature_coverage,
    revision_coverage_note,
    revision_manifest_features,
)
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_records import build_revision_payload
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"


def test_the_note_matches_the_stored_manifest() -> None:
    coverage = load_feature_coverage(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert "does not fit a model" in text
    assert "Nothing was promoted" in text
    assert coverage.manifest_features == (
        "forecast_high",
        "point_in_time_climatology",
        "prints_at_decision",
    )
    assert coverage.row_keys == (
        "climatology",
        "decision_time",
        "forecast_available_at",
        "forecast_high_f",
        "market_listed",
        "market_ticker",
        "prints_at_decision",
        "raw_probability",
        "sized_book",
        "station",
        "valid_on",
    )
    assert coverage.previous_runs_hourly == ("time", "temperature_2m_previous_day1")
    assert coverage.row_count == 39
    assert coverage.record_count == 39
    assert coverage.station == "CLIPHL"
    assert coverage.decision == "15:00:00Z"
    assert coverage.empty_bids == 39
    assert coverage.empty_asks == 39
    assert coverage.sized_book_false == 39
    assert coverage.absent_spec_features == coverage.spec_features
    assert len(coverage.spec_features) == 27
    for name in coverage.spec_features:
        assert f"| {name} | no stored value |" in text
    for column in coverage.manifest_features:
        assert column in text
    features = revision_manifest_features(PUBLIC)
    assert features == build_revision_payload(PUBLIC)["features"]
    note = revision_coverage_note(PUBLIC)
    assert note in text
    assert "They are not CLI rescore columns." in note
    assert "They are not a new threshold." in note
    assert "The holdout is not scored." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
