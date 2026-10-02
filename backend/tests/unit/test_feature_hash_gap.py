"""The feature-vector hash leaves two manifest row keys out. The hash is unchanged."""

from pathlib import Path

from entropytrade.weather.provenance import load_feature_hash_gap

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_ticker_and_sized_book_are_outside_the_feature_hash() -> None:
    gap = load_feature_hash_gap(ROOT)
    assert gap.omitted_keys == ("market_ticker", "sized_book")
    assert gap.row_keys == (
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
    assert gap.hashed_keys == tuple(key for key in gap.row_keys if key not in gap.omitted_keys)
