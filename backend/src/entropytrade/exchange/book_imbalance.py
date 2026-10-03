"""Stored CLI-window order books. This module does not open a socket.

An imbalance is the yes size minus the no size, divided by their sum, and
only when both sides have a level. An empty book does not get a ratio.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_MANIFEST = Path("kalshi-public/cli-window/manifest.json")


@dataclass(frozen=True)
class BookImbalance:
    """Counts from stored calls. ``traded`` and ``promoted`` stay false."""

    books: int
    imbalances: int
    skipped: tuple[str, ...]
    traded: bool
    promoted: bool


def load_book_imbalance(root: Path) -> BookImbalance:
    """Apply the written rule. A missing level is not invented."""
    manifest = _object(root / _MANIFEST)
    calls = manifest.get("calls")
    if not isinstance(calls, list):
        raise ValueError("the CLI-window calls are not a list")
    books = 0
    quotients: list[Decimal] = []
    skipped: list[str] = []
    for call in calls:
        if not isinstance(call, dict):
            skipped.append("call: not an object")
            continue
        url = call.get("url")
        if not isinstance(url, str) or "/orderbook" not in url:
            continue
        books += 1
        label = _ticker(url)
        if call.get("status") != 200:
            skipped.append(f"{label}: not HTTP 200")
            continue
        path = call.get("path")
        if not isinstance(path, str) or path == "":
            skipped.append(f"{label}: no stored body")
            continue
        yes, no = _sizes(root / path)
        if yes <= 0 or no <= 0:
            skipped.append(f"{label}: empty side")
            continue
        quotients.append((yes - no) / (yes + no))
    return BookImbalance(
        books=books,
        imbalances=len(quotients),
        skipped=tuple(skipped),
        traded=False,
        promoted=False,
    )


def book_imbalance_note(root: Path) -> str:
    """One sentence. The CLI coverage row stays unchanged."""
    found = load_book_imbalance(root)
    if found.traded or found.promoted:
        raise ValueError("the imbalance note must not trade")
    if found.imbalances == 0:
        computed = "so no imbalance was computed."
    else:
        computed = "The quotient was not rounded and was not a threshold."
    return " ".join(
        (
            "The stored Philadelphia CLI-window order books have",
            f"{found.books} books.",
            f"{found.imbalances} have both a yes level and a no level,",
            computed,
            f"{len(found.skipped)} books had an empty side or no stored body",
            "and were not filled in.",
            "It is not a CLI rescore column.",
            "It is not a threshold.",
            "Nothing was traded.",
            "Nothing was promoted.",
        )
    )


def _sizes(path: Path) -> tuple[Decimal, Decimal]:
    body = _object(path)
    raw = body.get("orderbook_fp")
    if not isinstance(raw, dict):
        raise ValueError("orderbook_fp is not an object")
    return _size(raw.get("yes_dollars")), _size(raw.get("no_dollars"))


def _size(value: object) -> Decimal:
    if not isinstance(value, list):
        raise ValueError("an order-book side is not a list")
    total = Decimal(0)
    for pair in value:
        if not isinstance(pair, list) or len(pair) < 2:
            raise ValueError("an order-book level needs a price and a size")
        size = pair[1]
        if isinstance(size, bool) or not isinstance(size, Decimal | int | str):
            raise ValueError("an order-book size is not a number")
        quantity = Decimal(size)
        if quantity > 0:
            total += quantity
    return total


def _ticker(url: str) -> str:
    marker = "/markets/"
    start = url.find(marker)
    if start < 0:
        return url
    rest = url[start + len(marker) :]
    return rest.split("/", maxsplit=1)[0]


def _object(path: Path) -> dict[str, object]:
    payload: object = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} is not an object")
    mapped: dict[str, object] = {}
    for key, item in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"{path.name} has a non-string key")
        mapped[key] = item
    return mapped
