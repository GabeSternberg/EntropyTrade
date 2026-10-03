"""Prediction records for the scored revision-bracket decisions.

One record is one train or validation day that had both vintages at or
before 15:00 UTC and before the label. The holdout is not recorded.
Probability is 1 when revision >= 2°F and 0 otherwise. That is the frozen
fire rule. Bid, ask, and net edge stay empty. A print is not a quote.
This module does not open a socket.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from entropytrade.domain.ids import canonical_json, content_hash
from entropytrade.domain.signals import PredictionRecord
from entropytrade.weather.revision_bracket import (
    NO_STORED_BRACKET,
    RULE_NAME,
    RevisionDecision,
    SkippedRevisionDay,
    load_revision_decisions,
    load_skipped_revision_days,
)
from entropytrade.weather.revision_rule import _decision

VERSION = "revision-bracket-records-v1"
_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_MANIFEST = Path("features/revision-bracket-manifest.json")
_PREDICTIONS = Path("features/revision-bracket-predictions.json")
_FEATURES = ("later_max", "earlier_max", "revision")


def build_revision_payload(root: Path) -> dict[str, object]:
    """The source manifest. Holdout days are absent. Equity is absent."""
    rows = tuple(_row(item) for item in load_revision_decisions(root))
    return {
        "decision": "15:00:00Z",
        "features": _FEATURES,
        "holdout_recorded": False,
        "promoted": False,
        "rows": rows,
        "rule": RULE_NAME,
        "version": VERSION,
    }


def build_revision_records(root: Path) -> tuple[PredictionRecord, ...]:
    """One record per decision. No bid, ask, or net edge."""
    payload = build_revision_payload(root)
    digest = content_hash(payload)
    rows = payload["rows"]
    if not isinstance(rows, tuple):
        raise ValueError("revision rows are not a tuple")
    records: list[PredictionRecord] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("a revision row is not an object")
        records.append(_record(raw, digest))
    return tuple(records)


def load_revision_records(root: Path) -> tuple[PredictionRecord, ...]:
    """Read the committed records and refuse a file that does not match a rebuild."""
    fresh = build_revision_records(root)
    payload = build_revision_payload(root)
    digest = content_hash(payload)
    stored = _read(root / _PREDICTIONS)
    expected = {
        "holdout_recorded": False,
        "promoted": False,
        "records": tuple(record.model_dump(mode="json") for record in fresh),
        "source_data_manifest_hash": digest,
    }
    if canonical_json(stored) != canonical_json(expected):
        raise ValueError("the stored revision records do not match a rebuild")
    manifest = _read(root / _MANIFEST)
    document = dict(payload)
    document["manifest_hash"] = digest
    if canonical_json(manifest) != canonical_json(document):
        raise ValueError("the stored revision manifest does not match a rebuild")
    return fresh


def write_revision_records(root: Path) -> None:
    """Write the manifest and prediction records next to the public data."""
    payload = build_revision_payload(root)
    digest = content_hash(payload)
    document = dict(payload)
    document["manifest_hash"] = digest
    _write(root / _MANIFEST, document)
    records = build_revision_records(root)
    _write(
        root / _PREDICTIONS,
        {
            "holdout_recorded": False,
            "promoted": False,
            "records": tuple(record.model_dump(mode="json") for record in records),
            "source_data_manifest_hash": digest,
        },
    )


def skipped_note(root: Path) -> str:
    """Name why train and validation days were left out. The holdout is not listed."""
    skipped = load_skipped_revision_days(root)
    late = _reason_count(skipped, "vintage clock is after 15:00 UTC")
    labeled = _reason_count(skipped, "vintage clock is at or after the label")
    missing = _reason_count(skipped, "a vintage max is missing")
    if late + labeled + missing != len(skipped):
        raise ValueError("a skipped day has an unknown reason")
    return " ".join(
        (
            f"Train and validation days left out of the revision records: {len(skipped)}.",
            f"Vintage clock after 15:00 UTC: {late}.",
            f"Vintage clock at or after the label: {labeled}.",
            f"A vintage max is missing: {missing}.",
            "The holdout is not listed.",
            "Nothing was promoted.",
        )
    )


def records_note(root: Path) -> str:
    """One scan-note sentence. It does not score the holdout."""
    records = build_revision_records(root)
    fires = sum(1 for record in records if record.probability_yes == Decimal(1))
    return " ".join(
        (
            f"Revision-bracket prediction records: {len(records)} train and validation days.",
            f"Fires: {fires}.",
            "The holdout is not recorded.",
            "Bid, ask, and net edge are empty.",
            "Nothing was promoted.",
        )
    )


def _reason_count(skipped: tuple[SkippedRevisionDay, ...], reason: str) -> int:
    return sum(1 for item in skipped if item.reason == reason)


def _row(item: RevisionDecision) -> dict[str, object]:
    if item.fold not in {"train", "validation"}:
        raise ValueError("a holdout day was recorded")
    if item.ticker == "":
        raise ValueError("a revision decision has no ticker")
    return {
        "earlier_max": item.earlier_max,
        "fired": item.fired,
        "fold": item.fold,
        "later_max": item.later_max,
        "place": item.place,
        "revision": item.revision,
        "rule": RULE_NAME,
        "ticker": item.ticker,
        "valid_on": item.valid_on.isoformat(),
    }


def _record(row: dict[str, object], digest: str) -> PredictionRecord:
    place = _text(row.get("place"), "place")
    valid_on = date.fromisoformat(_text(row.get("valid_on"), "valid_on"))
    fired = row.get("fired")
    if not isinstance(fired, bool):
        raise ValueError("fired is not a boolean")
    ticker = _text(row.get("ticker"), "ticker")
    if not fired and ticker != NO_STORED_BRACKET:
        raise ValueError("a day that did not fire names a market")
    return PredictionRecord(
        prediction_id=uuid5(_NAMESPACE, f"{RULE_NAME}:{place}:{valid_on.isoformat()}"),
        strategy_id=RULE_NAME,
        strategy_version=1,
        model_version="previous_day1-minus-previous_day2",
        calibration_version=None,
        market_ticker=ticker,
        decision_time=_decision(valid_on),
        feature_vector_hash=content_hash(_feature_vector(row)),
        source_data_manifest_hash=digest,
        probability_yes=Decimal(1) if fired else Decimal(0),
        uncertainty=None,
        market_yes_bid=None,
        market_yes_ask=None,
        net_edge_estimate=None,
    )


def _feature_vector(row: dict[str, object]) -> dict[str, object]:
    names = ("earlier_max", "later_max", "place", "revision", "rule", "valid_on")
    return {name: row[name] for name in names}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _read(path: Path) -> object:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return payload


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value
