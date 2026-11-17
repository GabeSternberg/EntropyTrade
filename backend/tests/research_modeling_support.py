"""Explicit synthetic event evidence for the acquired-feature modeling integration."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from entropytrade.data.sources import file_hash
from entropytrade.features.registry import scientific_hash
from entropytrade.research.acquire import RawStore
from entropytrade.research.families import weather_family
from entropytrade.research.hypotheses import local_hypotheses
from entropytrade.research.materialize import publish_feature
from entropytrade.research.model import HypothesisSpec, ResearchRequest
from entropytrade.research.registry import FeatureRegistry

REPO = Path(__file__).resolve().parents[2]
MODEL_NOW = datetime(2026, 11, 14, 15, tzinfo=UTC)


def modeling_fixture(
    root: Path,
    *,
    days: int = 220,
    late_labels: bool = False,
    constant_targets: bool = False,
    heldout_change: float = 0,
) -> tuple[HypothesisSpec, list[dict[str, Any]]]:
    """Publish real-format immutable artifacts; every source is labeled synthetic."""
    family = weather_family(REPO)
    request = ResearchRequest(
        objective="Study NWS forecast bias against Philadelphia settlement highs",
        family="weather",
        universe=("KXHIGHPHIL",),
    )
    spec = next(
        s
        for s in local_hypotheses(
            request, family, family.resolve_universe(request.objective, request.universe), MODEL_NOW
        )
        if s.provenance.template_id == "weather-forecast-bias"
    ).revalidated(candidate_models=("climatology", "gaussian_error", "ridge"))
    dataset = root / ".synthetic-dataset"
    dataset.mkdir(parents=True, exist_ok=True)
    (dataset / "records.jsonl").write_text(json.dumps({"synthetic": True, "days": days}) + "\n")
    raw_hash = RawStore(root).put(b"synthetic-modeling-source")
    (dataset / "receipts.jsonl").write_text(json.dumps({"sha256": raw_hash}) + "\n")
    (dataset / "parameters.json").write_text(json.dumps({"fixture": "synthetic-modeling"}))
    hashes = {
        name: file_hash(dataset / name)
        for name in ("records.jsonl", "receipts.jsonl", "parameters.json")
    }
    identifier = scientific_hash(hashes)
    (dataset / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "entropytrade-research-dataset-v1",
                "dataset_id": identifier,
                "checksums": hashes,
                "data_kind": "synthetic",
                "raw_hashes": [raw_hash],
            }
        )
    )
    target = root / "datasets" / ("sha256-" + identifier.removeprefix("sha256:"))
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        import shutil

        shutil.rmtree(dataset)
    else:
        dataset.rename(target)
    registry = FeatureRegistry()
    start = date(2026, 1, 1)
    artifacts = []
    for name in ("nws_pfm_max_f", "nws_cli_bias_f", "settlement_high_f"):
        definition = registry.get(name)
        rows = []
        for i in range(days):
            day = start + timedelta(days=i)
            at = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=15)
            forecast = 65 + (i % 21) - 10
            value = float(forecast + (i % 5) - 2)
            if constant_targets:
                value = 65
            if i >= int(days * 0.8):
                value += heldout_change
            if name == "settlement_high_f":
                rows.append(
                    {
                        "entity": "CLIPHL",
                        "target_date": day.isoformat(),
                        "decision_time": None,
                        "value": str(value),
                        "inputs_available_at": (
                            MODEL_NOW if late_labels else at + timedelta(days=1)
                        ).isoformat(),
                        "inputs": ["synthetic-label"],
                    }
                )
            else:
                for point in family.schedule:
                    from entropytrade.research.materialize import decision_times

                    decision = decision_times(day, [point], "America/New_York")[0]
                    rows.append(
                        {
                            "entity": "CLIPHL",
                            "target_date": day.isoformat(),
                            "decision_time": decision.isoformat(),
                            "value": str(forecast if name == "nws_pfm_max_f" else 0),
                            "inputs_available_at": (decision - timedelta(hours=1)).isoformat(),
                            "inputs": ["synthetic-forecast"],
                        }
                    )
        artifact = publish_feature(
            root,
            definition,
            entity="CLIPHL",
            schedule=family.schedule,
            window=(start, start + timedelta(days=days - 1)),
            input_datasets=[identifier],
            rows=rows,
            created_at=MODEL_NOW,
        )
        artifact["hypotheses"] = [spec.hypothesis_id]
        artifacts.append(artifact)
    return spec, artifacts
