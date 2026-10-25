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


# Operational research output schemas. The original demo schemas remain compatible.
class EvidenceNote(DomainModel):
    market_understanding: str = Field(min_length=20, max_length=4000)
    mechanisms: tuple[str, ...] = Field(min_length=1, max_length=8)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=12)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class ResearchHypothesis(DomainModel):
    hypothesis_id: str = Field(min_length=1, max_length=100)
    mechanism: str = Field(min_length=20, max_length=1500)
    market_family: str = Field(min_length=1, max_length=100)
    window: str = Field(min_length=1, max_length=500)
    variables: tuple[str, ...] = Field(min_length=1, max_length=12)
    direction: str = Field(min_length=1, max_length=500)
    test: str = Field(min_length=20, max_length=1500)
    falsification: str = Field(min_length=20, max_length=1500)
    necessary_evidence: tuple[str, ...] = Field(min_length=1, max_length=10)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class HypothesisBatch(DomainModel):
    hypotheses: tuple[ResearchHypothesis, ...] = Field(min_length=2, max_length=6)


class ResearchCandidate(DomainModel):
    candidate_id: str = Field(min_length=1, max_length=100)
    hypothesis_id: str = Field(min_length=1, max_length=100)
    spec: StrategySpec | None = None
    missing_capability: str = Field(default="", max_length=1500)
    required_features: tuple[str, ...] = Field(min_length=1, max_length=12)
    required_sources: tuple[str, ...] = Field(min_length=1, max_length=12)
    model_family: str = Field(default="none", max_length=100)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class CandidateBatch(DomainModel):
    candidates: tuple[ResearchCandidate, ...] = Field(min_length=2, max_length=8)


class CandidateVerdict(DomainModel):
    candidate_id: str = Field(min_length=1, max_length=100)
    accept_for_experiment: bool
    reason: str = Field(min_length=20, max_length=2500)
    concerns: tuple[str, ...] = Field(min_length=1, max_length=12)


class ResearchCritique(DomainModel):
    verdicts: tuple[CandidateVerdict, ...] = Field(min_length=1, max_length=8)
