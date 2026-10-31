"""Shared point-in-time fee policy; certification requires separate retained evidence."""

from pydantic import model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.enums import FeeType
from entropytrade.domain.ids import ContentHash
from entropytrade.domain.time import UtcDatetime
from entropytrade.execution.fees import FeeSchedule


class FeePolicy(DomainModel):
    schedule: FeeSchedule
    version: str
    available_at: UtcDatetime
    effective_from: UtcDatetime
    effective_to: UtcDatetime | None = None
    evidence: str
    evidence_hash: ContentHash | None = None
    certified: bool = False

    @model_validator(mode="after")
    def supported_schedule(self) -> "FeePolicy":
        if self.schedule.fee_type is not FeeType.QUADRATIC:
            raise ValueError("fee formula unsupported; no hidden flat fee approximation")
        if (
            self.schedule.quadratic_coefficient < 0
            or self.schedule.fee_multiplier < 0
            or self.schedule.maker_fraction < 0
        ):
            raise ValueError("fee coefficients must be nonnegative")
        return self
