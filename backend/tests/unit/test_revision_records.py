"""Revision-bracket prediction records. 2 F and 0.40 stay put. No holdout."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from entropytrade.agents.fixture import demo_specs
from entropytrade.weather.cli_observations import load_comparison
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.provenance import load_prediction_records
from entropytrade.weather.revision_bracket import (
    NO_STORED_BRACKET,
    SCAN_TICKERS,
    load_austin_bracket,
    load_chicago_bracket,
    load_dallas_bracket,
    load_down_decisions,
    load_newyork_bracket,
    load_oklahomacity_bracket,
    load_philadelphia_bracket,
    load_revision_decisions,
    load_scan_bracket,
    load_skipped_revision_days,
)
from entropytrade.weather.revision_records import (
    down_records_note,
    load_down_records,
    load_revision_empty_fields,
    load_revision_hash_gap,
    load_revision_records,
    load_revision_strategy,
    records_note,
    revision_prediction_ids,
    skipped_note,
)
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F
from entropytrade.weather.walk_forward import _thirds

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "revision_records.py"
)
_RESCORE = ROOT / "features" / "cli-rescore-predictions.json"


def test_revision_records_match_the_scored_days() -> None:
    decisions = load_revision_decisions(ROOT)
    assert decisions
    assert {item.fold for item in decisions} == {"train", "validation"}
    fires = tuple(item for item in decisions if item.fired)
    quiet = tuple(item for item in decisions if not item.fired)
    assert quiet
    assert all(item.ticker == NO_STORED_BRACKET for item in quiet)
    scores = (
        load_philadelphia_bracket(ROOT),
        load_chicago_bracket(ROOT),
        load_newyork_bracket(ROOT),
        load_austin_bracket(ROOT),
        load_oklahomacity_bracket(ROOT),
        load_dallas_bracket(ROOT),
        *(load_scan_bracket(ROOT, ticker) for ticker in SCAN_TICKERS),
    )
    expected = sum(score.train.fires + score.validation.fires for score in scores)
    assert len(fires) == expected
    philadelphia = tuple(item for item in fires if item.place == "Philadelphia")
    assert len(philadelphia) == 1
    assert philadelphia[0].fold == "train"
    assert philadelphia[0].ticker.startswith("KXHIGHPHIL-")
    boston = tuple(
        item for item in fires if item.place == "Boston" and item.ticker != NO_STORED_BRACKET
    )
    assert boston
    assert all(item.ticker.startswith("KXHIGHTBOS-") for item in boston)
    labels, _comparison = load_comparison(ROOT)
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    train, validation, holdout = _thirds(ordered)
    recorded = {item.valid_on for item in decisions if item.place == "Philadelphia"}
    assert recorded.isdisjoint({label.valid_on for label in holdout})
    assert recorded <= {label.valid_on for label in train + validation}
    records = load_revision_records(ROOT)
    assert len(records) == len(decisions)
    assert sum(record.probability_yes == Decimal(1) for record in records) == expected
    for record in records:
        assert record.probability_yes in {Decimal(0), Decimal(1)}
        assert record.market_yes_bid is None
        assert record.market_yes_ask is None
        assert record.net_edge_estimate is None
        assert record.uncertainty is None
        assert record.calibration_version is None
        assert record.strategy_id == "forecast_revision_bracket"
        assert record.strategy_version == 1
        assert record.decision_time.hour == 15
        assert record.decision_time.date() >= date(2026, 8, 1)
    text = _SOURCE.read_text(encoding="utf-8")
    assert "urllib" not in text
    assert "httpx" not in text
    assert "cli-aligned" in _RESCORE.read_text(encoding="utf-8")
    note = records_note(ROOT)
    assert "The holdout is not recorded." in note
    assert "Nothing was promoted." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_skipped_revision_days_are_missing_vintages() -> None:
    decisions = load_revision_decisions(ROOT)
    skipped = load_skipped_revision_days(ROOT)
    scores = (
        load_philadelphia_bracket(ROOT),
        load_chicago_bracket(ROOT),
        load_newyork_bracket(ROOT),
        load_austin_bracket(ROOT),
        load_oklahomacity_bracket(ROOT),
        load_dallas_bracket(ROOT),
        *(load_scan_bracket(ROOT, ticker) for ticker in SCAN_TICKERS),
    )
    window = sum(score.train_days + score.validation_days for score in scores)
    assert len(decisions) + len(skipped) == window
    assert len(skipped) == 17
    assert {item.reason for item in skipped} == {"a vintage max is missing"}
    assert {item.fold for item in skipped} == {"train"}
    assert {item.valid_on for item in skipped} == {date(2026, 8, 23)}
    assert "Philadelphia" not in {item.place for item in skipped}
    assert "Chicago" not in {item.place for item in skipped}
    recorded = {(item.place, item.valid_on) for item in decisions}
    left_out = {(item.place, item.valid_on) for item in skipped}
    assert recorded.isdisjoint(left_out)
    labels, _comparison = load_comparison(ROOT)
    ordered = tuple(sorted(labels, key=lambda label: (label.valid_on, label.available_at)))
    _train, _validation, holdout = _thirds(ordered)
    holdout_days = {label.valid_on for label in holdout}
    assert holdout_days.isdisjoint(item.valid_on for item in skipped)
    note = skipped_note(ROOT)
    assert "Train and validation days left out of the revision records: 17." in note
    assert "Vintage clock after 15:00 UTC: 0." in note
    assert "Vintage clock at or after the label: 0." in note
    assert "A vintage max is missing: 17." in note
    assert "The holdout is not listed." in note
    assert "Nothing was promoted." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_down_records_keep_the_frozen_fire() -> None:
    records = load_down_records(ROOT)
    decisions = load_down_decisions(ROOT)
    upward = revision_prediction_ids(ROOT)
    cli = {record.prediction_id for record in load_prediction_records(ROOT)}
    downward = {record.prediction_id for record in records}
    assert len(records) == 551
    assert len(decisions) == 551
    assert len(downward) == 551
    assert sum(record.probability_yes == Decimal(1) for record in records) == 227
    assert sum(item.fired for item in decisions) == 227
    assert sum(item.fired and item.place == "Philadelphia" for item in decisions) == 18
    assert downward.isdisjoint(upward)
    assert downward.isdisjoint(cli)
    for record in records:
        assert record.strategy_id == "forecast_revision_down"
        assert record.probability_yes in {Decimal(0), Decimal(1)}
        assert record.market_yes_bid is None
        assert record.market_yes_ask is None
        assert record.net_edge_estimate is None
        assert record.calibration_version is None
        assert record.uncertainty is None
        if record.probability_yes == Decimal(0):
            assert record.market_ticker == "no-stored-bracket"
    assert len(load_revision_records(ROOT)) == 551
    note = down_records_note(ROOT)
    assert "Fires: 227." in note
    assert "The holdout is not recorded." in note
    assert "Nothing was promoted." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_revision_calibration_and_uncertainty_stay_empty() -> None:
    gap = load_revision_empty_fields(ROOT)
    assert gap.records == 551
    assert gap.calibration_version_empty == 551
    assert gap.uncertainty_empty == 551
    spec = Path(__file__).resolve().parents[3] / "docs" / "project-spec.md"
    text = spec.read_text(encoding="utf-8")
    assert "calibration version" in text
    assert "uncertainty" in text
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_revision_ids_do_not_collide_with_the_cli_rescore() -> None:
    revision = revision_prediction_ids(ROOT)
    cli = load_prediction_records(ROOT)
    cli_ids = {record.prediction_id for record in cli}
    assert len(revision) == 551
    assert len(cli) == 39
    assert len(cli_ids) == 39
    assert revision.isdisjoint(cli_ids)
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_revision_strategy_is_not_a_stored_spec() -> None:
    named = load_revision_strategy(ROOT)
    assert named.records == 551
    assert named.strategy_id == "forecast_revision_bracket"
    assert named.strategy_version == 1
    specs = {spec.strategy_id for spec in demo_specs()}
    assert named.strategy_id not in specs
    hits = sorted(
        path
        for path in ROOT.rglob("*.json")
        if named.strategy_id in path.read_text(encoding="utf-8")
    )
    assert hits == [
        ROOT / "features" / "revision-bracket-manifest.json",
        ROOT / "features" / "revision-bracket-predictions.json",
    ]
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_revision_feature_hash_omits_ticker_fold_and_fired() -> None:
    gap = load_revision_hash_gap(ROOT)
    assert gap.omitted_keys == ("fired", "fold", "ticker")
    assert "high_f" not in gap.row_keys
    assert "yes_price" not in gap.row_keys
    assert gap.hashed_keys == tuple(key for key in gap.row_keys if key not in gap.omitted_keys)
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
