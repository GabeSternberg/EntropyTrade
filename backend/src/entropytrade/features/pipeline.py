"""Full-local-day forecasts, source-matched labels and causal history, shared across cities."""

import json
import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from entropytrade.data.schema import Location, Observation
from entropytrade.data.sources import file_hash
from entropytrade.domain.market import Strike
from entropytrade.domain.time import ensure_utc
from entropytrade.features.registry import FEATURE_NAMES, feature_schema, scientific_hash
from entropytrade.storage.forecast_archive import ForecastArchive


def _at(text: str) -> datetime:
    return ensure_utc(datetime.fromisoformat(text))


def full_day_maxima(
    observations: Sequence[Observation], *, location: Location, target: date, decision: datetime
) -> list[dict[str, Any]]:
    start = datetime(target.year, target.month, target.day, tzinfo=ZoneInfo(location.timezone))
    end = datetime.combine(
        target + timedelta(days=1), datetime.min.time(), ZoneInfo(location.timezone)
    )
    cursor, until = start.astimezone(UTC), end.astimezone(UTC)
    required: set[datetime] = set()
    while cursor < until:
        required.add(cursor)
        cursor += timedelta(hours=1)
    groups: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
    for o in observations:
        if o.entity_id != location.station or o.role != "feature" or not o.known_at(decision):
            continue
        if o.unit != "degF":
            continue  # Unknown units never become a Fahrenheit model input.
        if o.variable not in {"temperature_f", "daily_high_f"} and not o.variable.startswith(
            "ensemble_"
        ):
            continue
        if o.valid_at is not None and o.valid_at not in required:
            continue
        if o.valid_at is None and o.valid_on != target:
            continue
        member_model = (o.model or o.variable) + (
            (":" + o.variable) if o.variable.startswith("ensemble_") else ""
        )
        groups[(o.source_id, member_model, o.revision_id or o.raw_hash)].append(o)
    results: list[dict[str, Any]] = []
    for (provider, model, revision), points in groups.items():
        values_by_time: dict[datetime | date, set[object]] = defaultdict(set)
        for point in points:
            values_by_time[point.valid_at or point.valid_on].add(point.value)
        if any(len(values) > 1 for values in values_by_time.values()):
            continue  # Conflicting values cannot silently become one forecast revision.
        daily = [p for p in points if p.variable == "daily_high_f"]
        if not daily and {p.valid_at for p in points} != required:
            continue
        available = max(
            max(p.available_at, p.revised_at or p.available_at)
            for p in points
            if p.available_at is not None
        )
        results.append(
            {
                "provider": provider,
                "model": model,
                "revision": revision,
                "high_f": float(max(p.value for p in daily or points)),
                "available_at": available.isoformat(),
                "raw_refs": sorted({p.raw_ref for p in points}),
                "raw_hashes": sorted({p.raw_hash for p in points}),
                "ensemble": any(p.variable.startswith("ensemble_") for p in points),
            }
        )
    return sorted(
        results, key=lambda p: (p["available_at"], p["provider"], p["model"], p["revision"])
    )


def _settlement_source(row: dict[str, Any]) -> str | None:
    rules = json.loads(row["rules_json"])
    if rules.get("settlement_basis") != "contract_text":
        return None
    names = " ".join(source["name"].lower() for source in rules.get("settlement_sources", []))
    twc = "weather company" in names
    nws = "nws" in names or "national weather service" in names
    if twc and nws:
        return None  # Multiple named authorities require explicit disambiguation.
    if twc:
        return "weather-company"
    if nws:
        return "nws-cli"
    return None


def verified_targets(
    row: dict[str, Any], location: Location, observations: Sequence[Observation]
) -> list[Observation]:
    expected = _settlement_source(row)
    end = datetime.combine(
        date.fromisoformat(row["target_date"]) + timedelta(days=1),
        datetime.min.time(),
        ZoneInfo(location.timezone),
    ).astimezone(UTC)
    eligible = [
        o
        for o in observations
        if o.role == "observation"
        and o.source_id == expected
        and o.entity_id == location.station
        and o.variable == "settlement_high_f"
        and o.valid_on.isoformat() == row["target_date"]
        and o.unit == "degF"
        and o.timing_basis in {"received", "provider_publication"}
        and o.available_at is not None
        and o.available_at >= end
        and o.value == o.value.to_integral_value()
    ]
    return sorted(
        eligible,
        key=lambda o: (
            max(o.available_at, o.revised_at or o.available_at)
            if o.available_at
            else datetime.min.replace(tzinfo=UTC),
            o.raw_hash,
        ),
    )


def feature_rows(
    rows: Sequence[dict[str, Any]],
    observations: Sequence[Observation],
    locations: Sequence[Location],
) -> list[dict[str, Any]]:
    by_station = {p.station: p for p in locations}
    snapshots: dict[tuple[str, str], dict[str, Any]] = {}
    past: dict[str, dict[str, Any]] = {}
    output: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: (r["decision_time"], r["event_id"], r["market_ticker"])):
        decision, target = _at(row["decision_time"]), date.fromisoformat(row["target_date"])
        location = by_station[row["station"]]
        key = row["event_id"], row["decision_time"]
        labels = verified_targets(row, location, observations)
        label = labels[0] if labels else None
        if key not in snapshots:
            maxima = full_day_maxima(
                observations, location=location, target=target, decision=decision
            )
            per_model: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for p in maxima:
                per_model[(p["provider"], p["model"])].append(p)
            latest = [values[-1] for values in per_model.values()]
            revisions = [
                values[-1]["high_f"] - values[-2]["high_f"]
                for values in per_model.values()
                if len(values) > 1 and values[-1]["available_at"] > values[-2]["available_at"]
            ]
            members = [p["high_f"] for p in latest if p["ensemble"]]
            forecasts = [p["high_f"] for p in latest if not p["ensemble"]]
            if members:
                forecasts.append(fmean(members))
            high = fmean(forecasts) if forecasts else None
            history: list[float] = []
            bias_ids: list[str] = []
            for event_id, previous in past.items():
                available_labels = [o for o in previous["labels"] if o.known_at(decision)]
                if (
                    previous["station"] == location.station
                    and previous["day"] < target
                    and available_labels
                ):
                    latest_label = available_labels[-1]
                    history.append(float(latest_label.value) - previous["forecast"])
                    bias_ids.append(event_id)
            observed = [
                o
                for o in observations
                if o.entity_id == location.station
                and o.variable == "observed_temperature_f"
                and o.role == "feature"
                and o.unit == "degF"
                and o.known_at(decision)
                and o.valid_at is not None
                and o.valid_at <= decision
                and (decision - o.valid_at).total_seconds() <= 6 * 3600
            ]
            features: dict[str, float | None] = {
                "forecast_high_f": high,
                "revision_f": fmean(revisions) if revisions else None,
                "model_disagreement_f": pstdev(forecasts) if len(forecasts) > 1 else None,
                "ensemble_mean_f": fmean(members) if members else None,
                "ensemble_std_f": pstdev(members) if len(members) > 1 else None,
                "station_bias_f": fmean(history) if history else None,
                "observed_temperature_f": float(
                    max(
                        observed, key=lambda o: o.valid_at or datetime.min.replace(tzinfo=UTC)
                    ).value
                )
                if observed
                else None,
                "hours_to_close": None,
                "season_sin": math.sin(2 * math.pi * target.timetuple().tm_yday / 365.25),
                "season_cos": math.cos(2 * math.pi * target.timetuple().tm_yday / 365.25),
            }
            snapshots[key] = {
                "features": features,
                "forecast_evidence": latest,
                "bias_event_ids": sorted(bias_ids),
            }
            if label is not None and high is not None and row["event_id"] not in past:
                past[row["event_id"]] = {
                    "station": location.station,
                    "day": target,
                    "labels": labels,
                    "forecast": high,
                }
        snap = snapshots[key]
        features = dict(snap["features"])
        # These are the actual contract's deadlines, not a fabricated fixed settlement hour.
        market = json.loads(row["provenance_json"])["metadata"]["market"]
        strike_data = json.loads(row["strike_json"])
        evaluable = (
            strike_data is not None
            and Strike.model_validate(strike_data).is_evaluable
            and market["market_type"] == "binary"
        )
        rules_text = json.dumps(json.loads(row["rules_json"])).lower()
        fahrenheit_rules = "fahrenheit" in rules_text or "°f" in rules_text
        features["hours_to_close"] = (
            (_at(market["close_time"]) - decision).total_seconds() / 3600
            if row["rules_known_at_decision"]
            else None
        )
        quality = []
        if features["forecast_high_f"] is None:
            quality.append("no complete known forecast vintage")
        if label is None:
            quality.append("no source-matched integer temperature label")
        if not row["contract_existed_at_decision"]:
            quality.append("contract existence not established")
        if not row["rules_known_at_decision"]:
            quality.append("historical contract rules not known at decision")
        if not fahrenheit_rules:
            quality.append("contract Fahrenheit units not explicit")
        if not evaluable:
            quality.append("unsupported contract payout semantics")
        output.append(
            {
                **row,
                "feature_values_json": json.dumps(features, sort_keys=True, allow_nan=False),
                "feature_hash": scientific_hash(features),
                "feature_evidence_json": json.dumps(snap, sort_keys=True),
                "temperature_labels_json": json.dumps(
                    [o.model_dump(mode="json") for o in labels], sort_keys=True
                ),
                "temperature_target_f": None if label is None else float(label.value),
                "temperature_available_at": None
                if label is None or label.available_at is None
                else label.available_at.isoformat(),
                "feature_eligible": features["forecast_high_f"] is not None
                and row["contract_existed_at_decision"]
                and row["rules_known_at_decision"]
                and _settlement_source(row) is not None
                and fahrenheit_rules
                and evaluable,
                "missing_features_json": json.dumps(
                    [n for n in FEATURE_NAMES if features[n] is None]
                ),
                "eligibility_notes_json": json.dumps(quality),
            }
        )
    return output


def build_features(
    *,
    dataset: Path,
    archives: Sequence[Path],
    output: Path,
    observations: Sequence[Observation] = (),
    data_kind: str = "real",
) -> dict[str, Any]:
    manifest = json.loads((dataset / "manifest.json").read_text())
    if manifest.get("data_kind", "real") != data_kind:
        raise ValueError("real and synthetic datasets must not be mixed")
    checksum_path = dataset / "checksums.json"
    if checksum_path.exists():
        for name, digest in json.loads(checksum_path.read_text()).items():
            if (
                not (dataset / name).resolve().is_relative_to(dataset.resolve())
                or file_hash(dataset / name) != digest
            ):
                raise ValueError("source dataset checksum mismatch")
    all_observations = list(observations)
    snapshots: list[dict[str, Any]] = []
    for path in archives:
        archive = ForecastArchive(path, read_only=True)
        try:
            found, summary = archive.snapshot(data_kind=data_kind)
            all_observations.extend(found)
            snapshots.append(summary)
        finally:
            archive.close()
    if (dataset / "observations.parquet").exists():
        all_observations.extend(
            Observation.model_validate_json(r["payload_json"])
            for r in pq.read_table(dataset / "observations.parquet").to_pylist()
        )
    locations = [Location.model_validate(p) for p in manifest["config"]["locations"]]
    base_rows = pq.read_table(dataset / "rows.parquet").to_pylist()
    transformed = feature_rows(base_rows, all_observations, locations)
    code = {p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    payload = {
        "source_dataset": manifest["dataset_version"],
        "source_rows_hash": file_hash(dataset / "rows.parquet"),
        "data_kind": data_kind,
        "schema": feature_schema(),
        "code_hashes": code,
        "weather_archives": snapshots,
        "observations_hash": scientific_hash([o.model_dump(mode="json") for o in all_observations]),
        "rows_hash": scientific_hash(transformed),
        "rows": len(transformed),
        "independent_events": len({r["event_id"] for r in transformed}),
        "eligible_events": len({r["event_id"] for r in transformed if r["feature_eligible"]}),
        "events_with_scalar_labels": len(
            {r["event_id"] for r in transformed if r["temperature_target_f"] is not None}
        ),
        "cutoff_rule": "each row uses only information available by its decision time",
        "forecast_proxy": "maximum hourly forecast, not a claim of exact settlement measurement",
    }
    if "temporal_boundaries" in manifest:
        payload["temporal_boundaries"] = manifest["temporal_boundaries"]
        payload["protected_events"] = manifest.get("protected_events", [])
        payload["retained_capture_audit"] = manifest.get("retained_capture_audit", [])
        if "retained_shadow_audit" in manifest:
            payload["retained_shadow_audit"] = manifest["retained_shadow_audit"]
    version = scientific_hash(payload)
    destination = output / version.removeprefix("sha256:")
    if destination.exists():
        if json.loads((destination / "manifest.json").read_text()) != {
            **payload,
            "feature_version": version,
        }:
            raise ValueError("feature manifest mismatch")
        if (
            file_hash(destination / "features.parquet")
            != (destination / "features.sha256").read_text().strip()
        ):
            raise ValueError("feature artifact checksum mismatch")
        return {**payload, "feature_version": version}
    destination.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(transformed), destination / "features.parquet", compression="zstd"
    )
    (destination / "features.sha256").write_text(file_hash(destination / "features.parquet"))
    result = {**payload, "feature_version": version}
    (destination / "manifest.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    return result
