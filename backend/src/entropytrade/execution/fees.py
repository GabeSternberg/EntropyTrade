"""Series fee schedule. The quadratic coefficient is an input, not a built-in constant.

Makers pay only when the schedule says so. KXHIGH's quadratic schedule does not, so a
maker fill on that series is zero regardless of the coefficient the caller passes for takers.
"""

from decimal import ROUND_CEILING, Decimal

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import FeeType, LiquidityRole
from entropytrade.domain.numeric import MONEY_QUANTUM, ONE, ZERO, ExactDecimal, parse_money


class FeeFormulaError(ValueError):
    """This schedule has no implemented formula. The caller must supply the fee."""


class FeeSchedule(DomainModel):
    """One series fee schedule. ``quadratic_coefficient`` comes from that schedule's text."""

    fee_type: FeeType
    fee_multiplier: ExactDecimal
    maker_pays: bool
    quadratic_coefficient: ExactDecimal


_CENT = Decimal("0.01")


def trade_fee(
    schedule: FeeSchedule,
    *,
    yes_price: Decimal,
    quantity: Decimal,
    role: LiquidityRole,
) -> Decimal:
    """Fee for one fill. ``yes_price * (1 - yes_price)`` is the same on both legs."""
    if role is LiquidityRole.MAKER and not schedule.maker_pays:
        return parse_money(ZERO)
    if schedule.fee_type is FeeType.FLAT:
        raise FeeFormulaError("flat series fees are not computed from a hidden formula")
    raw = (
        schedule.quadratic_coefficient
        * schedule.fee_multiplier
        * quantity
        * yes_price
        * (ONE - yes_price)
    )
    cents = raw.quantize(_CENT, rounding=ROUND_CEILING)
    return cents.quantize(MONEY_QUANTUM)
