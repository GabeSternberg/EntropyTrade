"""Stored settlement dollars versus the stored result.

Exactly 1 is YES and exactly 0 is NO. Any other number, including a value
between them, is unevaluable. Nothing is rounded, filled, or promoted.
This module does not open a socket.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_YES = Decimal(1)
_NO = Decimal(0)


@dataclass(frozen=True)
class SettlementValueCheck:
    """How often the settlement dollars match the stored yes or no result."""

    markets: int
    agreements: int
    mismatches: int
    unevaluable: int
    guaranteed_fill: bool
    promoted: bool


def load_settlement_value_check(root: Path) -> SettlementValueCheck:
    """Compare settlement dollars with stored results. Do not round."""
    markets = 0
    agreements = 0
    mismatches = 0
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
            side = _side(market.get("settlement_value_dollars"))
            if side is None:
                continue
            if side == result:
                agreements += 1
            else:
                mismatches += 1
    return SettlementValueCheck(
        markets=markets,
        agreements=agreements,
        mismatches=mismatches,
        unevaluable=markets - agreements - mismatches,
        guaranteed_fill=False,
        promoted=False,
    )


def _side(value: object) -> str | None:
    number = _decimal(value)
    if number == _YES:
        return "yes"
    if number == _NO:
        return "no"
    return None


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
