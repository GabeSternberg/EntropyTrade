"""Approved data-source catalog and deterministic source evaluation.

Sources are reviewed data in ``configs/research/sources.json``; acquisition code exists only
for the adapters named there. A model may suggest a source, but only an exact catalog ID is
ever considered and no proposed URL is fetched.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.research.model import DataKind, DataRequirement

CATALOG_SCHEMA = "entropytrade-research-sources-v1"
ADAPTERS = frozenset(
    {"iem_afos_pfm", "iem_afos_cli", "weather_company_labels", "kalshi_settled_markets"}
)


class HostRule(DomainModel):
    host: str = Field(pattern=r"^[a-z0-9.-]+$")
    paths: tuple[str, ...] = Field(min_length=1)


class Provides(DomainModel):
    kind: DataKind
    variable: str


class SourceDescriptor(DomainModel):
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    name: str
    operator: str
    documentation: str
    access: Literal["public_anonymous", "credential_required", "unavailable"]
    authorization: str
    license: str
    hosts: tuple[HostRule, ...] = ()
    provides: tuple[Provides, ...] = Field(min_length=1)
    families: tuple[str, ...]
    historical: Literal["archive", "prospective_only", "none"]
    clock: Literal["issuance", "receipt", "unknown"]
    clock_basis: str
    timezone: str
    corrections: str
    cost: Literal["free", "metered"]
    rate_limit_seconds: float = Field(ge=0, le=60)
    settlement_authority: tuple[str, ...] = ()
    authority_note: str = ""
    adapter: str | None = None
    collector: Literal["canonical_local_chain", "requires_collector_change"] | None = None
    human_action: str = ""
    point_in_time: str
    entities: dict[str, dict[str, str]]
    unverified_entities_note: str = ""

    def provides_for(self, requirement: DataRequirement) -> bool:
        return any(
            p.kind is requirement.kind and p.variable == requirement.variable for p in self.provides
        )


class SourceDecision(DomainModel):
    source_id: str
    name: str
    requirement_id: str
    kind: DataKind
    entity: str
    decision: Literal["acquire", "forward_collect", "authorization_required", "reject"]
    reasons: tuple[str, ...]
    checks: dict[str, bool]


def load_catalog(repo: Path) -> dict[str, SourceDescriptor]:
    value: dict[str, Any] = json.loads((repo / "configs/research/sources.json").read_text())
    if value.get("schema") != CATALOG_SCHEMA:
        raise ValueError("unknown research source catalog schema")
    sources = [SourceDescriptor.model_validate(item) for item in value["sources"]]
    for source in sources:
        if source.adapter is not None and source.adapter not in ADAPTERS:
            raise ValueError(f"source {source.source_id} names an unimplemented adapter")
        if source.adapter is not None and not source.hosts:
            raise ValueError(f"source {source.source_id} has an adapter but no host allowlist")
        if source.historical == "prospective_only" and source.collector is None:
            raise ValueError(f"prospective source {source.source_id} names no collector")
    catalog = {s.source_id: s for s in sources}
    if len(catalog) != len(sources):
        raise ValueError("duplicate research source IDs")
    return catalog


_CLOCKS = {"issuance": {"issuance"}, "receipt": {"issuance", "receipt"}, "any": None}


def evaluate(
    source: SourceDescriptor, requirement: DataRequirement, *, today: date
) -> SourceDecision:
    """Check identity, authorization, licensing, coverage, clocks, authority and cost."""
    reasons: list[str] = []
    checks = {
        "approved_catalog": True,
        "provides_requirement": source.provides_for(requirement),
        "family": requirement.family in source.families,
        "entity": requirement.entity in source.entities,
        "authorization": source.access == "public_anonymous",
        "license_recorded": bool(source.license.strip()),
        "cost": source.cost == "free",
    }
    clocks = _CLOCKS[requirement.clock]
    checks["clock"] = clocks is None or source.clock in clocks
    if requirement.kind is DataKind.SETTLEMENT_LABELS and requirement.variable == "daily_high_f":
        checks["settlement_authority"] = requirement.series in source.settlement_authority
    historical_window = requirement.end < today
    checks["historical_coverage"] = source.historical == "archive" or not historical_window
    checks["adapter"] = source.adapter is not None
    if not checks["entity"]:
        reasons.append(
            f"no verified {source.source_id} mapping for {requirement.entity}"
            + (f" ({source.unverified_entities_note})" if source.unverified_entities_note else "")
        )
    if not checks["clock"]:
        reasons.append(
            f"provides {source.clock} clocks; the requirement needs {requirement.clock} clocks"
            f" ({source.point_in_time})"
        )
    if checks.get("settlement_authority") is False:
        reasons.append(
            source.authority_note or "not the settlement authority named in the contract text"
        )
    if not checks["authorization"]:
        reasons.append(f"access is {source.access}; needs explicit authorization")
    if not checks["cost"]:
        reasons.append("metered source; spending needs approval")
    blocking = [
        k
        for k in ("provides_requirement", "family", "entity", "clock", "settlement_authority")
        if checks.get(k) is False
    ]
    if blocking:
        decision: Literal["acquire", "forward_collect", "authorization_required", "reject"] = (
            "reject"
        )
    elif not checks["authorization"] or not checks["cost"]:
        decision = "authorization_required"
    elif source.historical == "prospective_only":
        decision = "forward_collect"
        reasons.append(source.point_in_time)
        if source.collector == "requires_collector_change":
            reasons.append(
                "the canonical collector does not capture this; a reviewed collector change and "
                "human deployment are required"
            )
    elif not checks["adapter"]:
        decision = "authorization_required"
        reasons.append(
            source.human_action or "no automated adapter; a human must acquire or certify this"
        )
    else:
        decision = "acquire"
        reasons.append(f"{source.clock} clocks: {source.clock_basis}")
    return SourceDecision(
        source_id=source.source_id,
        name=source.name,
        requirement_id=requirement.requirement_id,
        kind=requirement.kind,
        entity=requirement.entity,
        decision=decision,
        reasons=tuple(reasons),
        checks=checks,
    )


def discover(
    catalog: dict[str, SourceDescriptor], requirement: DataRequirement, *, today: date
) -> list[SourceDecision]:
    """Every catalog source that offers this kind and variable, with its decision."""
    return [
        evaluate(source, requirement, today=today)
        for source in catalog.values()
        if source.provides_for(requirement)
    ]
