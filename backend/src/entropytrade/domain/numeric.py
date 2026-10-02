"""Exact fixed-point numeric types for prices, money, quantities and probabilities.

All values are :class:`decimal.Decimal` on a fixed grid that mirrors Kalshi's wire formats:

* prices are fixed-point dollars with 4 decimal places (``"0.5600"``; sub-penny ticks are
  enabled per market, the tradable grid is given by the market's ``price_ranges``),
* contract counts are fixed-point with 2 decimal places (``"10.00"``; fractional trading is
  enabled per market),
* money (fees, balances, P&L) has 6 decimal places, the exchange's fee granularity.

Because ``price (4 dp) x quantity (2 dp)`` lands exactly on the 6 dp money grid, notional values
are always exact. Floats and bools are rejected outright: a float cannot reach a money field.
"""

from decimal import Decimal, InvalidOperation
from typing import Annotated, Final

from pydantic import BeforeValidator

from entropytrade.domain.enums import OutcomeSide

PRICE_PLACES: Final = 4
QUANTITY_PLACES: Final = 2
MONEY_PLACES: Final = 6

PRICE_QUANTUM: Final = Decimal(1).scaleb(-PRICE_PLACES)
QUANTITY_QUANTUM: Final = Decimal(1).scaleb(-QUANTITY_PLACES)
MONEY_QUANTUM: Final = Decimal(1).scaleb(-MONEY_PLACES)

ZERO: Final = Decimal(0)
ONE: Final = Decimal(1)


def to_decimal(value: object) -> Decimal:
    """Convert ``value`` to a finite Decimal. Accepts ``Decimal``, ``int`` and ``str`` only."""
    if isinstance(value, bool | float):
        raise ValueError(
            f"{type(value).__name__} is not accepted for exact numeric fields; "
            "pass a str, int or Decimal"
        )
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"not a decimal number: {value!r}") from exc
    else:
        raise ValueError(f"unsupported numeric type: {type(value).__name__}")
    if not result.is_finite():
        raise ValueError("NaN and infinity are not allowed")
    return result


def _on_grid(value: Decimal, quantum: Decimal, what: str) -> Decimal:
    quantized = value.quantize(quantum)
    if quantized != value:
        raise ValueError(f"{what} {value} has more precision than the {quantum} grid")
    return quantized


def parse_price(value: object) -> Decimal:
    """A price in dollars per contract: ``0 <= p <= 1`` on the 4 dp grid."""
    price = _on_grid(to_decimal(value), PRICE_QUANTUM, "price")
    if not ZERO <= price <= ONE:
        raise ValueError(f"price {price} must be between 0 and 1")
    return price


def parse_order_price(value: object) -> Decimal:
    """A limit price for an order: strictly between 0 and 1."""
    price = parse_price(value)
    if price in (ZERO, ONE):
        raise ValueError("an order price must be strictly between 0 and 1")
    return price


def parse_quantity(value: object) -> Decimal:
    """A non-negative contract count on the 2 dp grid."""
    quantity = _on_grid(to_decimal(value), QUANTITY_QUANTUM, "quantity")
    if quantity < ZERO:
        raise ValueError("quantity cannot be negative")
    return quantity


def parse_positive_quantity(value: object) -> Decimal:
    quantity = parse_quantity(value)
    if quantity == ZERO:
        raise ValueError("quantity must be positive")
    return quantity


def parse_money(value: object) -> Decimal:
    """A signed dollar amount on the 6 dp grid."""
    return _on_grid(to_decimal(value), MONEY_QUANTUM, "money")


def parse_non_negative_money(value: object) -> Decimal:
    money = parse_money(value)
    if money < ZERO:
        raise ValueError("amount cannot be negative")
    return money


def parse_probability(value: object) -> Decimal:
    """A probability in ``[0, 1]``. No grid: probabilities come from models, not the exchange."""
    probability = to_decimal(value)
    if not ZERO <= probability <= ONE:
        raise ValueError(f"probability {probability} must be between 0 and 1")
    return probability


def parse_exact_decimal(value: object) -> Decimal:
    """Any finite Decimal (no float input). For thresholds, feature values and parameters."""
    return to_decimal(value)


Price = Annotated[Decimal, BeforeValidator(parse_price)]
OrderPrice = Annotated[Decimal, BeforeValidator(parse_order_price)]
Quantity = Annotated[Decimal, BeforeValidator(parse_quantity)]
PositiveQuantity = Annotated[Decimal, BeforeValidator(parse_positive_quantity)]
Money = Annotated[Decimal, BeforeValidator(parse_money)]
NonNegativeMoney = Annotated[Decimal, BeforeValidator(parse_non_negative_money)]
Probability = Annotated[Decimal, BeforeValidator(parse_probability)]
ExactDecimal = Annotated[Decimal, BeforeValidator(parse_exact_decimal)]


def complement(price: Decimal) -> Decimal:
    """The opposite leg's price: a YES bid at ``p`` is a NO ask at ``1 - p``."""
    return parse_price(ONE - parse_price(price))


def cost_per_contract(side: OutcomeSide, yes_price: Decimal) -> Decimal:
    """Dollars paid per contract to be long ``side`` at a YES-denominated price."""
    price = parse_price(yes_price)
    return price if side is OutcomeSide.YES else complement(price)


def notional(price: Decimal, quantity: Decimal) -> Decimal:
    """Exact ``price x quantity`` on the money grid."""
    product = parse_price(price) * parse_quantity(quantity)
    return _on_grid(product, MONEY_QUANTUM, "notional")


def canonical_decimal_str(value: Decimal) -> str:
    """Scale-independent string form: ``Decimal('0.50')`` and ``Decimal('0.5')`` -> ``'0.5'``."""
    if value == ZERO:
        return "0"
    return format(value.normalize(), "f")
