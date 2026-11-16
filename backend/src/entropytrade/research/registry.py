"""Family-neutral feature registry.

Every feature a strategy may reference has a stable identifier, version, typed inputs,
availability and missing-value semantics, and a content hash of its definition. Names are
resolved exactly or through an explicitly reviewed alias; an unknown name is never mapped
to a semantically different feature.
"""

from typing import Literal

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.features.registry import FEATURES as WEATHER_PIPELINE_FEATURES
from entropytrade.features.registry import scientific_hash
from entropytrade.research.model import NAME, DataKind

Transform = Literal[
    "latest_vintage",
    "vintage_revision",
    "trailing_mean_error",
    "label_value",
    "provider_spread",
    "weather_pipeline",
    "contract_terms",
    "calendar",
    "quote_mid",
    "quote_spread",
    "book_depth",
    "covariate_latest",
]


class FeatureInput(DomainModel):
    kind: DataKind
    variable: str = Field(pattern=NAME)
    clock: Literal["issuance", "receipt", "any"]
    fidelity: Literal["any", "quote", "order_book"] = "any"
    min_vintages: int = Field(default=1, ge=1, le=4)
    min_sources: int = Field(default=1, ge=1, le=4)
    blocking: Literal["predictive", "execution"] = "predictive"


class FeatureDefinition(DomainModel):
    feature_id: str = Field(pattern=NAME)
    version: str = Field(min_length=1, max_length=20)
    family: Literal["weather", "market", "bitcoin", "calendar"]
    role: Literal["feature", "label"] = "feature"
    dtype: Literal["float64", "int64", "bool"] = "float64"
    unit: str
    entity: Literal["station_day", "contract_decision", "event_decision", "series_decision"]
    inputs: tuple[FeatureInput, ...]
    transform: Transform
    params: dict[str, int | str] = Field(default_factory=dict)
    availability: str = "max(input availability clocks) must be at or before the decision time"
    missing: str = "null; never imputed, carried forward from a later vintage or zero-filled"
    validation: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    materializer: Literal["research", "weather_pipeline", "not_implemented"]
    description: str

    @property
    def definition_hash(self) -> str:
        return scientific_hash(self.model_dump(mode="json"))


class Resolution(DomainModel):
    requested: str
    feature_id: str | None
    via: Literal["exact", "alias", "unregistered"]
    definition_hash: str | None = None
    version: str | None = None


_PFM_MAX = FeatureInput(kind=DataKind.FORECAST_VINTAGES, variable="daytime_max_f", clock="issuance")
_CLI_HIGH = FeatureInput(
    kind=DataKind.REFERENCE_OBSERVATIONS, variable="daily_high_f", clock="issuance"
)
_QUOTES = FeatureInput(
    kind=DataKind.DECISION_QUOTES,
    variable="yes_quotes",
    clock="receipt",
    fidelity="quote",
    blocking="execution",
)
_CONTRACTS = FeatureInput(kind=DataKind.MARKET_CONTRACTS, variable="contract_terms", clock="any")
_HOURLY = FeatureInput(
    kind=DataKind.FORECAST_VINTAGES, variable="hourly_temperature_f", clock="receipt"
)
_PIT = ("every input availability clock is at or before the decision time",)

RESEARCH_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        feature_id="nws_pfm_max_f",
        version="1",
        family="weather",
        unit="degF",
        entity="station_day",
        inputs=(_PFM_MAX,),
        transform="latest_vintage",
        validation=(*_PIT, "value within -60..140 degF"),
        materializer="research",
        description=(
            "NWS Point Forecast Matrix daytime (7am-7pm local) maximum for the target local "
            "date, from the latest product issued at or before the decision time. A forecast "
            "of the daytime maximum, not the calendar-day settlement high."
        ),
    ),
    FeatureDefinition(
        feature_id="nws_pfm_revision_f",
        version="1",
        family="weather",
        unit="degF",
        entity="station_day",
        inputs=(
            FeatureInput(
                kind=DataKind.FORECAST_REVISIONS,
                variable="daytime_max_f",
                clock="issuance",
                min_vintages=2,
            ),
        ),
        transform="vintage_revision",
        validation=(*_PIT, "two distinct issuance clocks"),
        materializer="research",
        description=(
            "Latest minus the immediately preceding PFM daytime maximum for the same target "
            "date; both products issued at or before the decision time."
        ),
    ),
    FeatureDefinition(
        feature_id="nws_cli_bias_f",
        version="1",
        family="weather",
        unit="degF",
        entity="station_day",
        inputs=(_PFM_MAX, _CLI_HIGH),
        transform="trailing_mean_error",
        params={"window_days": 21, "min_count": 5},
        validation=(*_PIT, "only prior target dates whose CLI report was issued by decision"),
        materializer="research",
        description=(
            "Mean of (NWS CLI reported high - PFM daytime maximum issued at the same relative "
            "decision time) over earlier target dates whose CLI final report had been issued "
            "by the decision time. CLI is a reference observation, not the settlement source."
        ),
    ),
    FeatureDefinition(
        feature_id="settlement_high_f",
        version="1",
        family="weather",
        role="label",
        unit="degF",
        entity="station_day",
        inputs=(
            FeatureInput(kind=DataKind.SETTLEMENT_LABELS, variable="daily_high_f", clock="receipt"),
        ),
        transform="label_value",
        availability="outcome label; never a decision-time feature",
        validation=("official/revised source status only", "station and date match contract"),
        materializer="research",
        description=(
            "Settlement-authority daily high from the source named in the contract text. "
            "Availability begins at collection receipt."
        ),
    ),
    FeatureDefinition(
        feature_id="forecast_provider_disagreement",
        version="1",
        family="weather",
        unit="degF",
        entity="station_day",
        inputs=(
            FeatureInput(
                kind=DataKind.FORECAST_VINTAGES,
                variable="hourly_temperature_f",
                clock="receipt",
                min_sources=2,
            ),
        ),
        transform="provider_spread",
        validation=(*_PIT, "two providers with receipt clocks"),
        materializer="weather_pipeline",
        description=(
            "Absolute difference between two providers' full-day hourly-maximum forecasts "
            "received by the decision time."
        ),
    ),
    FeatureDefinition(
        feature_id="market_implied_probability",
        version="1",
        family="market",
        unit="probability",
        entity="contract_decision",
        inputs=(_QUOTES,),
        transform="quote_mid",
        validation=("two-sided book received at or before decision", "bid < ask"),
        materializer="not_implemented",
        description="Midpoint of the YES bid and ask captured at or before the decision time.",
    ),
    FeatureDefinition(
        feature_id="bid_ask_spread",
        version="1",
        family="market",
        unit="probability",
        entity="contract_decision",
        inputs=(_QUOTES,),
        transform="quote_spread",
        validation=("two-sided book received at or before decision",),
        materializer="not_implemented",
        description="YES ask minus YES bid at the decision time.",
    ),
    FeatureDefinition(
        feature_id="order_book_depth",
        version="1",
        family="market",
        unit="contracts",
        entity="contract_decision",
        inputs=(
            FeatureInput(
                kind=DataKind.ORDER_BOOK_DEPTH,
                variable="yes_book",
                clock="receipt",
                fidelity="order_book",
                blocking="execution",
            ),
        ),
        transform="book_depth",
        materializer="not_implemented",
        description="Contracts available within one cent of the best price at decision.",
    ),
    FeatureDefinition(
        feature_id="market_result",
        version="1",
        family="market",
        role="label",
        dtype="bool",
        unit="outcome",
        entity="contract_decision",
        inputs=(
            FeatureInput(
                kind=DataKind.SETTLEMENT_LABELS, variable="binary_result", clock="receipt"
            ),
        ),
        transform="label_value",
        availability="outcome label; never a decision-time feature",
        validation=("finalized exchange result with a receipt clock",),
        materializer="not_implemented",
        description="Official finalized contract result from the exchange.",
    ),
    FeatureDefinition(
        feature_id="spot_usd",
        version="1",
        family="bitcoin",
        unit="USD",
        entity="series_decision",
        inputs=(FeatureInput(kind=DataKind.COVARIATE_SERIES, variable="btc_usd", clock="receipt"),),
        transform="covariate_latest",
        materializer="not_implemented",
        description="Latest fresh BTC-USD trade received by the decision time; a covariate.",
    ),
)


def _pipeline(definition: object) -> FeatureDefinition:
    """Describe an existing weather-pipeline feature; its code remains the materializer."""
    from entropytrade.features.registry import FeatureDefinition as Legacy

    if not isinstance(definition, Legacy):
        raise TypeError("expected a weather pipeline feature definition")
    inputs: dict[str, tuple[FeatureInput, ...]] = {
        "forecast_high_f": (_HOURLY,),
        "revision_f": (
            FeatureInput(
                kind=DataKind.FORECAST_REVISIONS,
                variable="hourly_temperature_f",
                clock="receipt",
                min_vintages=2,
            ),
        ),
        "model_disagreement_f": (_HOURLY.revalidated(min_sources=2),),
        "ensemble_mean_f": (
            FeatureInput(
                kind=DataKind.FORECAST_VINTAGES, variable="ensemble_member_f", clock="receipt"
            ),
        ),
        "ensemble_std_f": (
            FeatureInput(
                kind=DataKind.FORECAST_VINTAGES, variable="ensemble_member_f", clock="receipt"
            ),
        ),
        "station_bias_f": (
            _HOURLY,
            FeatureInput(kind=DataKind.SETTLEMENT_LABELS, variable="daily_high_f", clock="receipt"),
        ),
        "observed_temperature_f": (
            FeatureInput(
                kind=DataKind.INTRADAY_OBSERVATIONS, variable="temperature_f", clock="receipt"
            ),
        ),
        "hours_to_close": (_CONTRACTS,),
        "season_sin": (),
        "season_cos": (),
    }
    name = definition.name
    family: Literal["weather", "market", "calendar"] = (
        "calendar"
        if name.startswith("season_")
        else "market"
        if name == "hours_to_close"
        else "weather"
    )
    return FeatureDefinition(
        feature_id=name,
        version=definition.version,
        family=family,
        unit=definition.unit,
        entity="contract_decision" if name == "hours_to_close" else "station_day",
        inputs=inputs[name],
        transform=(
            "calendar"
            if family == "calendar"
            else "contract_terms"
            if name == "hours_to_close"
            else "weather_pipeline"
        ),
        availability=definition.availability,
        missing=definition.missing_behavior,
        validation=_PIT,
        aliases=("forecast_revision_f",) if name == "revision_f" else (),
        materializer="weather_pipeline",
        description=definition.transformation,
    )


def builtin_features() -> tuple[FeatureDefinition, ...]:
    definitions = (*(_pipeline(d) for d in WEATHER_PIPELINE_FEATURES), *RESEARCH_FEATURES)
    names = [d.feature_id for d in definitions]
    aliases = [a for d in definitions for a in d.aliases]
    if (
        len(set(names)) != len(names)
        or set(names) & set(aliases)
        or len(set(aliases)) != len(aliases)
    ):
        raise ValueError("feature identifiers and aliases must be unique")
    return definitions


class FeatureRegistry:
    """Exact or reviewed-alias resolution only. Unknown names stay unregistered."""

    def __init__(self, definitions: tuple[FeatureDefinition, ...] | None = None) -> None:
        self.definitions = {d.feature_id: d for d in definitions or builtin_features()}
        self.aliases = {a: d.feature_id for d in self.definitions.values() for a in d.aliases}

    def resolve(self, name: str) -> Resolution:
        if name in self.definitions:
            found = self.definitions[name]
            via: Literal["exact", "alias", "unregistered"] = "exact"
        elif name in self.aliases:
            found = self.definitions[self.aliases[name]]
            via = "alias"
        else:
            return Resolution(requested=name, feature_id=None, via="unregistered")
        return Resolution(
            requested=name,
            feature_id=found.feature_id,
            via=via,
            definition_hash=found.definition_hash,
            version=found.version,
        )

    def get(self, feature_id: str) -> FeatureDefinition:
        return self.definitions[feature_id]

    def catalog(self) -> list[dict[str, object]]:
        return [
            {**d.model_dump(mode="json"), "definition_hash": d.definition_hash}
            for d in sorted(self.definitions.values(), key=lambda item: item.feature_id)
        ]
