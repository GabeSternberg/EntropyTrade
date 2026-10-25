"""Causal feature families across forecast vintages, local days and verified labels."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from entropytrade.features.pipeline import feature_rows, full_day_maxima
from tests.r2_support import LOCATION, observation, row

DAY = date(2025, 2, 1)
AT = datetime(2025, 2, 1, 15, tzinfo=UTC)


def values(result: dict[str, object]) -> dict[str, float | None]:
    return dict(json.loads(str(result["feature_values_json"])))


def test_later_forecast_and_observation_do_not_leak_into_earlier_decision() -> None:
    observations = [
        observation(DAY, 70, AT - timedelta(hours=3), revision="old"),
        observation(DAY, 74, AT + timedelta(minutes=1), revision="new"),
        observation(
            DAY, 60, AT + timedelta(minutes=1), variable="observed_temperature_f"
        ).revalidated(valid_at=AT - timedelta(hours=1)),
    ]
    earlier = feature_rows([row(DAY)], observations, [LOCATION])[0]
    later = feature_rows([row(DAY, decision=AT + timedelta(minutes=2))], observations, [LOCATION])[
        0
    ]
    assert values(earlier)["forecast_high_f"] == 70
    assert values(earlier)["revision_f"] is None
    assert values(earlier)["observed_temperature_f"] is None
    assert values(later)["forecast_high_f"] == 74
    assert values(later)["revision_f"] == 4
    assert values(later)["observed_temperature_f"] == 60


def test_uncertain_clocks_and_wrong_units_excluded() -> None:
    assumed = observation(DAY, 70, AT - timedelta(hours=1)).revalidated(timing_basis="assumed")
    celsius = observation(DAY, 20, AT - timedelta(hours=1)).revalidated(unit="degC")
    for o in (assumed, celsius):
        result = feature_rows([row(DAY)], [o], [LOCATION])[0]
        assert not result["feature_eligible"]
        assert values(result)["forecast_high_f"] is None


@pytest.mark.parametrize(("day", "hours"), [(date(2025, 3, 9), 23), (date(2025, 11, 2), 25)])
def test_hourly_maximum_requires_complete_local_day_including_dst(day: date, hours: int) -> None:
    start = datetime.combine(day, datetime.min.time(), ZoneInfo(LOCATION.timezone)).astimezone(UTC)
    before = start - timedelta(hours=3)
    observations = [
        observation(day, 50 + h, before).revalidated(
            variable="temperature_f", valid_at=start + timedelta(hours=h)
        )
        for h in range(hours)
    ]
    result = full_day_maxima(observations, location=LOCATION, target=day, decision=before)
    assert len(result) == 1
    assert result[0]["high_f"] == 50 + hours - 1
    assert full_day_maxima(observations[:-1], location=LOCATION, target=day, decision=before) == []


def test_bias_only_uses_frozen_prior_forecast_and_label_revision_known_now() -> None:
    days = [DAY + timedelta(days=n) for n in range(3)]
    rows = [row(day) for day in days]
    observations = [
        observation(day, 70, AT + timedelta(days=n, hours=-1)) for n, day in enumerate(days)
    ]
    observations.extend(
        [
            observation(
                DAY,
                72,
                AT + timedelta(hours=19),
                role="observation",
                source="weather-company",
                variable="settlement_high_f",
            ),
            observation(
                DAY,
                76,
                AT + timedelta(days=2, hours=-1),
                role="observation",
                source="weather-company",
                variable="settlement_high_f",
                revision="correction",
            ),
            # A subsequent forecast may not overwrite yesterday's frozen predictor.
            observation(DAY, 90, AT + timedelta(days=1), revision="after-event"),
        ]
    )
    results = feature_rows(rows, observations, [LOCATION])
    assert values(results[0])["station_bias_f"] is None
    assert values(results[1])["station_bias_f"] == 2
    assert values(results[2])["station_bias_f"] == 6
    assert "FIX-2025-02-01" in json.loads(results[2]["feature_evidence_json"])["bias_event_ids"]


def test_settlement_sources_not_interchangeable_or_fractional() -> None:
    forecast = observation(DAY, 70, AT - timedelta(hours=2))
    source = observation(
        DAY,
        72,
        AT + timedelta(days=1),
        role="observation",
        source="nws-cli",
        variable="settlement_high_f",
    )
    mismatched = feature_rows([row(DAY)], [forecast, source], [LOCATION])[0]
    assert mismatched["temperature_target_f"] is None
    twc = source.revalidated(source_id="weather-company")
    matched = feature_rows([row(DAY)], [forecast, twc], [LOCATION])[0]
    assert matched["temperature_target_f"] == 72
    fractional = feature_rows(
        [row(DAY)], [forecast, twc.revalidated(value=Decimal("72.2"))], [LOCATION]
    )[0]
    assert fractional["temperature_target_f"] is None


def test_future_rules_do_not_supply_a_deadline_and_missing_units_refused() -> None:
    forecast = observation(DAY, 70, AT - timedelta(hours=2))
    unknown = {**row(DAY), "rules_known_at_decision": False}
    result = feature_rows([unknown], [forecast], [LOCATION])[0]
    assert values(result)["hours_to_close"] is None
    assert not result["feature_eligible"]
    raw = row(DAY)
    rules = json.loads(raw["rules_json"])
    rules["rules_primary"] = "Temperature units not specified"
    raw["rules_json"] = json.dumps(rules)
    assert not feature_rows([raw], [forecast], [LOCATION])[0]["feature_eligible"]


def test_model_disagreement_and_ensemble_members_are_distinct_families() -> None:
    available = AT - timedelta(hours=1)
    observations = [
        observation(DAY, 70, available),
        observation(DAY, 74, available, source="fixture-nws"),
        observation(DAY, 60, available, source="fixture-ensemble", variable="ensemble_1"),
        observation(DAY, 80, available, source="fixture-ensemble", variable="ensemble_2"),
    ]
    start = datetime(2025, 2, 1, 5, tzinfo=UTC)
    observations = observations[:2] + [
        p.revalidated(valid_at=start + timedelta(hours=h))
        for p in observations[2:]
        for h in range(24)
    ]
    result = feature_rows([row(DAY)], observations, [LOCATION])[0]
    assert values(result)["ensemble_mean_f"] == 70
    assert values(result)["ensemble_std_f"] == 10
    assert values(result)["forecast_high_f"] == pytest.approx(214 / 3)
    assert values(result)["model_disagreement_f"] is not None


def test_fitting_uses_only_scalar_label_revision_known_at_fit_cutoff() -> None:
    from entropytrade.ml.experiment import _examples

    observations = [
        observation(DAY, 70, AT - timedelta(hours=1)),
        observation(
            DAY,
            72,
            AT + timedelta(hours=19),
            role="observation",
            source="weather-company",
            variable="settlement_high_f",
        ),
        observation(
            DAY,
            76,
            AT + timedelta(days=10),
            role="observation",
            source="weather-company",
            variable="settlement_high_f",
            revision="corrected",
        ),
    ]
    source_row = row(DAY)
    source_row["outcome_available_at"] = (AT + timedelta(days=12)).isoformat()
    rows = feature_rows([source_row], observations, [LOCATION])
    before = _examples(rows, (source_row["event_id"],), AT + timedelta(hours=18))
    initial = _examples(rows, (source_row["event_id"],), AT + timedelta(days=2))
    corrected = _examples(rows, (source_row["event_id"],), AT + timedelta(days=11))
    assert before == []
    assert initial[0].target_f == 72
    assert corrected[0].target_f == 76


def test_revision_clock_orders_vintages_even_when_original_availability_is_unchanged() -> None:
    old = observation(DAY, 70, AT - timedelta(hours=2), revision="z-old")
    revised = observation(DAY, 74, AT - timedelta(hours=2), revision="a-new").revalidated(
        revised_at=AT + timedelta(minutes=1)
    )
    earlier = feature_rows([row(DAY)], [old, revised], [LOCATION])[0]
    later = feature_rows(
        [row(DAY, decision=AT + timedelta(minutes=2))], [old, revised], [LOCATION]
    )[0]
    assert values(earlier)["forecast_high_f"] == 70
    assert values(later)["forecast_high_f"] == 74
    assert values(later)["revision_f"] == 4


def test_ambiguous_settlement_authorities_are_not_guessed() -> None:
    raw = row(DAY)
    rules = json.loads(raw["rules_json"])
    rules["settlement_sources"].append({"name": "National Weather Service"})
    raw["rules_json"] = json.dumps(rules)
    observations = [
        observation(DAY, 70, AT - timedelta(hours=1)),
        observation(
            DAY,
            72,
            AT + timedelta(days=1),
            role="observation",
            source="weather-company",
            variable="settlement_high_f",
        ),
    ]
    result = feature_rows([raw], observations, [LOCATION])[0]
    assert result["temperature_target_f"] is None
    assert not result["feature_eligible"]
