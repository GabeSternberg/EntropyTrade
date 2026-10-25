"""Feature-family definitions and hashes for scientific floating point artifacts."""

import json
from dataclasses import asdict, dataclass

from entropytrade.domain.ids import content_hash


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    version: str
    unit: str
    source_requirements: tuple[str, ...]
    transformation: str
    missing_behavior: str = "null; never fill in source data"
    availability: str = "only evidence available at or before decision"
    dtype: str = "float64"
    dependencies: tuple[str, ...] = ()


FEATURES = (
    FeatureDefinition(
        "forecast_high_f",
        "1",
        "degF",
        ("forecast",),
        "mean of latest full-local-day hourly maximum proxies per provider/model",
    ),
    FeatureDefinition(
        "revision_f",
        "1",
        "degF",
        ("two distinct forecast vintages",),
        "mean latest minus preceding maximum per model; distinct receipt/revision required",
    ),
    FeatureDefinition(
        "model_disagreement_f",
        "1",
        "degF",
        ("two forecast models",),
        "population standard deviation of model maximum proxies",
    ),
    FeatureDefinition("ensemble_mean_f", "1", "degF", ("ensemble members",), "mean member maxima"),
    FeatureDefinition(
        "ensemble_std_f", "1", "degF", ("ensemble members",), "population member spread"
    ),
    FeatureDefinition(
        "station_bias_f",
        "1",
        "degF",
        ("prior verified settlement highs",),
        "mean prior scalar target minus its frozen decision-time forecast",
        dependencies=("forecast_high_f",),
    ),
    FeatureDefinition(
        "observed_temperature_f",
        "1",
        "degF",
        ("observed temperature",),
        "last observation valid and available by decision",
    ),
    FeatureDefinition("hours_to_close", "1", "hour", ("contract rules",), "close minus decision"),
    FeatureDefinition("season_sin", "1", "dimensionless", ("target local date",), "annual sine"),
    FeatureDefinition("season_cos", "1", "dimensionless", ("target local date",), "annual cosine"),
)
FEATURE_NAMES = tuple(f.name for f in FEATURES)


def scientific_hash(value: object) -> str:
    # Money hashing remains Decimal-only in domain.ids; scientific metrics have explicit floats.
    return content_hash(
        {
            "scientific_json": json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        }
    )


def feature_schema() -> dict[str, object]:
    payload: dict[str, object] = json.loads(
        json.dumps(
            {"features": [asdict(f) for f in FEATURES], "schema_version": "weather-features-v1"}
        )
    )
    return payload
