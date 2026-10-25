"""Bounded local formulation, not language-model reasoning or generated executable code.

Recognize documented signal words and literal feature comparisons. Preserve the complete
idea in research lineage; unsupported requests remain proposals with no executable spec.
"""

import re
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from entropytrade.agents.outputs import (
    CandidateBatch,
    CandidateVerdict,
    EvidenceNote,
    HypothesisBatch,
    ResearchCandidate,
    ResearchCritique,
    ResearchHypothesis,
)
from entropytrade.domain.enums import ActorKind, StrategyFamily, TimeInForce
from entropytrade.domain.lifecycle import Actor
from entropytrade.domain.strategy import (
    ComparisonOp,
    ExecutionPreferences,
    FeatureRequirement,
    MarketUniverse,
    ModelKind,
    PositionSizing,
    Predicate,
    RuleSet,
    SizingMethod,
    StrategySpec,
)
from entropytrade.domain.time import utc_now

if TYPE_CHECKING:
    from entropytrade.agents.evidence import ResearchEvidence

ALIASES = (
    (r"\brevision|\brevis", "revision_f"),
    (r"\bdisagreement|\bdispersion", "model_disagreement_f"),
    (r"\bbias", "station_bias_f"),
    (r"\bbitcoin|\bbtc|\bspot", "spot_minus_floor_usd"),
    (r"\bforecast|\btemperature|\bweather", "forecast_high_f"),
)
# Consume the entire non-whitespace token before validating the bounded decimal grammar.
# A prefix match could silently change 1.2345678, 1.2e3 or 1,000 into another threshold.
COMPARISON = re.compile(r"\b([a-z][a-z0-9_]*)\s*(>=|<=|>|<|==)\s*(\S+)")
DECIMAL_TOKEN = re.compile(r"-?[0-9]+(?:\.[0-9]{1,6})?")
OPS = {
    ">": ComparisonOp.GT,
    ">=": ComparisonOp.GE,
    "<": ComparisonOp.LT,
    "<=": ComparisonOp.LE,
    "==": ComparisonOp.EQ,
}
CONJUNCTION_GRAMMAR = (
    "Use a complete conjunction: [Test|Research] feature OP decimal "
    "[and feature OP decimal ...]; other connectors, grouping and surrounding prose "
    "are unsupported"
)


def parse_conjunction(text: str) -> tuple[Predicate, ...]:
    """Consume the entire expression, never infer AND from extracted comparisons.

    Only the optional documented introductory verb and whitespace-delimited ``and``
    are accepted outside a comparison. Numeric tokens are validated whole before any
    Decimal is constructed, including when a token contains punctuation or an operator.
    """
    expression = re.sub(r"^(?:test|research)\s+", "", text.strip().casefold(), count=1)
    predicates = []
    position = 0
    while True:
        match = COMPARISON.match(expression, position)
        if match is None:
            raise ValueError(CONJUNCTION_GRAMMAR)
        if DECIMAL_TOKEN.fullmatch(match[3]) is None:
            raise ValueError(
                "Use complete plain decimal tokens with at most six fractional digits; "
                "scientific notation, separators and suffixes are unsupported"
            )
        predicates.append(
            Predicate(feature=match[1], op=OPS[match[2]], threshold=Decimal(match[3]))
        )
        position = match.end()
        if position == len(expression):
            return tuple(predicates)
        connector = re.compile(r"\s+and\s+").match(expression, position)
        if connector is None:
            raise ValueError(CONJUNCTION_GRAMMAR)
        position = connector.end()


def formulate_templates(
    prompt: str,
    evidence: "ResearchEvidence",
    run_id: str,
) -> tuple[EvidenceNote, HypothesisBatch, CandidateBatch, ResearchCritique]:
    """Two predeclared model comparisons over the requested signal.

    Comparisons are conjunctions, with exact decimals; no eval, guessed thresholds or
    arbitrary tool selection. Bare prose selects a signal for modeling, not an entry filter.
    """
    citations = tuple(c["evidence_id"] for c in evidence.calls[:3])
    text = prompt.casefold()
    matches = list(COMPARISON.finditer(text))
    names = tuple(dict.fromkeys(m[1] for m in matches))
    if not names:
        names = tuple(
            n for n in evidence.registered_names if re.search(rf"\b{re.escape(n)}\b", text)
        )
    if not names:
        names = next(
            ((name,) for pattern, name in ALIASES if re.search(pattern, text)),
            ("unrecognized_signal",),
        )
    series = tuple(sorted({m["series"] for m in evidence.markets}))
    # A named actual series scopes the template; otherwise all permitted series are explicit.
    selected = tuple(s for s in series if s.casefold() in text) or series
    family = selected[0] if selected else "UNAVAILABLE"
    sources = tuple(evidence.coverage["configured_source_kinds"])
    if evidence.coverage["data_kind"] != "synthetic" and "revision_f" in evidence.registered_names:
        sources = ("kalshi", "open-meteo")
    unsupported = []
    predicates: tuple[Predicate, ...] = ()
    if re.search(r"[<>=!]", text):
        try:
            predicates = parse_conjunction(text)
        except ValueError as exc:
            unsupported.append(str(exc))
    if len(names) > 10:
        unsupported.append("Local formulation supports at most ten distinct requested signals")
        names = names[:10]
    if re.search(
        r"\b(kelly|hedg\w*|momentum|arbitrage|short|sell|buy no|resting|limit order)\b", text
    ):
        unsupported.append("Requested semantics exceed local YES/hold-to-settlement templates")
    if re.search(r"\b(or|xor|unless|not|nor|otherwise|except|if|when)\b|[|&^]|!=", text):
        unsupported.append("Unsupported logic requires a reviewed explicit specification")
    missing_names = set(names) - set(evidence.registered_names)
    if missing_names:
        unsupported.append(
            "Signal unavailable in this adapter: " + ", ".join(sorted(missing_names))
        )
    if not selected:
        unsupported.append("No actual listed contracts are available in the captured evidence")
    hypotheses, candidates = [], []
    for index, variables in enumerate((names, tuple(dict.fromkeys((*names, "hours_to_close"))))):
        mechanism = (
            "The requested signal " + ", ".join(names) + " may improve contract probabilities."
            if index == 0
            else "A forecast-error baseline may be more stable than regression for this signal."
        )
        hypothesis = ResearchHypothesis(
            hypothesis_id=f"template-h{index}",
            mechanism=mechanism,
            market_family=family,
            window="Frozen decision-time inputs before each actual contract close",
            variables=variables,
            direction="Test probability accuracy; association and sign remain unverified",
            test="Compare event-weighted temporal validation Brier and log loss with baselines.",
            falsification="Reject without validation improvement and fee-aware depth evidence.",
            necessary_evidence=(
                "Point-in-time source vintages and source-matched official outcomes",
                "Independent date blocks, historical sized books and effective fees",
            ),
            evidence_ids=citations,
        )
        hypotheses.append(hypothesis)
        model = "ridge" if index == 0 else "forecast_error"
        if "forward_only" in evidence.config.model_families:
            model = "forward_only"
        spec = None
        if not unsupported:
            spec = StrategySpec(
                strategy_id=f"local-template-{index}",
                name=f"{family} signal test {index + 1}",
                version=1,
                description=mechanism,
                hypothesis=mechanism,
                strategy_family=StrategyFamily.INFORMATIONAL,
                market_universe=MarketUniverse(
                    series_tickers=selected, description="Actual permitted captured series"
                ),
                required_sources=sources,
                features=tuple(
                    FeatureRequirement(
                        name=n,
                        version=evidence.registered_versions[n],
                        description="Frozen decision-time covariate",
                    )
                    for n in variables
                ),
                model_kind=ModelKind.DOMAIN_STATISTICAL,
                entry_rules=RuleSet(
                    description="Requested comparisons AND model probability > 0.55",
                    all_of=(
                        Predicate(
                            feature="model_yes_probability",
                            op=ComparisonOp.GT,
                            threshold=Decimal("0.55"),
                        ),
                        *predicates,
                    ),
                ),
                exit_rules=RuleSet(
                    description="Hold to settlement using the official contract outcome",
                    all_of=(
                        Predicate(feature="settlement", op=ComparisonOp.EQ, threshold=Decimal(1)),
                    ),
                ),
                minimum_edge=Decimal("0.03"),
                position_sizing=PositionSizing(
                    method=SizingMethod.FIXED_CONTRACTS,
                    contracts=Decimal(1),
                    max_contracts=Decimal(1),
                ),
                execution=ExecutionPreferences(time_in_force=TimeInForce.FILL_OR_KILL),
                assumptions=(
                    "Local template; unsupported prose is not interpreted as trading rules",
                    "Model families use their registered feature sets; no feature ablation",
                ),
                invalidation_conditions=("Evidence, model or execution gates fail",),
                generated_by=Actor(kind=ActorKind.AGENT, actor_id="local-template-v1"),
                generation_run_id=UUID(run_id),
                created_at=utc_now(),
            )
        candidates.append(
            ResearchCandidate(
                candidate_id=f"template-c{index}",
                hypothesis_id=hypothesis.hypothesis_id,
                spec=spec,
                missing_capability="; ".join(unsupported),
                required_features=variables,
                required_sources=sources or ("kalshi",),
                model_family=model,
                evidence_ids=citations,
            )
        )
    note = EvidenceNote(
        market_understanding="Local templates select signals and literal feature comparisons.",
        mechanisms=tuple(h.mechanism for h in hypotheses),
        limitations=(
            "No language model is used; arbitrary prose is not fully understood.",
            "Two model comparisons are not causal tests or feature ablations.",
            *unsupported,
        ),
        evidence_ids=citations,
    )
    critique = ResearchCritique(
        verdicts=tuple(
            CandidateVerdict(
                candidate_id=c.candidate_id,
                accept_for_experiment=not unsupported,
                reason="Local rule checks only; independent evidence and experiment gates apply.",
                concerns=("No LLM critique or empirical edge follows from local formulation.",),
            )
            for c in candidates
        )
    )
    return (
        note,
        HypothesisBatch(hypotheses=tuple(hypotheses)),
        CandidateBatch(candidates=tuple(candidates)),
        critique,
    )
