"""Receipt-time settlement highs from the official public Weather Company portal.

Only explicit source/station/date/rule matches qualify. Binary market results and
hourly maxima are never used as scalar labels. All parsing is replayable offline.
"""

import base64
import binascii
import json
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import Field, model_validator

from entropytrade.data.schema import Observation
from entropytrade.domain.base import DomainModel
from entropytrade.domain.time import UtcDatetime
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.features.pipeline import _settlement_source
from entropytrade.features.registry import scientific_hash

URL = "https://weather.com/kalshi/api/climate/primary?date="
MAX_BODY = 2_000_000
MAX_DATES = 8
STATIONS = {
    "CLIPHL": ("PHL", "KPHL", "America/New_York"),
    "CLIMDW": ("MDW", "KMDW", "America/Chicago"),
}


class LabelTarget(DomainModel):
    event_id: str
    station: str
    target_date: date
    timezone: str
    rules_hashes: tuple[str, ...]
    refusal: str = ""


class LabelReceipt(DomainModel):
    url: str
    received_at: UtcDatetime
    status: int | None = Field(default=None, ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    body_base64: str = Field(default="", max_length=2_700_000)
    error: str = ""

    def body(self) -> bytes:
        try:
            body = base64.b64decode(self.body_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid weather label receipt bytes") from exc
        if len(body) > MAX_BODY:
            raise ValueError("weather label response exceeds byte budget")
        return body

    @property
    def digest(self) -> str:
        return "sha256:" + sha256(self.body()).hexdigest()

    @model_validator(mode="after")
    def check(self) -> "LabelReceipt":
        if not re.fullmatch(re.escape(URL) + r"\d{4}-\d{2}-\d{2}", self.url):
            raise ValueError("weather label destination denied")
        date.fromisoformat(self.url.removeprefix(URL))
        self.body()
        if set(self.headers) - {"date", "last-modified", "etag", "content-type"}:
            raise ValueError("unexpected weather label receipt headers")
        return self


def compatible_rules(rules: dict[str, Any], ticker: str, station: str, day: str) -> bool:
    primary = rules["rules_primary"].casefold()
    return (
        _settlement_source({"rules_json": json.dumps(rules)}) == "weather-company"
        and "according to the weather company" in primary
        and "maximum temperature" in primary
        and re.search(rf"\({re.escape(station.casefold())}\)", primary) is not None
        and "fahrenheit" in primary
        and ticker_target_date(ticker) == date.fromisoformat(day)
        and rules.get("settlement_target_date") == day
    )


def targets(root: Path, protected: frozenset[str] = frozenset()) -> tuple[LabelTarget, ...]:
    """Read verified immutable rows, preserving every contract rule version per event."""
    from entropytrade.weather.history import load_snapshot

    snapshot = load_snapshot(root)
    rows = pq.read_table(root / "dataset/rows.parquet").to_pylist()
    locations = json.loads((root / "dataset/manifest.json").read_text())["config"]["locations"]
    timezones = {p["station"]: p["timezone"] for p in locations}
    protected |= frozenset(snapshot["identity"]["protected_events"])
    holdout = snapshot["identity"]["temporal_boundaries"][2]
    protected_pairs = {
        (r["station"], r["target_date"])
        for r in rows
        if r["event_id"] in protected or r["target_date"] >= holdout
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["event_id"]].append(row)
    result = []
    for event, members in sorted(grouped.items()):
        row = members[0]
        station, day = row["station"], row["target_date"]
        refusal = ""
        versions: dict[str, set[str]] = defaultdict(set)
        for member in members:
            rules = json.loads(member["rules_json"])
            versions[member["market_ticker"]].add(rules["rules_hash"])
            if (member["station"], member["target_date"]) != (station, day):
                refusal = "inconsistent station/date within event"
            if not compatible_rules(rules, member["market_ticker"], station, day):
                refusal = "unsupported or mismatched settlement source/station/date/rules"
        if any(len(v) != 1 for v in versions.values()):
            refusal = "contract rules changed across selected decisions"
        if station not in STATIONS or timezones[station] != STATIONS[station][2]:
            refusal = "station/timezone mapping is unsupported"
        if (station, day) in protected_pairs:
            refusal = "protected label excluded from acquisition and research"
        result.append(
            LabelTarget(
                event_id=event,
                station=station,
                target_date=date.fromisoformat(day),
                timezone=timezones[station],
                rules_hashes=tuple(sorted({v for vs in versions.values() for v in vs})),
                refusal=refusal,
            )
        )
    return tuple(result)


def _time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("provider clock is not an ISO timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("provider clock has no timezone")
    return parsed.astimezone(UTC)


def parse_label(target: LabelTarget, receipt: LabelReceipt) -> Observation:
    """Strict portal schema observed on 2026-10-31; no fixture-schema fallback."""
    if target.refusal:
        raise ValueError(target.refusal)
    if receipt.url != URL + target.target_date.isoformat():
        raise ValueError("wrong source/date receipt")
    if receipt.error or receipt.status != 200:
        raise ValueError(receipt.error or f"source HTTP {receipt.status}")
    if "application/json" not in receipt.headers.get("content-type", ""):
        raise ValueError("source did not return JSON")
    body = json.loads(receipt.body())
    if not isinstance(body, dict) or body.get("date") != target.target_date.isoformat():
        raise ValueError("source response date mismatch")
    cli, icao, timezone = STATIONS[target.station]
    if target.timezone != timezone:
        raise ValueError("wrong station timezone")
    found = [
        r
        for r in body.get("results", [])
        if isinstance(r, dict)
        and isinstance(r.get("station"), dict)
        and r["station"].get("cliId") == cli
    ]
    if len(found) != 1:
        raise ValueError("missing or duplicate settlement station")
    record = found[0]
    station, data = record["station"], record.get("data")
    if (station.get("icao"), station.get("timezone"), station.get("isDomestic")) != (
        icao,
        timezone,
        True,
    ):
        raise ValueError("source station identity/timezone mismatch")
    if (
        record.get("status") not in {"official", "revised"}
        or not isinstance(data, dict)
        or data.get("isOfficial") is not True
    ):
        raise ValueError("source report is preliminary, missing or nonofficial")
    if data.get("stationId") != cli or data.get("reportDate") != target.target_date.isoformat():
        raise ValueError("source report station/date mismatch")
    high = data.get("maxTemp")
    if type(high) is not int or not -150 <= high <= 150:
        raise ValueError("source high must be an integer Fahrenheit value")
    end = datetime.combine(
        target.target_date + timedelta(days=1), datetime.min.time(), ZoneInfo(timezone)
    ).astimezone(UTC)
    published = _time(data.get("issueTime"))
    revised = _time(record.get("revisedAt"))
    if receipt.received_at < end or any(
        t and not end <= t <= receipt.received_at for t in (published, revised)
    ):
        raise ValueError(
            "source publication/revision/receipt clock incompatible with completed day"
        )
    if published and revised and revised < published:
        raise ValueError("provider revision precedes publication")
    revision = scientific_hash(
        {
            "station": station,
            "data": data,
            "status": record["status"],
            "revisedAt": record.get("revisedAt"),
        }
    )
    return Observation(
        source_id="weather-company",
        entity_id=target.station,
        variable="settlement_high_f",
        valid_on=target.target_date,
        value=Decimal(high),
        unit="degF",
        role="observation",
        revision_id=revision,
        published_at=published,
        revised_at=revised,
        available_at=receipt.received_at,
        received_at=receipt.received_at,
        ingested_at=receipt.received_at,
        timing_basis="received",
        evidence="Official Weather Company portal daily maxTemp. "
        "Provider issue/revision clocks may be unknown. Availability begins at collection receipt; "
        "not a binary settlement certification.",
        raw_ref="receipt:" + receipt.digest,
        raw_hash=receipt.digest,
    )


class LabelBatch(DomainModel):
    schema_version: str = "weather-label-batch-v1"
    source_dataset: str
    protected_events: tuple[str, ...]
    targets: tuple[LabelTarget, ...] = Field(max_length=2048)
    receipts: tuple[LabelReceipt, ...] = Field(max_length=MAX_DATES)
    parser_version: str = "weather-company-primary-v1"

    @model_validator(mode="after")
    def check(self) -> "LabelBatch":
        if (
            self.schema_version != "weather-label-batch-v1"
            or self.parser_version != "weather-company-primary-v1"
        ):
            raise ValueError("unsupported weather label schema/parser")
        if len({r.url for r in self.receipts}) != len(self.receipts):
            raise ValueError("duplicate weather label source receipt")
        if len({t.event_id for t in self.targets}) != len(self.targets):
            raise ValueError("duplicate weather label target")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.source_dataset):
            raise ValueError("invalid source dataset identity")
        return self

    @property
    def version(self) -> str:
        return scientific_hash(self.model_dump(mode="json"))

    def records(self) -> list[dict[str, Any]]:
        result = []
        for target in self.targets:
            receipt = next(
                (r for r in self.receipts if r.url == URL + target.target_date.isoformat()), None
            )
            observation = None
            refusal = target.refusal or (
                "protected label excluded from acquisition and research"
                if target.event_id in self.protected_events
                else ""
            )
            if not refusal:
                if receipt is None:
                    refusal = "source receipt missing (interrupted or day not complete)"
                else:
                    try:
                        observation = parse_label(target, receipt).model_dump(mode="json")
                    except (ValueError, KeyError, TypeError) as exc:
                        refusal = str(exc)
            result.append(
                {
                    "target": target.model_dump(mode="json"),
                    "observation": observation,
                    "refusal": refusal,
                }
            )
        return result

    def summary(self) -> dict[str, Any]:
        records = self.records()
        return {
            "version": self.version,
            "source_dataset": self.source_dataset,
            "verified_events": sum(r["observation"] is not None for r in records),
            "refused_events": sum(r["observation"] is None for r in records),
            "records": records,
            "receipts": [
                {
                    **r.model_dump(mode="json", exclude={"body_base64"}),
                    "sha256": r.digest,
                    "bytes": len(r.body()),
                }
                for r in self.receipts
            ],
            "submission_enabled": False,
        }


def load_batch(path: Path) -> LabelBatch:
    if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > 24_000_000:
        raise ValueError("unsafe weather label batch")
    batch = LabelBatch.model_validate_json(path.read_bytes())
    if path.stem != batch.version.removeprefix("sha256:"):
        raise ValueError("weather label batch identity mismatch")
    return batch
