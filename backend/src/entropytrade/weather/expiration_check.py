"""Stored expiration value versus the strike and the stored result.

The comparison uses the existing strike rule. A missing bound, an unknown
strike, or an expiration value that is not an exact number is left
unevaluable. Nothing is invented, nothing is filled, and nothing is
promoted. This module does not open a socket.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from entropytrade.domain.enums import StrikeType
from entropytrade.domain.market import Strike


@dataclass(frozen=True)
class ExpirationCheck:
    """How often the stored result matches the strike at the expiration value."""

    markets: int
    evaluable: int
    unevaluable: int
    missing_expiration: int
    missing_strike: int
    agreements: int
    mismatches: int
    guaranteed_fill: bool
    promoted: bool


def load_expiration_check(root: Path) -> ExpirationCheck:
    """Compare stored expiration values with stored strikes and results."""
    markets = 0
    evaluable = 0
    missing_expiration = 0
    missing_strike = 0
    agreements = 0
    folder = root / "kalshi-public"
    for path in sorted(folder.glob("historical-*.json")):
        payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} is not an object")
        rows = payload.get("markets")
        if not isinstance(rows, list):
            raise ValueError(f"{path.name} has no markets")
        for market in rows:
            if not isinstance(market, dict):
                continue
            ticker = market.get("ticker")
            result = market.get("result")
            if not isinstance(ticker, str) or not ticker.startswith("KXHIGHPHIL-"):
                continue
            if result not in ("yes", "no"):
                continue
            markets += 1
            if _decimal(market.get("expiration_value")) is None:
                missing_expiration += 1
                continue
            yes = _yes(market)
            if yes is None:
                missing_strike += 1
                continue
            evaluable += 1
            if yes == (result == "yes"):
                agreements += 1
    return ExpirationCheck(
        markets=markets,
        evaluable=evaluable,
        unevaluable=markets - evaluable,
        missing_expiration=missing_expiration,
        missing_strike=missing_strike,
        agreements=agreements,
        mismatches=evaluable - agreements,
        guaranteed_fill=False,
        promoted=False,
    )


def _yes(market: dict[str, object]) -> bool | None:
    value = _decimal(market.get("expiration_value"))
    strike = _strike(market)
    if value is None or strike is None:
        return None
    return strike.resolves_yes(value)


def _strike(market: dict[str, object]) -> Strike | None:
    raw = market.get("strike_type")
    if not isinstance(raw, str):
        return None
    try:
        kind = StrikeType(raw)
    except ValueError:
        return None
    try:
        strike = Strike(
            strike_type=kind,
            floor=_decimal(market.get("floor_strike")),
            cap=_decimal(market.get("cap_strike")),
        )
    except ValueError:
        return None
    if not strike.is_evaluable:
        return None
    return strike


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool | float):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except ArithmeticError:
            return None
    return None
