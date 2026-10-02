"""Settlement source taken from the contract text, with the KXHIGH date schedule as fallback.

Current KXHIGH contracts, including Philadelphia (``KXHIGHPHIL``, station CLIPHL), name
The Weather Company for target dates on and after 2026-08-14. Older contracts name the
NWS Daily Climate Report. The sentence in the rules wins when it names a source. The date
is used only when a KXHIGH contract's text does not.
"""

from datetime import date
from typing import Literal

from pydantic import Field

from entropytrade.domain.base import DomainModel
from entropytrade.domain.market import SettlementSource

KXHIGH_CUTOVER = date(2026, 8, 14)
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

SourceBasis = Literal["contract_text", "kxhigh_schedule", "unresolved"]


class ParsedSettlement(DomainModel):
    sources: tuple[SettlementSource, ...]
    basis: SourceBasis
    target_date: date | None = None
    series_prefix: str = Field(min_length=1)


def ticker_target_date(ticker: str) -> date | None:
    """``KXHIGHPHIL-26OCT02-T89`` -> 2026-10-02. ``None`` when the ticker has no YYMONDD token."""
    parts = ticker.upper().split("-")
    for part in parts:
        if len(part) < 7:
            continue
        year_text, month_text, day_text = part[:2], part[2:5], part[5:7]
        if not (year_text.isdigit() and day_text.isdigit()):
            continue
        month = _MONTHS.get(month_text)
        if month is None:
            continue
        return date(2000 + int(year_text), month, int(day_text))
    return None


def parse_settlement(rules_primary: str, rules_secondary: str, ticker: str) -> ParsedSettlement:
    """Name the source a contract actually uses. Text first, then the KXHIGH schedule."""
    text = f"{rules_primary}\n{rules_secondary}".casefold()
    target = ticker_target_date(ticker)
    prefix = ticker.split("-", maxsplit=1)[0].upper()
    named = _from_text(text)
    if named is not None:
        return ParsedSettlement(
            sources=(named,),
            basis="contract_text",
            target_date=target,
            series_prefix=prefix,
        )
    if prefix.startswith("KXHIGH") and target is not None:
        source = _weather_company() if target >= KXHIGH_CUTOVER else _nws_cli()
        return ParsedSettlement(
            sources=(source,),
            basis="kxhigh_schedule",
            target_date=target,
            series_prefix=prefix,
        )
    return ParsedSettlement(
        sources=(),
        basis="unresolved",
        target_date=target,
        series_prefix=prefix,
    )


def _from_text(text: str) -> SettlementSource | None:
    if "weather company" in text or "weather.com" in text:
        return _weather_company()
    if "national weather service" in text or "daily climate" in text or " nws " in f" {text} ":
        return _nws_cli()
    return None


def _weather_company() -> SettlementSource:
    return SettlementSource(name="The Weather Company", url="https://weather.com/kalshi")


def _nws_cli() -> SettlementSource:
    return SettlementSource(name="NWS Daily Climate Report", url=None)
