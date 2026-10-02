"""On-disk feature manifest and prediction records for the CLI rescore.

Each record uses only values that were available at 15:00 UTC on that valid
day. The day's own CLI high is the outcome, not a feature. Bid, ask, and net
edge stay empty because the stored tape has no sized book. This module does
not open a socket.
"""

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.ids import canonical_json, content_hash
from entropytrade.domain.market import Strike
from entropytrade.domain.observations import Forecast
from entropytrade.domain.signals import PredictionRecord
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.weather.cli_observations import CliLabel, load_comparison
from entropytrade.weather.probability import (
    InsufficientHistoryError,
    calibrate,
    climatology_hit_rate,
    raw_forecast_probability,
)
from entropytrade.weather.settlement_score import load_stored_forecasts

_STRIKE = Strike(strike_type=StrikeType.BETWEEN, floor=Decimal(80), cap=Decimal(81))

FEATURE_VERSION = "cli-rescore-features-v1"
_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_MANIFEST = Path("features/cli-rescore-manifest.json")
_PREDICTIONS = Path("features/cli-rescore-predictions.json")


def load_feature_manifest(root: Path) -> Mapping[str, object]:
    """Read the committed manifest and check it matches a fresh build."""
    stored = _mapping(_read(root / _MANIFEST), "manifest")
    payload = build_feature_payload(root)
    digest = content_hash(payload)
    if stored.get("manifest_hash") != digest:
        raise ValueError("the on-disk feature manifest does not match the stored rows")
    return stored


def load_prediction_records(root: Path) -> tuple[PredictionRecord, ...]:
    """Read the committed prediction records and check them against the rows."""
    stored = _mapping(_read(root / _PREDICTIONS), "predictions")
    fresh = build_prediction_records(root)
    if stored.get("source_data_manifest_hash") != fresh[0].source_data_manifest_hash:
        raise ValueError("prediction records cite a different feature manifest")
    rows = _seq(stored.get("records"), "records")
    if len(rows) != len(fresh):
        raise ValueError("prediction record count does not match the stored rows")
    for raw, record in zip(rows, fresh, strict=True):
        body = _mapping(raw, "record")
        if body.get("prediction_id") != str(record.prediction_id):
            raise ValueError("a stored prediction id does not match the rows")
        if body.get("feature_vector_hash") != record.feature_vector_hash:
            raise ValueError("a stored feature hash does not match the rows")
    return fresh


def build_feature_payload(root: Path) -> dict[str, object]:
    """Feature rows known at each decision. Outcomes are not included."""
    labels, _comparison = load_comparison(root)
    forecasts = {item.valid_from.date(): item for item in load_stored_forecasts(root)}
    tickers = _b805_by_day(root)
    rows: list[dict[str, object]] = []
    for label, forecast, decision, climate in _decisions(labels, forecasts):
        raw = raw_forecast_probability(forecast.value, _STRIKE)
        rows.append(
            {
                "climatology": climate,
                "decision_time": decision,
                "forecast_available_at": forecast.available_at,
                "forecast_high_f": forecast.value,
                "market_listed": label.valid_on in tickers,
                "market_ticker": _ticker(tickers, label),
                "raw_probability": raw,
                "sized_book": False,
                "station": "CLIPHL",
                "valid_on": label.valid_on,
            }
        )
    return {
        "decision": "15:00:00Z",
        "features": (
            "forecast_high",
            "point_in_time_climatology",
        ),
        "sources": _sources(root),
        "strike": _strike_name(_STRIKE),
        "version": FEATURE_VERSION,
        "rows": tuple(rows),
    }


def build_prediction_records(root: Path) -> tuple[PredictionRecord, ...]:
    """One record per rescore probability day. No bid, ask, or net edge."""
    payload = build_feature_payload(root)
    digest = content_hash(payload)
    labels, _comparison = load_comparison(root)
    forecasts = {item.valid_from.date(): item for item in load_stored_forecasts(root)}
    tickers = _b805_by_day(root)
    records: list[PredictionRecord] = []
    for label, forecast, decision, climate in _decisions(labels, forecasts):
        raw = raw_forecast_probability(forecast.value, _STRIKE)
        blended = calibrate(raw, climate)
        listed = label.valid_on in tickers
        feature_hash = content_hash(
            {
                "climatology": climate,
                "decision_time": decision,
                "forecast_available_at": forecast.available_at,
                "forecast_high_f": forecast.value,
                "market_listed": listed,
                "raw_probability": raw,
                "station": "CLIPHL",
                "valid_on": label.valid_on,
            }
        )
        records.append(
            PredictionRecord(
                prediction_id=uuid5(_NAMESPACE, f"cli-rescore:{label.valid_on.isoformat()}"),
                strategy_id="cli-aligned",
                strategy_version=1,
                model_version="previous_day1",
                calibration_version=None,
                market_ticker=_ticker(tickers, label),
                decision_time=decision,
                feature_vector_hash=feature_hash,
                source_data_manifest_hash=digest,
                probability_yes=raw,
                uncertainty=abs(raw - blended),
                market_yes_bid=None,
                market_yes_ask=None,
                net_edge_estimate=None,
            )
        )
    return tuple(records)


def write_provenance(root: Path) -> None:
    """Write the manifest and prediction records next to the public data."""
    payload = build_feature_payload(root)
    digest = content_hash(payload)
    document = dict(payload)
    document["manifest_hash"] = digest
    _write(root / _MANIFEST, document)
    records = build_prediction_records(root)
    _write(
        root / _PREDICTIONS,
        {
            "records": tuple(record.model_dump(mode="json") for record in records),
            "source_data_manifest_hash": digest,
        },
    )


def _decisions(
    labels: tuple[CliLabel, ...],
    forecasts: Mapping[date, Forecast],
) -> tuple[tuple[CliLabel, Forecast, datetime, Decimal], ...]:
    prior = [(label.available_at, label.high_f) for label in labels]
    found: list[tuple[CliLabel, Forecast, datetime, Decimal]] = []
    for label in labels:
        forecast = forecasts.get(label.valid_on)
        if forecast is None or forecast.available_at >= label.available_at:
            continue
        decision = datetime(
            label.valid_on.year,
            label.valid_on.month,
            label.valid_on.day,
            15,
            tzinfo=UTC,
        )
        try:
            climate = climatology_hit_rate(prior, decision_time=decision, strike=_STRIKE)
        except InsufficientHistoryError:
            continue
        found.append((label, forecast, decision, climate))
    return tuple(found)


def _sources(root: Path) -> tuple[dict[str, str], ...]:
    public = _mapping(_read(root / "manifest.json"), "public manifest")
    iem = _mapping(_read(root / "iem" / "manifest.json"), "iem manifest")
    window = _mapping(
        _read(root / "kalshi-public" / "cli-window" / "manifest.json"),
        "cli-window manifest",
    )
    return (
        _source(public, "open-meteo/previous-runs.json"),
        _source(iem, "iem/cliphl-afos.txt"),
        {
            "available_at": _text(window.get("fetched_at"), "fetched_at"),
            "endpoint": _text(window.get("host"), "host"),
            "path": "kalshi-public/cli-window/manifest.json",
        },
    )


def _source(manifest: Mapping[str, object], path: str) -> dict[str, str]:
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        if item.get("path") != path:
            continue
        stamp = item.get("fetched_at") or manifest.get("fetched_at")
        return {
            "available_at": _text(stamp, "fetched_at"),
            "endpoint": _text(item.get("url"), "url"),
            "path": path,
        }
    raise ValueError(f"{path} is not in the manifest")


def _b805_by_day(root: Path) -> dict[date, str]:
    manifest = _mapping(
        _read(root / "kalshi-public" / "cli-window" / "manifest.json"),
        "cli-window manifest",
    )
    found: dict[date, str] = {}
    for call in _seq(manifest.get("calls"), "calls"):
        item = _mapping(call, "call")
        url = item.get("url")
        if not isinstance(url, str) or "/orderbook" not in url:
            continue
        ticker = url.split("/markets/", maxsplit=1)[-1].split("/", maxsplit=1)[0]
        if not ticker.endswith("-B80.5"):
            continue
        valid_on = ticker_target_date(ticker)
        if valid_on is not None:
            found[valid_on] = ticker
    return found


def _ticker(tickers: Mapping[date, str], label: CliLabel) -> str:
    """Stored B80.5 ticker, or the stored series when that strike was not listed."""
    return tickers.get(label.valid_on, "KXHIGHPHIL")


def _strike_name(strike: Strike) -> str:
    return f"{strike.strike_type.value}:{strike.floor}:{strike.cap}"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _read(path: Path) -> object:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    return payload


def _mapping(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} is not an object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{what} has a non-string key")
        mapped[key] = item
    return mapped


def _text(value: object, what: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{what} is not text")
    return value


def _seq(value: object, what: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a list")
    return tuple(value)
