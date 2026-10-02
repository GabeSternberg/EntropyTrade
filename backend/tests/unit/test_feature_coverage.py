"""The feature note quotes stored columns and does not fill in spec features."""

from pathlib import Path

from entropytrade.weather.feature_coverage import load_feature_coverage

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
