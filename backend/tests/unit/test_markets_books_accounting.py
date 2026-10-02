"""Strikes, rules identity, books, positions and settlement payouts."""

from decimal import Decimal

import pytest

from entropytrade.domain.enums import (
    FeeType,
    MarketResult,
    MarketStatus,
    MarketType,
    OutcomeSide,
    StrikeType,
)
from entropytrade.domain.market import (
    Contract,
    Market,
    MarketRules,
    PriceRange,
    Series,
    SettlementSource,
    Strike,
    TickSchedule,
)
from entropytrade.domain.market_data import OrderBook, OrderBookLevel
from entropytrade.domain.numeric import notional
from entropytrade.domain.portfolio import (
    Position,
    Settlement,
    settlement_value_for,
)
from tests.support import utc


def _level(price: str, quantity: str = "5.00") -> OrderBookLevel:
    return OrderBookLevel(price=Decimal(price), quantity=Decimal(quantity))


def test_kalshi_temperature_strike_semantics() -> None:
    """KXHIGHPHIL wording (2026-10-02): greater 89 is above 89, less 82 is below 82."""
    above = Strike(strike_type=StrikeType.GREATER, floor=Decimal(89))
    below = Strike(strike_type=StrikeType.LESS, cap=Decimal(82))
    bracket = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(88), cap=Decimal(89))
    assert above.resolves_yes(Decimal(90))
    assert not above.resolves_yes(Decimal(89))
    assert below.resolves_yes(Decimal(81))
    assert not below.resolves_yes(Decimal(82))
    assert bracket.resolves_yes(Decimal(88))
    assert bracket.resolves_yes(Decimal(89))
    assert not bracket.resolves_yes(Decimal(87))
    assert not bracket.resolves_yes(Decimal(90))


def test_strike_shape_is_checked() -> None:
    with pytest.raises(ValueError, match="floor"):
        Strike(strike_type=StrikeType.GREATER, cap=Decimal(1))
    with pytest.raises(ValueError, match="floor must not exceed"):
        Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(3), cap=Decimal(2))
    functional = Strike(strike_type=StrikeType.FUNCTIONAL)
    assert not functional.is_evaluable
    with pytest.raises(ValueError, match="cannot be evaluated"):
        functional.resolves_yes(Decimal(1))


def test_rules_hash_changes_with_the_text_and_not_the_capture_time() -> None:
    first = MarketRules(
        market_ticker="KXHIGHPHIL-26OCT02-T89",
        rules_primary="Settles on The Weather Company.",
        settlement_sources=(SettlementSource(name="The Weather Company"),),
        captured_at=utc(2026, 10, 1),
    )
    later = first.revalidated(captured_at=utc(2026, 10, 2))
    changed = first.revalidated(rules_primary="Settles on the NWS Daily Climate Report.")
    assert later.rules_hash == first.rules_hash
    assert changed.rules_hash != first.rules_hash


def test_market_rejects_inconsistent_lifecycle() -> None:
    rules = MarketRules(
        market_ticker="M",
        rules_primary="Rules.",
        captured_at=utc(2026, 1, 1),
    )
    schedule = TickSchedule(
        ranges=(PriceRange(start=Decimal(0), end=Decimal(1), step=Decimal("0.01")),)
    )
    common = {
        "ticker": "M",
        "event_ticker": "E",
        "market_type": MarketType.BINARY,
        "title": "Example",
        "open_time": utc(2026, 1, 1),
        "close_time": utc(2026, 1, 2),
        "rules": rules,
        "tick_schedule": schedule,
    }
    Market.model_validate({**common, "status": MarketStatus.ACTIVE})
    with pytest.raises(ValueError, match="result"):
        Market.model_validate({**common, "status": MarketStatus.ACTIVE, "result": MarketResult.YES})
    with pytest.raises(ValueError, match="finalized"):
        Market.model_validate({**common, "status": MarketStatus.FINALIZED})
    settled = Market.model_validate(
        {
            **common,
            "status": MarketStatus.FINALIZED,
            "result": MarketResult.YES,
            "settlement_value": Decimal(1),
            "settlement_ts": utc(2026, 1, 3),
        }
    )
    assert settled.contract(OutcomeSide.NO).side is OutcomeSide.NO


def test_series_carries_its_fee_schedule() -> None:
    series = Series(
        ticker="KXHIGHPHIL",
        title="Highest temperature in Philadelphia",
        fee_type=FeeType.QUADRATIC,
        fee_multiplier=Decimal(1),
    )
    assert series.fee_type is FeeType.QUADRATIC


def test_book_converts_no_bids_onto_the_yes_scale() -> None:
    book = OrderBook.from_yes_and_no_bids(
        "M",
        yes_bids=(_level("0.40"), _level("0.39")),
        no_bids=(_level("0.55"),),
        received_at=utc(2026, 10, 2, 15),
    )
    assert book.best_bid is not None
    assert book.best_bid.price == Decimal("0.40")
    assert book.best_ask is not None
    assert book.best_ask.price == Decimal("0.45")
    assert book.no_bids()[0].price == Decimal("0.55")
    assert book.best_price_to_buy(OutcomeSide.YES) == Decimal("0.45")
    assert book.best_price_to_buy(OutcomeSide.NO) == Decimal("0.60")
    assert not book.is_crossed


def test_crossed_book_is_flagged_and_unsorted_books_are_rejected() -> None:
    book = OrderBook.from_yes_and_no_bids(
        "M",
        yes_bids=(_level("0.60"),),
        no_bids=(_level("0.50"),),
        received_at=utc(2026, 10, 2, 15),
    )
    assert book.is_crossed
    with pytest.raises(ValueError, match="descending"):
        OrderBook(
            market_ticker="M",
            bids=(_level("0.40"), _level("0.41")),
            received_at=utc(2026, 10, 2, 15),
        )


def test_position_cost_cannot_exceed_a_dollar_per_contract() -> None:
    contract = Contract(market_ticker="M", side=OutcomeSide.YES)
    Position(
        contract=contract,
        quantity=Decimal("2.00"),
        total_cost=Decimal("1.50"),
        as_of=utc(2026, 1, 1),
    )
    with pytest.raises(ValueError, match="cost basis"):
        Position(
            contract=contract,
            quantity=Decimal("2.00"),
            total_cost=Decimal("2.01"),
            as_of=utc(2026, 1, 1),
        )


def test_settlement_payout_matches_the_result() -> None:
    assert settlement_value_for(MarketResult.YES) == Decimal(1)
    assert settlement_value_for(MarketResult.NO) == Decimal(0)
    settlement = Settlement(
        market_ticker="M",
        result=MarketResult.YES,
        yes_value=Decimal(1),
        yes_quantity=Decimal("2.00"),
        no_quantity=Decimal("3.00"),
        revenue=Decimal("2.000000"),
        settled_at=utc(2026, 1, 2),
    )
    assert settlement.revenue == notional(Decimal(1), Decimal("2.00"))
    with pytest.raises(ValueError, match="revenue"):
        Settlement(
            market_ticker="M",
            result=MarketResult.NO,
            yes_value=Decimal(0),
            yes_quantity=Decimal("1.00"),
            revenue=Decimal("1.000000"),
            settled_at=utc(2026, 1, 2),
        )
