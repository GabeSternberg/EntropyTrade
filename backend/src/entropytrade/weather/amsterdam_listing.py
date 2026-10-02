"""Amsterdam listing. The Celsius contract is not the frozen bracket.

The listed markets settle in Celsius. Every requested B80.5 ticker is
``not_found``. The Fahrenheit 80-81 bracket is not applied to those
Celsius strikes. Nothing is scored. Nothing is promoted. This module
does not open a socket.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AmsterdamListing:
    """The stored listing. ``scored`` stays false."""

    series: str
    markets_missing: int
    markets_found: int
    celsius_markets_listed: int
    bracket_applied: bool
    scored: bool
    promoted: bool


def load_amsterdam_listing(root: Path) -> AmsterdamListing:
    """Read the stored rows. A Celsius strike is not treated as 80.5 Fahrenheit."""
    folder = root / "amsterdam"
    manifest = _object(folder / "manifest.json")
    if manifest.get("series") != "KXHIGHTEHAM":
        raise ValueError("Amsterdam series changed")
    if manifest.get("scored") is not False or manifest.get("bracket_applied") is not False:
        raise ValueError("Amsterdam applied the Fahrenheit bracket")
    if manifest.get("promoted") is not False:
        raise ValueError("Amsterdam is promoted")
    markets = _rows(folder / "markets.json")
    missing = all(row.get("http_status") == 404 and "result" not in row for row in markets)
    if len(markets) != 40 or not missing:
        raise ValueError("Amsterdam B80.5 rows are not all missing")
    samples = _rows(folder / "celsius-markets.json")
    if not samples:
        raise ValueError("Amsterdam has no Celsius sample")
    for row in samples:
        rules = row.get("rules_primary")
        ticker = row.get("ticker")
        if not isinstance(rules, str) or "Celsius" not in rules:
            raise ValueError("a listed Amsterdam market is not Celsius")
        if not isinstance(ticker, str) or "B80.5" in ticker:
            raise ValueError("a Celsius sample uses the Fahrenheit strike")
    if len(samples) != _count(manifest.get("celsius_markets_listed"), "celsius_markets_listed"):
        raise ValueError("the Amsterdam manifest does not match the Celsius samples")
    return AmsterdamListing(
        series="KXHIGHTEHAM",
        markets_missing=40,
        markets_found=0,
        celsius_markets_listed=len(samples),
        bracket_applied=False,
        scored=False,
        promoted=False,
    )


def _rows(path: Path) -> tuple[dict[str, object], ...]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} is not a list")
    rows: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"{path.name} has a non-object row")
        mapped: dict[str, object] = {}
        for key, value in item.items():
            if not isinstance(key, str):
                raise ValueError(f"{path.name} has a non-string key")
            mapped[key] = value
        rows.append(mapped)
    return tuple(rows)


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    mapped: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"{path.name} has a non-string key")
        mapped[key] = item
    return mapped


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is not a count")
    return value
