"""A coherent distribution over integer reported Fahrenheit daily highs.

This is a model of the reported integer, not an undocumented assertion about how a
provider rounds physical temperature. Unsupported units/functional strikes are refused.
"""

import math
from collections.abc import Callable
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike


def normal_cdf(value: float) -> float:
    return (1 + math.erf(value / math.sqrt(2))) / 2


def contract_probability(
    strike: Strike, cdf: Callable[[float], float], *, unit: str = "degF"
) -> float:
    if unit != "degF":
        raise ValueError("model contract unit must be explicitly verified Fahrenheit")
    floor, cap = strike.floor, strike.cap
    lower: int | None = None
    upper: int | None = None
    if strike.strike_type is StrikeType.GREATER and floor is not None:
        lower = int(floor.to_integral_value(rounding=ROUND_FLOOR)) + 1
    elif strike.strike_type is StrikeType.GREATER_OR_EQUAL and floor is not None:
        lower = int(floor.to_integral_value(rounding=ROUND_CEILING))
    elif strike.strike_type is StrikeType.LESS and cap is not None:
        upper = int(cap.to_integral_value(rounding=ROUND_CEILING)) - 1
    elif strike.strike_type is StrikeType.LESS_OR_EQUAL and cap is not None:
        upper = int(cap.to_integral_value(rounding=ROUND_FLOOR))
    elif strike.strike_type is StrikeType.BETWEEN and floor is not None and cap is not None:
        lower = int(floor.to_integral_value(rounding=ROUND_CEILING))
        upper = int(cap.to_integral_value(rounding=ROUND_FLOOR))
    else:
        raise ValueError("unsupported contract payout semantics")
    if lower is not None and upper is not None and lower > upper:
        return 0.0
    lo = 0.0 if lower is None else cdf(lower - 0.5)
    hi = 1.0 if upper is None else cdf(upper + 0.5)
    if not (math.isfinite(lo) and math.isfinite(hi) and -1e-12 <= lo <= hi + 1e-12 <= 1 + 2e-12):
        raise ValueError("invalid or nonmonotone forecast CDF")
    return max(0.0, min(1.0, hi - lo))


def strike_from_json(text: str) -> Strike:
    return Strike.model_validate_json(text)


def exact_probability(value: float) -> Decimal:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("probability out of bounds")
    return Decimal(str(value))
