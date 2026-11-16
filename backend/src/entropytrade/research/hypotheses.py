"""Hypothesis formulation, deduplication and machine-readable data requirements.

Local templates are deterministic research proposals, not language-model reasoning.
Provider proposals are untrusted typed data; they are validated and normalized here
before anything is persisted. No hypothesis is ever presented as an established edge.
"""

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.features.registry import scientific_hash
from entropytrade.research.families import Entity, Family, Template
from entropytrade.research.model import (
    MIN_EVENTS,
    NAME,
    DataKind,
    DataRequirement,
    FeatureNeed,
    HypothesisSpec,
    Provenance,
    ResearchRequest,
    RuleSketch,
    hypothesis_signature,
    requirement_id,
)
from entropytrade.research.registry import FeatureInput, FeatureRegistry, Resolution

_ISSUED = {
    DataKind.FORECAST_VINTAGES,
    DataKind.FORECAST_REVISIONS,
    DataKind.REFERENCE_OBSERVATIONS,
}
_MARKET = {
    DataKind.MARKET_CONTRACTS,
    DataKind.MARKET_RULES,
    DataKind.DECISION_QUOTES,
    DataKind.ORDER_BOOK_DEPTH,
    DataKind.TRADE_PRINTS,
    DataKind.FEE_SCHEDULE,
}


class ProposedFeature(DomainModel):
    name: str = Field(pattern=NAME)
    data_kinds: tuple[DataKind, ...] = Field(default=(), max_length=6)
    note: str = Field(default="", max_length=400)


class HypothesisProposal(DomainModel):
    """Provider output schema. Every field is validated; prose never becomes executable."""

    title: str = Field(min_length=5, max_length=160)
    rationale: str = Field(min_length=20, max_length=2000)
    features: tuple[ProposedFeature, ...] = Field(min_length=1, max_length=8)
    label: str = Field(pattern=NAME)
    rules: tuple[RuleSketch, ...] = Field(default=(), max_length=4)
    candidate_models: tuple[str, ...] = Field(min_length=1, max_length=6)
    validation_plan: str = Field(min_length=10, max_length=1500)
    leakage_risks: tuple[str, ...] = Field(min_length=1, max_length=8)
    invalidation: tuple[str, ...] = Field(min_length=1, max_length=8)
    proposed_sources: tuple[str, ...] = Field(default=(), max_length=8)


class HypothesisProposalBatch(DomainModel):
    hypotheses: tuple[HypothesisProposal, ...] = Field(min_length=2, max_length=6)


def _rank(template: Template, objective: str) -> tuple[int, str]:
    text = objective.casefold()
    return (-sum(word in text for word in template.keywords), template.template_id)


def _spec(
    *,
    request: ResearchRequest,
    family: Family,
    universe: Sequence[Entity],
    title: str,
    rationale: str,
    features: tuple[FeatureNeed, ...],
    label: FeatureNeed,
    rules: tuple[RuleSketch, ...],
    models: tuple[str, ...],
    validation_plan: str,
    leakage: tuple[str, ...],
    invalidation: tuple[str, ...],
    provenance: Provenance,
) -> HypothesisSpec:
    signature = hypothesis_signature(family.family, rationale, tuple(f.name for f in features))
    return HypothesisSpec(
        hypothesis_id="h-" + signature.removeprefix("sha256:")[:12],
        signature=signature,
        title=title,
        objective=request.objective,
        family=family.family,
        universe=tuple(e.series for e in universe),
        rationale=rationale,
        features=features,
        label=label,
        decision_schedule=family.schedule,
        timestamp_semantics=family.timestamp_semantics,
        candidate_models=models,
        rules=rules,
        validation_plan=validation_plan,
        leakage_risks=leakage,
        invalidation=invalidation,
        provenance=provenance,
    )


def local_hypotheses(
    request: ResearchRequest, family: Family, universe: Sequence[Entity], now: datetime
) -> list[HypothesisSpec]:
    """Every family template, ranked by overlap with the objective."""
    ordered = sorted(family.templates, key=lambda t: _rank(t, request.objective))
    return [
        _spec(
            request=request,
            family=family,
            universe=universe,
            title=t.title,
            rationale=t.rationale,
            features=t.features,
            label=t.label,
            rules=t.rules,
            models=t.candidate_models,
            validation_plan=t.validation_plan,
            leakage=t.leakage_risks,
            invalidation=t.invalidation,
            provenance=Provenance(
                generator="local_templates", template_id=t.template_id, created_at=now
            ),
        )
        for t in ordered
    ]


def provider_hypotheses(
    batch: HypothesisProposalBatch,
    request: ResearchRequest,
    family: Family,
    universe: Sequence[Entity],
    provenance: Provenance,
) -> list[HypothesisSpec]:
    """Normalize provider proposals. Unknown models are dropped, never invented."""
    allowed = set(family.models)
    result = []
    for proposal in batch.hypotheses:
        models = tuple(dict.fromkeys(m for m in proposal.candidate_models if m in allowed))
        result.append(
            _spec(
                request=request,
                family=family,
                universe=universe,
                title=proposal.title,
                rationale=proposal.rationale,
                features=tuple(
                    FeatureNeed(name=f.name, data_kinds=f.data_kinds, note=f.note)
                    for f in proposal.features
                ),
                label=FeatureNeed(name=proposal.label, role="label"),
                rules=tuple(
                    r for r in proposal.rules if r.feature in {f.name for f in proposal.features}
                ),
                models=models or ("market_baseline",),
                validation_plan=proposal.validation_plan,
                leakage=proposal.leakage_risks,
                invalidation=proposal.invalidation,
                provenance=provenance,
            )
        )
    return result


def deduplicate(
    specs: Iterable[HypothesisSpec], prior: dict[str, str]
) -> list[tuple[HypothesisSpec, str]]:
    """Return (spec, note). A repeated signature in this batch is a duplicate.

    ``prior`` maps signatures to the job that first searched them; repeats across jobs are
    kept but recorded, so selection effects can be accounted for later.
    """
    seen: set[str] = set()
    result = []
    for index, spec in enumerate(specs):
        if spec.signature in seen:
            # Keep the duplicate inspectable under its own identifier.
            digest = scientific_hash({"duplicate_of": spec.signature, "position": index})
            result.append(
                (
                    spec.revalidated(hypothesis_id="h-" + digest.removeprefix("sha256:")[:12]),
                    "duplicate",
                )
            )
            continue
        seen.add(spec.signature)
        result.append((spec, "previously_searched" if spec.signature in prior else "new"))
    return result


def _inputs(
    need: FeatureNeed, resolution: Resolution, registry: FeatureRegistry
) -> tuple[FeatureInput, ...]:
    if resolution.feature_id is not None:
        return registry.get(resolution.feature_id).inputs
    # An unregistered name keeps its declared evidence needs so acquisition can still be
    # attempted. Its variable is its own name: no dataset silently stands in for it.
    return tuple(
        FeatureInput(
            kind=kind,
            variable=need.name,
            clock="issuance" if kind in _ISSUED else "receipt",
            fidelity="quote" if kind is DataKind.DECISION_QUOTES else "any",
        )
        for kind in need.data_kinds
    )


def requirements(
    spec: HypothesisSpec,
    family: Family,
    universe: Sequence[Entity],
    registry: FeatureRegistry,
    *,
    window: tuple[date, date],
    depth: Literal["quick", "standard", "thorough"],
) -> tuple[list[DataRequirement], list[Resolution]]:
    """Machine-readable requirements, one per evidence kind and entity."""
    minimum = MIN_EVENTS[depth]
    resolutions: list[Resolution] = []
    needs: list[tuple[FeatureInput, str]] = []
    for need in (*spec.features, spec.label):
        resolution = registry.resolve(need.name)
        resolutions.append(resolution)
        needs.extend(
            (item.revalidated(blocking="predictive"), resolution.feature_id or "")
            for item in _inputs(need, resolution, registry)
        )
    for kind, variable, clock, fidelity in family.execution_needs:
        needs.append(
            (
                FeatureInput(
                    kind=kind,
                    variable=variable,
                    clock=clock,
                    fidelity=fidelity,
                    blocking="execution",
                ),
                "",
            )
        )
    merged: dict[str, DataRequirement] = {}
    for item, feature in needs:
        for entity in universe:
            key_entity = (
                entity.series
                if item.kind in _MARKET or family.family != "weather"
                else entity.entity
            )
            identifier = requirement_id(
                kind=item.kind,
                family=family.family,
                entity=key_entity,
                variable=item.variable,
                clock=item.clock,
                fidelity=item.fidelity,
            )
            if item.min_sources > 1:
                identifier += f"-s{item.min_sources}"
            events = 1 if item.kind is DataKind.FEE_SCHEDULE else minimum
            previous = merged.get(identifier)
            if previous is None:
                merged[identifier] = DataRequirement(
                    requirement_id=identifier,
                    kind=item.kind,
                    family=family.family,
                    entity=key_entity,
                    series=entity.series,
                    variable=item.variable,
                    start=window[0],
                    end=window[1],
                    clock=item.clock,
                    fidelity=item.fidelity,
                    min_events=events,
                    min_vintages=item.min_vintages,
                    min_sources=item.min_sources,
                    blocking=item.blocking,
                    purpose=_purpose(item, feature),
                    features=(feature,) if feature else (),
                    hypotheses=(spec.hypothesis_id,),
                    predictive_for=(spec.hypothesis_id,) if item.blocking == "predictive" else (),
                )
            else:
                merged[identifier] = previous.revalidated(
                    blocking="predictive"
                    if "predictive" in {previous.blocking, item.blocking}
                    else "execution",
                    features=tuple(
                        dict.fromkeys((*previous.features, *([feature] if feature else [])))
                    ),
                    min_vintages=max(previous.min_vintages, item.min_vintages),
                    predictive_for=previous.predictive_for
                    or ((spec.hypothesis_id,) if item.blocking == "predictive" else ()),
                )
    return list(merged.values()), resolutions


def _purpose(item: FeatureInput, feature: str) -> str:
    use = f"input to {feature}" if feature else "executable backtest evidence"
    clock = {
        "issuance": "with original issuance clocks",
        "receipt": "with receipt clocks",
        "any": "with recorded provenance",
    }[item.clock]
    return f"{item.kind.value.replace('_', ' ')} ({item.variable}) {clock}; {use}"


def merge_requirements(groups: Iterable[Sequence[DataRequirement]]) -> list[DataRequirement]:
    """Combine per-hypothesis requirements into one job-level set."""
    merged: dict[str, DataRequirement] = {}
    for group in groups:
        for item in group:
            previous = merged.get(item.requirement_id)
            if previous is None:
                merged[item.requirement_id] = item
                continue
            merged[item.requirement_id] = previous.revalidated(
                blocking="predictive"
                if "predictive" in {previous.blocking, item.blocking}
                else "execution",
                features=tuple(dict.fromkeys((*previous.features, *item.features))),
                hypotheses=tuple(dict.fromkeys((*previous.hypotheses, *item.hypotheses))),
                predictive_for=tuple(
                    dict.fromkeys((*previous.predictive_for, *item.predictive_for))
                ),
                min_vintages=max(previous.min_vintages, item.min_vintages),
                min_events=max(previous.min_events, item.min_events),
            )
    return sorted(merged.values(), key=lambda r: (r.blocking != "predictive", r.kind, r.entity))
