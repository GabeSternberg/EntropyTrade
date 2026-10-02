"""Pre-registered rules. Thresholds stay put after the score is known."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.observations import Forecast
from entropytrade.exchange.trade_prints import TradePrint
from entropytrade.weather.cli_observations import CliLabel
from entropytrade.weather.informational_rules import (
    BRACKET_CAP,
    BRACKET_FLOOR,
    MIDPOINT,
    PRICE_THRESHOLD,
    load_rule_scores,
    score_rules,
)

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_the_thresholds_are_the_pre_registered_ones() -> None:
    assert Decimal(80) == BRACKET_FLOOR
    assert Decimal(81) == BRACKET_CAP
    assert Decimal("80.5") == MIDPOINT
    assert Decimal("0.4000") == PRICE_THRESHOLD


def test_a_no_rule_uses_a_rich_yes_print_and_a_yes_rule_does_not() -> None:
    valid_on = date(2026, 8, 25)
    label = CliLabel(
        available_at=datetime(2026, 8, 26, 8, tzinfo=UTC),
        source="test",
        endpoint="test",
        valid_on=valid_on,
        high_f=Decimal(86),
        header="KPHI 260800",
    )
    forecast = _forecast(Decimal(85))
    printed = _print(created=datetime(2026, 8, 25, 14, tzinfo=UTC), price="0.9000")
    scored = {item.name: item for item in score_rules((label,), {valid_on: forecast}, (printed,))}
    above = scored["forecast_above"]
    assert above.tried is True
    assert above.promoted is False
    assert above.fires == 1
    assert above.claim_hits == 1
    optimistic, base, conservative = above.scenarios
    assert optimistic.assumed_fills == 1
    assert optimistic.equity == Decimal("100.900000")
    assert optimistic.guaranteed_fill is False
    assert optimistic.fidelity == "trade-print"
    assert base.assumed_fills == 0
    assert base.equity == Decimal("100.000000")
    assert conservative.assumed_fills == 0
    gap = scored["forecast_gap"]
    assert gap.fires == 1
    assert gap.scenarios[0].assumed_fills == 0
    assert scored["forecast_inside"].fires == 0
    assert scored["forecast_below"].fires == 0


def test_stored_rules_are_tried_and_not_promoted() -> None:
    scored = {item.name: item for item in load_rule_scores(ROOT)}
    assert set(scored) == {
        "forecast_inside",
        "forecast_above",
        "forecast_below",
        "forecast_gap",
    }
    for rule in scored.values():
        assert rule.tried is True
        assert rule.promoted is False
        assert rule.scenarios[1].assumed_fills == 0
        assert rule.scenarios[1].equity == Decimal("100.000000")
        assert rule.scenarios[2].assumed_fills == 0
        assert rule.scenarios[2].guaranteed_fill is False
    assert scored["forecast_inside"].fires == 0
    assert scored["forecast_inside"].scenarios[0].assumed_fills == 0
    assert scored["forecast_above"].fires == 19
    assert scored["forecast_above"].claim_hits == 17
    assert scored["forecast_above"].scenarios[0].assumed_fills == 0
    assert scored["forecast_below"].fires == 21
    assert scored["forecast_below"].claim_hits == 14
    assert scored["forecast_below"].scenarios[0].assumed_fills == 0
    gap = scored["forecast_gap"]
    assert gap.fires == 19
    assert gap.claim_hits == 1
    assert gap.scenarios[0].assumed_fills == 3
    assert gap.scenarios[0].equity == Decimal("99.900000")
    assert gap.scenarios[0].guaranteed_fill is False


def _forecast(value: Decimal) -> Forecast:
    run = datetime(2026, 8, 24, 6, tzinfo=UTC)
    return Forecast(
        source_id="open-meteo",
        event_time=run,
        available_at=run,
        ingested_at=run,
        provider="open-meteo",
        model="gfs",
        run_time=run,
        location_id="CLIPHL",
        variable="temperature_2m_max",
        valid_from=datetime(2026, 8, 25, tzinfo=UTC),
        valid_to=datetime(2026, 8, 26, tzinfo=UTC),
        value=value,
        unit="F",
    )


def _print(*, created: datetime, price: str) -> TradePrint:
    return TradePrint(
        trade_id="synthetic",
        ticker="KXHIGHPHIL-26AUG25-B80.5",
        created_at=created,
        fetched_at=created + timedelta(days=30),
        endpoint="https://example.test/markets/trades",
        yes_price=Decimal(price),
        count=Decimal("5.00"),
    )
