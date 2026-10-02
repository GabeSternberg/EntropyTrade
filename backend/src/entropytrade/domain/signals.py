"""Predictions, edges and signals (spec sections 12 and 28).

Prediction is not trading. :class:`EdgeEstimate` keeps the model probability, the executable
price and every cost reserve separate, so "70% vs a 69c ask" is visibly worthless after costs.
"""

from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import Field, computed_field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.ids import ContentHash, new_id
from entropytrade.domain.market import Contract
from entropytrade.domain.numeric import ExactDecimal, NonNegativeMoney, Price, Probability
from entropytrade.domain.time import UtcDatetime


class EdgeEstimate(DomainModel):
    """Per-contract expected value of buying one contract of a given outcome.

    ``outcome_probability`` is the probability that the purchased contract pays $1 and
    ``price_per_contract`` is what it costs to buy it at an executable price (an ask, or a
    depth-walked average), never a midpoint or last trade.
    """

    outcome_probability: Probability
    price_per_contract: Price
    fee_per_contract: NonNegativeMoney
    expected_slippage: NonNegativeMoney = Decimal(0)
    latency_cost: NonNegativeMoney = Decimal(0)
    fill_uncertainty_reserve: NonNegativeMoney = Decimal(0)
    model_uncertainty_reserve: NonNegativeMoney = Decimal(0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def raw_edge(self) -> Decimal:
        return self.outcome_probability - self.price_per_contract

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_costs(self) -> Decimal:
        return (
            self.fee_per_contract
            + self.expected_slippage
            + self.latency_cost
            + self.fill_uncertainty_reserve
            + self.model_uncertainty_reserve
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def net_edge(self) -> Decimal:
        return self.raw_edge - self.total_costs


class PredictionRecord(DomainModel):
    """Everything needed to answer "why did the model believe this, at that moment?"."""

    prediction_id: UUID = Field(default_factory=new_id)
    strategy_id: str = Field(min_length=1)
    strategy_version: int = Field(ge=1)
    model_version: str = Field(min_length=1)
    calibration_version: str | None = None
    market_ticker: str = Field(min_length=1)
    decision_time: UtcDatetime
    feature_vector_hash: ContentHash
    source_data_manifest_hash: ContentHash
    probability_yes: Probability
    uncertainty: Probability | None = None
    market_yes_bid: Price | None = None
    market_yes_ask: Price | None = None
    net_edge_estimate: ExactDecimal | None = None


class Signal(DomainModel):
    """A strategy's desire to hold a contract, before sizing, portfolio netting and risk."""

    signal_id: UUID = Field(default_factory=new_id)
    strategy_id: str = Field(min_length=1)
    strategy_version: int = Field(ge=1)
    contract: Contract
    decision_time: UtcDatetime
    edge: EdgeEstimate
    prediction_id: UUID | None = None
    rationale: str = ""

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.rationale and self.prediction_id is None:
            raise ValueError("a signal needs a prediction_id or a rationale for the audit trail")
        return self
