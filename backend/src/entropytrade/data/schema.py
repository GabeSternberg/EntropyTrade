"""Input contracts for reusable daily-high datasets. Unknown clocks remain unknown."""

from datetime import UTC, date, datetime
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.market import Market
from entropytrade.domain.numeric import ExactDecimal
from entropytrade.domain.time import UtcDatetime


class Location(DomainModel):
    name: str
    series: str
    station: str
    timezone: str
    latitude: str | None = None
    longitude: str | None = None
    forecast_file: str | None = None


class DatasetConfig(DomainModel):
    locations: tuple[Location, ...] = Field(min_length=1)
    start: date
    end: date
    decision_utc: tuple[str, ...] = ("15:00",)
    max_age_seconds: int = Field(default=300, ge=0)
    sources: tuple[str, ...] = ("kalshi", "open-meteo", "nws")

    @model_validator(mode="after")
    def check_schedule(self) -> Self:
        if self.end < self.start or (self.end - self.start).days > 366:
            raise ValueError("date window must be ordered and at most 367 days")
        if len({p.series for p in self.locations}) != len(self.locations):
            raise ValueError("each series must have one location configuration")
        for location in self.locations:
            ZoneInfo(location.timezone)
        if not self.decision_utc:
            raise ValueError("at least one UTC decision time is required")
        for value in self.decision_utc:
            parsed = datetime.strptime(value, "%H:%M").replace(tzinfo=UTC)
            if parsed.strftime("%H:%M") != value:
                raise ValueError("decision times must use HH:MM UTC")
        return self


class MarketEvidence(DomainModel):
    @model_validator(mode="before")
    @classmethod
    def validate_serialized_market(cls, value: object) -> object:
        if isinstance(value, dict) and isinstance(value.get("market"), dict):
            raw = dict(value["market"])
            if isinstance(raw.get("rules"), dict):
                rules = dict(raw["rules"])
                digest = rules.pop("rules_hash", None)
                raw["rules"] = rules
                market = Market.model_validate(raw)
                if digest is not None and digest != market.rules.rules_hash:
                    raise ValueError("serialized rules hash mismatch")
                return {**value, "market": market}
        return value

    market: Market
    created_at: UtcDatetime | None = None
    capture_basis: Literal["receipt", "legacy_manifest", "unknown"] = "unknown"
    raw_ref: str
    raw_hash: str


class Observation(DomainModel):
    """One provider revision, never inferred from a valid date or settlement label.

    provider_publication requires an explicit release timestamp and evidence description;
    received means availability is no earlier than the recorded collector receipt.
    """

    source_id: str
    entity_id: str
    variable: str
    valid_on: date
    value: ExactDecimal
    unit: str | None = None
    model: str | None = None
    revision_id: str | None = None
    valid_at: UtcDatetime | None = None
    issued_at: UtcDatetime | None = None
    published_at: UtcDatetime | None = None
    available_at: UtcDatetime | None = None
    received_at: UtcDatetime | None = None
    ingested_at: UtcDatetime | None = None
    revised_at: UtcDatetime | None = None
    timing_basis: Literal["received", "provider_publication", "unknown", "assumed"] = "unknown"
    evidence: str = "availability not established"
    role: Literal["feature", "observation"] = "feature"
    raw_ref: str
    raw_hash: str

    @model_validator(mode="after")
    def check_clock(self) -> Self:
        if self.timing_basis in ("received", "provider_publication"):
            if self.available_at is None or not self.evidence.strip():
                raise ValueError("strict observations need availability evidence")
            if self.timing_basis == "received" and (
                self.received_at is None or self.available_at < self.received_at
            ):
                raise ValueError("receipt-based availability cannot precede receipt")
            if self.timing_basis == "provider_publication" and self.published_at is None:
                raise ValueError("provider availability requires an actual publication time")
            for earlier in (self.issued_at, self.published_at):
                if earlier is not None and earlier > self.available_at:
                    raise ValueError("availability precedes issue/publication")
        if (
            self.ingested_at is not None
            and self.received_at is not None
            and self.ingested_at < self.received_at
        ):
            raise ValueError("ingestion precedes receipt")
        return self

    def known_at(self, decision: datetime) -> bool:
        return (
            self.timing_basis in ("received", "provider_publication")
            and self.available_at is not None
            and self.available_at <= decision
            and (self.revised_at is None or self.revised_at <= decision)
        )


class MarketState(DomainModel):
    market_ticker: str
    event_time: UtcDatetime
    available_at: UtcDatetime | None = None
    received_at: UtcDatetime | None = None
    ingested_at: UtcDatetime | None = None
    fidelity: Literal["order_book", "quote", "trade_print", "candle", "invalid"]
    payload: dict[str, object]
    raw_ref: str
    raw_hash: str

    @model_validator(mode="after")
    def check_state_clock(self) -> Self:
        if self.available_at is not None and (
            self.received_at is None
            or self.available_at < self.received_at
            or self.available_at < self.event_time
        ):
            raise ValueError("strict market state needs a defensible receipt clock")
        if (
            self.ingested_at is not None
            and self.received_at is not None
            and self.ingested_at < self.received_at
        ):
            raise ValueError("market state ingestion precedes receipt")
        return self
