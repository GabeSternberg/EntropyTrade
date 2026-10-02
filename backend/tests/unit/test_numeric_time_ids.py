"""Exact numbers, UTC time and content hashes."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from entropytrade.domain.enums import OutcomeSide
from entropytrade.domain.ids import canonical_json, content_hash
from entropytrade.domain.numeric import (
    MONEY_QUANTUM,
    complement,
    cost_per_contract,
    notional,
    parse_money,
    parse_order_price,
    parse_price,
    parse_probability,
    parse_quantity,
)
from entropytrade.domain.time import SimulatedClock, ensure_utc
from tests.support import utc


def test_floats_and_bools_never_enter_money() -> None:
    for parser in (parse_price, parse_quantity, parse_money, parse_probability):
        with pytest.raises(ValueError, match="float"):
            parser(0.5)
        with pytest.raises(ValueError, match="bool"):
            parser(True)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "nope", ""])
def test_non_finite_and_garbage_rejected(value: str) -> None:
    with pytest.raises(ValueError, match=r"not a decimal|NaN and infinity"):
        parse_price(value)


def test_price_grid_and_bounds() -> None:
    assert parse_price("0.5600") == Decimal("0.56")
    assert parse_price(0) == Decimal(0)
    assert parse_price(1) == Decimal(1)
    with pytest.raises(ValueError, match="grid"):
        parse_price("0.56001")
    with pytest.raises(ValueError, match="between"):
        parse_price("-0.01")
    with pytest.raises(ValueError, match="between"):
        parse_price("1.0001")


def test_order_price_excludes_the_endpoints() -> None:
    with pytest.raises(ValueError, match="strictly"):
        parse_order_price(0)
    with pytest.raises(ValueError, match="strictly"):
        parse_order_price(1)
    assert parse_order_price("0.0100") == Decimal("0.01")


def test_quantity_and_money_signs() -> None:
    assert parse_quantity("10.50") == Decimal("10.50")
    with pytest.raises(ValueError, match="negative"):
        parse_quantity("-1")
    with pytest.raises(ValueError, match="grid"):
        parse_quantity("1.001")
    assert parse_money("-1.25") == Decimal("-1.25")
    with pytest.raises(ValueError, match="grid"):
        parse_money("0.0000001")


def test_complement_and_cost() -> None:
    assert complement(Decimal("0.30")) == Decimal("0.70")
    assert cost_per_contract(OutcomeSide.YES, Decimal("0.30")) == Decimal("0.30")
    assert cost_per_contract(OutcomeSide.NO, Decimal("0.30")) == Decimal("0.70")


def test_notional_lands_on_the_fee_grid() -> None:
    assert notional(Decimal("0.3333"), Decimal("1.50")) == Decimal("0.499950")
    assert notional(Decimal("0.3333"), Decimal("1.50")).quantize(MONEY_QUANTUM) == Decimal(
        "0.499950"
    )


def test_naive_datetimes_are_rejected_and_offsets_become_utc() -> None:
    with pytest.raises(ValueError, match="naive"):
        ensure_utc(datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001
    eastern = timezone(timedelta(hours=-5))
    converted = ensure_utc(datetime(2026, 1, 1, 12, 0, tzinfo=eastern))
    assert converted == datetime(2026, 1, 1, 17, 0, tzinfo=UTC)
    assert converted.tzinfo is UTC


def test_simulated_clock_only_moves_forward() -> None:
    clock = SimulatedClock(utc(2026, 1, 1))
    assert clock.advance(timedelta(hours=1)) == utc(2026, 1, 1, 1)
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(timedelta(seconds=-1))
    with pytest.raises(ValueError, match="backwards"):
        clock.advance_to(utc(2025, 12, 31))


def test_content_hash_ignores_key_order_and_decimal_scale() -> None:
    first = content_hash({"b": Decimal("0.50"), "a": 1})
    second = content_hash({"a": 1, "b": Decimal("0.5")})
    assert first == second
    assert first.startswith("sha256:")
    assert canonical_json({"when": utc(2026, 1, 1)}) == '{"when":"2026-01-01T00:00:00+00:00"}'
    with pytest.raises(TypeError, match="float"):
        content_hash({"x": 0.1})
