"""Frozen source adapters, shared by all configured locations. No city-specific rules."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from entropytrade.data.schema import DatasetConfig, MarketEvidence, Observation
from entropytrade.domain.time import ensure_utc
from entropytrade.exchange.kalshi.recorded import market_from_body


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return ensure_utc(datetime.fromisoformat(value))


def load_sources(
    root: Path,
    config: DatasetConfig,
) -> tuple[list[MarketEvidence], list[Observation], dict[str, str], list[str]]:
    markets: list[MarketEvidence] = []
    observations: list[Observation] = []
    inputs: dict[str, str] = {}
    warnings: list[str] = []
    # Canonical inputs are also the output of the public SDK acquisition command.
    canonical = root / "markets.jsonl"
    if canonical.exists():
        for sidecar in ("acquisition.json", "normalization.json", "acquisition.sqlite"):
            path = root / sidecar
            if path.exists():
                inputs[sidecar] = file_hash(path)
        for path in sorted((root / "raw").glob("*.json")):
            inputs[path.relative_to(root).as_posix()] = file_hash(path)
        inputs["markets.jsonl"] = file_hash(canonical)
        markets.extend(
            MarketEvidence.model_validate_json(line)
            for line in canonical.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    else:
        # Legacy raw JSON pages have actual exchange contracts; ignore narrow summaries
        # lacking rules, rather than reconstructing nonexistent contract definitions.
        manifests: dict[Path, datetime] = {}
        for path in sorted(root.rglob("*manifest.json")):
            body = json.loads(path.read_text(encoding="utf-8"))
            fetched = stamp(body.get("fetched_at"))
            if fetched is not None:
                manifests[path.parent] = fetched
                inputs[path.relative_to(root).as_posix()] = file_hash(path)
        for path in sorted(root.rglob("*.json")):
            if "manifest" in path.name:
                continue
            body = json.loads(path.read_text(encoding="utf-8"))
            rows = body.get("markets", []) if isinstance(body, dict) else body
            if not isinstance(rows, list):
                continue
            selected = [
                row
                for row in rows
                if isinstance(row, dict)
                and "rules_primary" in row
                and any(
                    str(row.get("ticker", "")).startswith(p.series + "-") for p in config.locations
                )
            ]
            if not selected:
                continue
            parent = path.parent
            while parent != root and parent not in manifests:
                parent = parent.parent
            captured = manifests.get(parent)
            if captured is None:
                warnings.append(f"{path.relative_to(root)}: no defensible receipt timestamp")
                continue
            relative = path.relative_to(root).as_posix()
            digest = file_hash(path)
            inputs[relative] = digest
            for row in selected:
                series = str(row["ticker"]).split("-", 1)[0]
                markets.append(
                    MarketEvidence(
                        market=market_from_body(row, captured_at=captured, series=series),
                        created_at=stamp(row.get("created_time")),
                        capture_basis="legacy_manifest",
                        raw_ref=relative,
                        raw_hash=digest,
                    )
                )
    normalized = root / "observations.jsonl"
    if normalized.exists():
        inputs["observations.jsonl"] = file_hash(normalized)
        observations.extend(
            Observation.model_validate_json(line)
            for line in normalized.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    # Raw immutable references are mandatory and hashed. Never silently trust edited inputs.
    if "open-meteo" in config.sources:
        for location in config.locations:
            if location.forecast_file is not None:
                path = root / location.forecast_file
                if path.exists():
                    receipt = None
                    for manifest in (path.parent / "manifest.json", root / "manifest.json"):
                        if manifest.exists():
                            receipt = stamp(json.loads(manifest.read_text()).get("fetched_at"))
                            if receipt is not None:
                                break
                    if receipt is not None:
                        observations.extend(
                            import_previous_runs(
                                path, root=root, entity=location.station, received_at=receipt
                            )
                        )
                    else:
                        warnings.append(f"{location.name}: forecast receipt unknown; not imported")
    records: list[MarketEvidence | Observation] = [*markets, *observations]
    for record in records:
        path = (root / record.raw_ref).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("source raw_ref must point inside the source directory")
        relative = path.relative_to(root.resolve()).as_posix()
        if relative not in inputs:
            inputs[relative] = file_hash(path)
        actual = inputs[relative]
        if actual != record.raw_hash:
            raise ValueError(f"raw source hash mismatch: {relative}")
    return markets, observations, inputs, warnings


def import_previous_runs(
    path: Path,
    *,
    root: Path,
    entity: str,
    received_at: datetime,
) -> tuple[Observation, ...]:
    """Preserve legacy previous-day values but explicitly refuse to invent run clocks."""
    body: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    hourly = body.get("hourly", {})
    result: list[Observation] = []
    digest = file_hash(path)
    for variable, values in hourly.items():
        if "previous_day" not in variable or not variable.startswith("temperature_2m"):
            continue
        for valid, value in zip(hourly.get("time", []), values, strict=True):
            if value is None:
                continue
            day = date.fromisoformat(str(valid)[:10])
            result.append(
                Observation(
                    source_id="open-meteo",
                    entity_id=entity,
                    variable=variable,
                    unit=body.get("hourly_units", {}).get(variable),
                    valid_at=(
                        datetime.fromisoformat(str(valid)).replace(tzinfo=UTC)
                        if body.get("utc_offset_seconds") == 0
                        else None
                    ),
                    valid_on=day,
                    value=Decimal(str(value)),
                    received_at=received_at,
                    timing_basis="unknown",
                    evidence="previous_day field has no issue/publication vintage timestamp",
                    raw_ref=path.relative_to(root).as_posix(),
                    raw_hash=digest,
                )
            )
    return tuple(result)


def days(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=i) for i in range((end - start).days + 1))


def decisions(day: date, schedule: tuple[str, ...]) -> tuple[datetime, ...]:
    return tuple(
        datetime.fromisoformat(f"{day}T{hour}:00").replace(tzinfo=UTC)
        for hour in sorted(set(schedule))
    )
