"""Small independent weather/model evidence builders for R2 invariant tests."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from entropytrade.data.schema import Location, Observation

LOCATION = Location(
    name="Philadelphia fixture",
    series="FIXPHL",
    station="KPHL",
    timezone="America/New_York",
    latitude="39.87",
    longitude="-75.24",
)


def observation(
    day: date,
    value: int,
    available: datetime,
    *,
    revision: str = "one",
    variable: str = "daily_high_f",
    source: str = "fixture-gfs",
    role: str = "feature",
) -> Observation:
    return Observation.model_validate(
        {
            "source_id": source,
            "model": source,
            "entity_id": LOCATION.station,
            "variable": variable,
            "valid_on": day,
            "value": Decimal(value),
            "unit": "degF",
            "available_at": available,
            "received_at": available,
            "timing_basis": "received",
            "revision_id": revision,
            "raw_ref": "fixture:" + revision,
            "raw_hash": revision,
            "role": role,
            "evidence": "controlled test receipt",
        }
    )


def row(day: date, *, decision: datetime | None = None) -> dict[str, Any]:
    decision = decision or datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=15)
    return {
        "event_id": "FIX-" + day.isoformat(),
        "market_ticker": "FIX-" + day.isoformat() + "-B70",
        "decision_time": decision.isoformat(),
        "target_date": day.isoformat(),
        "station": "KPHL",
        "city": LOCATION.name,
        "strike_json": json.dumps({"strike_type": "greater", "floor": "70"}),
        "rules_json": json.dumps(
            {
                "settlement_basis": "contract_text",
                "rules_primary": "Integer Fahrenheit high per The Weather Company",
                "settlement_sources": [{"name": "The Weather Company"}],
            }
        ),
        "rules_known_at_decision": True,
        "contract_existed_at_decision": True,
        "provenance_json": json.dumps(
            {
                "metadata": {
                    "market": {
                        "market_type": "binary",
                        "close_time": (decision + timedelta(hours=12)).isoformat(),
                    }
                }
            }
        ),
        "outcome": "yes",
        "outcome_available_at": (decision + timedelta(days=1)).isoformat(),
        "market_state_json": None,
    }


def open_meteo_body(day: date, *, temperature: int = 70, generated: int = 1) -> bytes:
    start = datetime.combine(day, datetime.min.time(), UTC)
    return json.dumps(
        {
            "latitude": 39.87,
            "longitude": -75.24,
            "utc_offset_seconds": 0,
            "generationtime_ms": generated,
            "hourly_units": {"temperature_2m": "°F"},
            "hourly": {
                "time": [
                    (start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(48)
                ],
                "temperature_2m": [temperature] * 48,
            },
        }
    ).encode()
