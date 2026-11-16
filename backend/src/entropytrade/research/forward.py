"""Forward-collection planning against the existing canonical collector.

The website never starts a second canonical chain. A forward request records which existing
collector covers a requirement, how many independent events have accrued, and when the
requirement will be reevaluated. When coverage needs a collector change, the request says so
and waits for a human deployment instead of changing the collector.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from entropytrade.research.model import Assessment, AssessmentStatus, DataKind, DataRequirement
from entropytrade.research.sources import SourceDescriptor

CHECK_INTERVAL = timedelta(hours=6)
CollectorStatus = Literal["covered", "requires_collector_change"]


class CollectorConfig:
    """Read-only view of the canonical collector's checked-in configuration."""

    def __init__(self, repo: Path) -> None:
        collector = json.loads((repo / "configs/data/collector.json").read_text())
        weather = json.loads((repo / "configs/data/weather-forward.json").read_text())
        self.series = frozenset(str(s) for s in collector.get("series", []))
        self.stations = frozenset(str(item["station"]) for item in weather.get("locations", []))
        self.providers = tuple(str(p) for p in weather.get("providers", []))

    def coverage(
        self, source: SourceDescriptor, requirement: DataRequirement
    ) -> tuple[CollectorStatus, str]:
        if source.collector == "requires_collector_change":
            return (
                "requires_collector_change",
                f"The canonical collector does not capture {source.name}. A reviewed collector "
                "change and a human deployment on the collector host are required.",
            )
        if requirement.kind in {DataKind.DECISION_QUOTES, DataKind.ORDER_BOOK_DEPTH}:
            if requirement.series in self.series:
                return (
                    "covered",
                    f"configs/data/collector.json captures {requirement.series} order books.",
                )
            return (
                "requires_collector_change",
                f"{requirement.series} is not in configs/data/collector.json; adding it is a "
                "reviewed collector change.",
            )
        if requirement.kind in {DataKind.FORECAST_VINTAGES, DataKind.FORECAST_REVISIONS}:
            if (
                requirement.entity in self.stations
                and len(self.providers) >= requirement.min_sources
            ):
                return (
                    "covered",
                    f"configs/data/weather-forward.json polls {', '.join(self.providers)} for "
                    f"{requirement.entity}.",
                )
            return (
                "requires_collector_change",
                f"{requirement.entity} is not polled by enough providers in "
                "configs/data/weather-forward.json.",
            )
        return ("requires_collector_change", "No canonical collector captures this evidence.")


def forward_spec(requirement: DataRequirement) -> dict[str, Any]:
    return {
        "kind": requirement.kind.value,
        "variable": requirement.variable,
        "entity": requirement.entity,
        "series": requirement.series,
        "family": requirement.family,
        "clock": requirement.clock,
        "fidelity": requirement.fidelity,
        "min_sources": requirement.min_sources,
    }


def estimate(observed: int, required: int, now: datetime) -> datetime | None:
    """Daily contracts add at most one independent event per entity per day."""
    if observed >= required:
        return now
    return now + timedelta(days=required - observed)


def decorate_forward(
    requests: list[dict[str, Any]],
    requirements: list[DataRequirement],
    assessments: dict[str, Assessment],
    now: datetime,
) -> list[dict[str, Any]]:
    """Describe operational evidence separately from a checked-in collection plan.

    The existing integration has no installed-configuration attestation or authenticated
    recent receipt feed. Consequently it cannot claim ``deployed`` or ``collecting``.
    Counts in a sanitized collector summary never alter these states. Sufficiency comes
    only from the job's current evidence assessment, not a shared request's cached count.
    """
    result = []
    for request in requests:
        related = [r for r in requirements if r.coverage_key == request["coverage_key"]]
        checked = [assessments.get(r.requirement_id) for r in related]
        sufficient = bool(checked) and all(
            a is not None and a.status is AssessmentStatus.SATISFIED for a in checked
        )
        if sufficient:
            state = "sufficient"
            detail = "This job's evidence assessment meets its requirement; model and "
            detail += "execution gates independently verify the retained data before use."
        elif request.get("last_error"):
            state = "failed" if request.get("status") == "failed" else "stalled"
            detail = "Collection has a recorded error; no active collection is verified."
        elif request.get("collector_status") != "covered":
            state = "blocked"
            detail = "A reviewed collector change and installation on the collector host "
            detail += "are required. The website has not deployed collection."
        else:
            state = "planned"
            detail = "Repository configuration covers this request. Installation and recent "
            detail += "original collector receipts have not been verified in this workspace."
        result.append(
            {
                **request,
                "operational_status": state,
                "operational_detail": detail,
                "operational_assessed_at": now.isoformat(),
                "deployment_verified": False,
                "recent_receipts_verified": False,
            }
        )
    return result
