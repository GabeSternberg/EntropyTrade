"""Explicit mock research over registered family evidence; no provider or invented predictions."""

from decimal import Decimal
from uuid import UUID

from pydantic_ai.models.test import TestModel

from entropytrade.agents.evidence import ResearchEvidence
from entropytrade.agents.fixture import demo_specs
from entropytrade.agents.outputs import (
    CandidateBatch,
    CandidateVerdict,
    EvidenceNote,
    HypothesisBatch,
    ResearchCandidate,
    ResearchCritique,
    ResearchHypothesis,
)
from entropytrade.domain.strategy import (
    ComparisonOp,
    FeatureRequirement,
    MarketUniverse,
    Predicate,
    RuleSet,
)


def adapter_models(evidence: ResearchEvidence, run_id: str) -> tuple[TestModel, ...]:
    citations = tuple(c["evidence_id"] for c in evidence.calls[:3])
    family = evidence.markets[0]["series"] if evidence.markets else "UNAVAILABLE"
    variables = evidence.registered_names[:2]
    sources = tuple(evidence.coverage["configured_source_kinds"])
    hypotheses, candidates = [], []
    for i, name in enumerate(variables):
        mechanism = (
            f"Decision-time {name} may explain contract probability variation in {family}; "
            "this is a predeclared mock proposal, requiring independent temporal validation."
        )
        hypotheses.append(
            ResearchHypothesis(
                hypothesis_id=f"h{i}",
                mechanism=mechanism,
                market_family=family,
                window="Captured decision time before the actual contract close",
                variables=(name,),
                direction="Test a positive association; reject absent validation gain",
                test="Compare event-weighted validation Brier and log loss with fixed baselines.",
                falsification=(
                    "Reject without independent out-of-sample gain and certified execution data."
                ),
                necessary_evidence=(
                    "Repeated point-in-time captures across independent dates",
                    "Actual settlement-source outcomes, historical sized books and effective fees",
                ),
                evidence_ids=citations,
            )
        )
        spec = None
        if evidence.markets:
            spec = demo_specs()[0].revalidated(
                strategy_id=f"adapter-mock-{i}",
                name=f"{family} {name} research",
                description=mechanism,
                hypothesis=mechanism,
                market_universe=MarketUniverse(
                    series_tickers=(family,), description="Actual captured family only"
                ),
                features=(
                    FeatureRequirement(
                        name=name,
                        version=evidence.registered_versions[name],
                        description=mechanism,
                    ),
                ),
                required_sources=sources,
                entry_rules=RuleSet(
                    description="Bounded informational hypothesis",
                    all_of=(
                        Predicate(
                            feature="model_yes_probability",
                            op=ComparisonOp.GT,
                            threshold=Decimal("0.55"),
                        ),
                        Predicate(feature=name, op=ComparisonOp.GT, threshold=Decimal(0)),
                    ),
                ),
                model_kind="domain_statistical",
                generation_run_id=UUID(run_id),
            )
        candidates.append(
            ResearchCandidate(
                candidate_id=f"c{i}",
                hypothesis_id=f"h{i}",
                spec=spec,
                missing_capability="No listed contracts were captured" if spec is None else "",
                required_features=(name,),
                required_sources=sources,
                model_family="forward_only",
                evidence_ids=citations,
            )
        )
    note = EvidenceNote(
        market_understanding=(
            "Forward public capture is evidence of availability now; history is unproven."
        ),
        mechanisms=tuple(h.mechanism for h in hypotheses),
        limitations=(
            "Mock reasoning; no fitted probability model or historical performance claim.",
        ),
        evidence_ids=citations,
    )
    critique = ResearchCritique(
        verdicts=tuple(
            CandidateVerdict(
                candidate_id=c.candidate_id,
                accept_for_experiment=True,
                reason=(
                    "Research proposal only; deterministic evidence gates "
                    "must refuse missing history."
                ),
                concerns=(
                    "Independent date blocks, source-matched outcomes "
                    "and execution evidence are missing.",
                ),
            )
            for c in candidates
        )
    )
    outputs = (
        note,
        HypothesisBatch(hypotheses=tuple(hypotheses)),
        CandidateBatch(candidates=tuple(candidates)),
        critique,
    )
    return tuple(
        TestModel(
            custom_output_args=output.model_dump(mode="json"),
            call_tools=["inspect_evidence"] if i == 0 else [],
        )
        for i, output in enumerate(outputs)
    )
