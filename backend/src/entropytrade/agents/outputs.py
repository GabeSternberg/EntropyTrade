"""Typed notes the research agents return. None of these is an order."""

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.strategy import StrategySpec


class ResearchNote(DomainModel):
    summary: str = Field(min_length=20)
    uncertainties: tuple[str, ...] = Field(min_length=1)
    suggested_sources: tuple[str, ...] = Field(min_length=1)


class HypothesisDraft(DomainModel):
    statement: str = Field(min_length=20)


class QuantBatch(DomainModel):
    specs: tuple[StrategySpec, ...] = Field(min_length=1)


class SpecJudgement(DomainModel):
    strategy_id: str = Field(min_length=1)
    accept: bool
    reason: str = Field(min_length=1)


class CriticBatch(DomainModel):
    judgements: tuple[SpecJudgement, ...] = Field(min_length=1)
