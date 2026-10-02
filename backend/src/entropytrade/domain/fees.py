"""Identity of a fee schedule. The calculator is a later phase (spec section 36).

Kalshi fees differ by series (``fee_type``, ``fee_multiplier``) and can include maker fees.
A backtest records which schedule it used; nothing here hard-codes a formula.
"""

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import FeeType
from entropytrade.domain.numeric import ExactDecimal
from entropytrade.domain.time import UtcDatetime


class FeeModelRef(DomainModel):
    version: str = Field(min_length=1)
    fee_type: FeeType
    fee_multiplier: ExactDecimal
    maker_pays: bool
    effective_from: UtcDatetime
    notes: str = ""
