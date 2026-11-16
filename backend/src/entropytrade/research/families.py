"""Family adapters: entity resolution, decision schedules and local hypothesis templates.

The orchestration core is family-neutral. A family adapter supplies only typed domain
facts. A family with generic interfaces but no verified sources is never declared ready.
"""

import json
import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Literal

from entropytrade.research.model import DataKind, DecisionPoint, FeatureNeed, RuleSketch

ExecutionNeed = tuple[
    DataKind, str, Literal["issuance", "receipt", "any"], Literal["any", "quote", "order_book"]
]


@dataclass(frozen=True)
class Entity:
    series: str
    entity: str
    name: str
    timezone: str


@dataclass(frozen=True)
class Template:
    template_id: str
    title: str
    rationale: str
    features: tuple[FeatureNeed, ...]
    label: FeatureNeed
    rules: tuple[RuleSketch, ...]
    candidate_models: tuple[str, ...]
    validation_plan: str
    leakage_risks: tuple[str, ...]
    invalidation: tuple[str, ...]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class Family:
    family: str
    readiness: Literal["research_ready", "requirements_only"]
    readiness_note: str
    entities: tuple[Entity, ...]
    aliases: dict[str, tuple[str, ...]]
    schedule: tuple[DecisionPoint, ...]
    timestamp_semantics: str
    execution_needs: tuple[ExecutionNeed, ...]
    templates: tuple[Template, ...]
    models: tuple[str, ...]

    def resolve_universe(self, objective: str, universe: tuple[str, ...]) -> tuple[Entity, ...]:
        known = {e.series: e for e in self.entities}
        if universe:
            unknown = [s for s in universe if s not in known]
            if unknown:
                raise ValueError("unsupported series for this family: " + ", ".join(unknown))
            return tuple(known[s] for s in universe)
        text = objective.casefold()
        named = [
            e
            for e in self.entities
            if any(re.search(r"\b" + re.escape(a) + r"\b", text) for a in self.aliases[e.series])
        ]
        return tuple(named) if named else self.entities[:1]

    def describe(self) -> dict[str, object]:
        return {
            "family": self.family,
            "readiness": self.readiness,
            "readiness_note": self.readiness_note,
            "series": [
                {"series": e.series, "entity": e.entity, "name": e.name, "timezone": e.timezone}
                for e in self.entities
            ],
            "templates": [t.template_id for t in self.templates],
            "models": list(self.models),
        }


def _need(name: str, role: Literal["feature", "label"] = "feature") -> FeatureNeed:
    return FeatureNeed(name=name, role=role)


_WEATHER_LEAKAGE = (
    "A target date's own CLI report or settlement label is published after the day ends "
    "and must never enter that date's decision-time features.",
    "Forecast products issued after the decision time; only issuance clocks at or before "
    "the decision qualify.",
    "Contract rules retrieved after settlement are not proof of the rules known at decision.",
    "Many strikes on one station-day are one dependent outcome; count station-days.",
)
_WEATHER_SPLIT = (
    "Time-ordered fit, calibration and validation partitions by target date with a two-day "
    "embargo; compare Brier score and log loss with the market-implied and climatology "
    "baselines; the protected holdout is never used for selection."
)

WEATHER_TEMPLATES = (
    Template(
        template_id="weather-forecast-bias",
        title="NWS forecast bias against the settlement high",
        rationale=(
            "If official NWS point forecasts of the daytime maximum are biased relative to the "
            "settlement-authority daily high at a station, a bias-corrected forecast could "
            "price threshold contracts differently from the market. NWS CLI reports issued "
            "after each day provide a point-in-time reference for estimating that bias."
        ),
        features=(_need("nws_pfm_max_f"), _need("nws_cli_bias_f")),
        label=_need("settlement_high_f", "label"),
        rules=(RuleSketch(feature="nws_cli_bias_f", op=">", side="yes"),),
        candidate_models=("market_baseline", "climatology", "gaussian_error", "logistic"),
        validation_plan=_WEATHER_SPLIT,
        leakage_risks=_WEATHER_LEAKAGE,
        invalidation=(
            "Bias-corrected probabilities do not beat the market-implied Brier score on the "
            "validation partition.",
            "The estimated bias changes sign between partitions.",
            "Fewer independent station-days than the minimum for the selected depth.",
        ),
        keywords=("bias", "forecast", "settlement", "official"),
    ),
    Template(
        template_id="weather-revision-momentum",
        title="Delayed market adjustment after forecast revisions",
        rationale=(
            "When a new NWS point forecast revises the expected daytime maximum, contract "
            "prices may adjust gradually. A revision observed at decision time could then "
            "predict the direction of the market's subsequent repricing and settlement."
        ),
        features=(_need("nws_pfm_revision_f"), _need("market_implied_probability")),
        label=_need("settlement_high_f", "label"),
        rules=(RuleSketch(feature="nws_pfm_revision_f", op=">", side="yes"),),
        candidate_models=("market_baseline", "logistic", "gradient_boosting"),
        validation_plan=_WEATHER_SPLIT,
        leakage_risks=(
            *_WEATHER_LEAKAGE,
            "Quotes captured after the revision's issuance must not be attributed to an "
            "earlier decision time.",
        ),
        invalidation=(
            "Revision sign does not predict the settlement outcome beyond the market-implied "
            "probability.",
            "No decision-time quotes exist to measure the market's adjustment.",
        ),
        keywords=("revision", "momentum", "update", "adjust"),
    ),
    Template(
        template_id="weather-provider-disagreement",
        title="Market pricing when forecast providers disagree",
        rationale=(
            "When independent forecast providers disagree about the daily maximum, the "
            "market may anchor to one provider. The size of the disagreement may predict "
            "where the market-implied probability is miscalibrated."
        ),
        features=(_need("forecast_provider_disagreement"), _need("market_implied_probability")),
        label=_need("settlement_high_f", "label"),
        rules=(RuleSketch(feature="forecast_provider_disagreement", op=">"),),
        candidate_models=("market_baseline", "logistic"),
        validation_plan=_WEATHER_SPLIT,
        leakage_risks=_WEATHER_LEAKAGE,
        invalidation=(
            "Market calibration does not differ between high- and low-disagreement days.",
        ),
        keywords=("disagree", "provider", "competing", "model"),
    ),
    Template(
        template_id="weather-uncertainty-mispricing",
        title="Mispricing during elevated forecast uncertainty",
        rationale=(
            "Wide ensemble spread signals uncertain outcomes. If market prices understate that "
            "uncertainty, contracts far from the ensemble mean may be underpriced."
        ),
        features=(_need("ensemble_std_f"), _need("market_implied_probability")),
        label=_need("settlement_high_f", "label"),
        rules=(RuleSketch(feature="ensemble_std_f", op=">"),),
        candidate_models=("market_baseline", "gaussian_error"),
        validation_plan=_WEATHER_SPLIT,
        leakage_risks=_WEATHER_LEAKAGE,
        invalidation=("Market calibration error does not grow with ensemble spread.",),
        keywords=("uncertain", "spread", "ensemble", "volatil"),
    ),
    Template(
        template_id="weather-near-expiry",
        title="Market reaction to observations near expiration",
        rationale=(
            "Late in the target day, observed temperatures constrain the remaining possible "
            "daily maximum. Prices may lag the information in the latest observations."
        ),
        features=(
            _need("observed_temperature_f"),
            _need("hours_to_close"),
            _need("market_implied_probability"),
        ),
        label=_need("settlement_high_f", "label"),
        rules=(RuleSketch(feature="hours_to_close", op="<", side="either"),),
        candidate_models=("market_baseline", "logistic"),
        validation_plan=_WEATHER_SPLIT,
        leakage_risks=(
            *_WEATHER_LEAKAGE,
            "Intraday observations must carry receipt clocks at or before the decision.",
        ),
        invalidation=("Prices already reflect the latest observation within one poll.",),
        keywords=("expir", "observ", "late", "close", "intraday"),
    ),
)

WEATHER_EXECUTION: tuple[ExecutionNeed, ...] = (
    (DataKind.MARKET_CONTRACTS, "contract_terms", "any", "any"),
    (DataKind.DECISION_QUOTES, "yes_quotes", "receipt", "quote"),
    (DataKind.FEE_SCHEDULE, "fee_schedule", "any", "any"),
)

_CITY_ALIASES = {
    "KXHIGHPHIL": ("philadelphia", "philly", "phl"),
    "KXHIGHCHI": ("chicago", "midway", "chi"),
    "KXHIGHNY": ("new york", "nyc", "manhattan", "central park"),
    "KXHIGHTDAL": ("dallas", "dfw", "fort worth"),
}


def weather_family(repo: Path) -> Family:
    """Stations come from the canonical forward-collector configuration."""
    config = json.loads((repo / "configs/data/weather-forward.json").read_text())
    entities = tuple(
        Entity(
            series=str(item["series"]),
            entity=str(item["station"]),
            name=str(item["name"]),
            timezone=str(item["timezone"]),
        )
        for item in config["locations"]
    )
    return Family(
        family="weather",
        readiness="research_ready",
        readiness_note=(
            "Daily-high temperature contracts. Historical NWS products and settlement-authority "
            "labels are acquirable for verified stations; decision-time quotes are prospective."
        ),
        entities=entities,
        aliases={e.series: _CITY_ALIASES.get(e.series, (e.name.casefold(),)) for e in entities},
        schedule=(
            DecisionPoint(day_offset=-1, local_time=time(18, 0)),
            DecisionPoint(day_offset=0, local_time=time(10, 0)),
        ),
        timestamp_semantics=(
            "Decision times are in the station's local timezone. A forecast qualifies only if "
            "its issuance clock is at or before the decision; a reference observation only if "
            "its report was issued by then. Settlement labels are outcomes, never features."
        ),
        execution_needs=WEATHER_EXECUTION,
        templates=WEATHER_TEMPLATES,
        models=("market_baseline", "climatology", "gaussian_error", "logistic", "ridge"),
    )


BITCOIN_TEMPLATES = (
    Template(
        template_id="bitcoin-spot-distance",
        title="Spot distance to strike against implied probability",
        rationale=(
            "Near expiration, the distance between the BTC spot price and a contract's strike "
            "largely determines the outcome. Market prices may lag fast spot moves."
        ),
        features=(
            _need("spot_usd"),
            _need("hours_to_close"),
            _need("market_implied_probability"),
        ),
        label=_need("market_result", "label"),
        rules=(RuleSketch(feature="hours_to_close", op="<"),),
        candidate_models=("market_baseline", "logistic"),
        validation_plan=(
            "Time-ordered partitions by expiration with an embargo; compare with the "
            "market-implied baseline."
        ),
        leakage_risks=(
            "Spot is a covariate, never a settlement label; the settlement index is unverified.",
            "Hourly contracts on one expiration share one outcome path.",
        ),
        invalidation=("No improvement over market-implied Brier score.",),
        keywords=("bitcoin", "btc", "spot", "crypto"),
    ),
)


def bitcoin_family() -> Family:
    return Family(
        family="bitcoin",
        readiness="requirements_only",
        readiness_note=(
            "Generic interfaces only. No verified settlement-index source or historical "
            "decision-time evidence is registered, so the family is not research-ready."
        ),
        entities=(Entity(series="KXBTCD", entity="KXBTCD", name="Bitcoin daily", timezone="UTC"),),
        aliases={"KXBTCD": ("bitcoin", "btc")},
        schedule=(DecisionPoint(day_offset=0, local_time=time(12, 0)),),
        timestamp_semantics=(
            "Decision times are UTC. Spot covariates qualify only with receipt clocks at or "
            "before the decision."
        ),
        execution_needs=WEATHER_EXECUTION,
        templates=BITCOIN_TEMPLATES,
        models=("market_baseline", "logistic"),
    )


def load_families(repo: Path) -> dict[str, Family]:
    return {"weather": weather_family(repo), "bitcoin": bitcoin_family()}
