"""Read-only discovery of Kalshi series tickers from retained public catalog receipts.

The family-selection procedure says candidate tickers must come from a catalog receipt,
never from memory. Discovery retains unauthenticated ``GET /series`` responses with a
hashed manifest and lists what they contain. It neither ranks nor selects anything:
choosing which series to screen, and which family to implement, stays with the user.
"""

import asyncio
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import httpx

from entropytrade.domain.time import Clock, SystemClock
from entropytrade.families.public import BoundedTransport
from entropytrade.families.screening import KALSHI_HOST, ScreeningError

DISCOVERY_SCHEMA = "entropytrade.family-series-discovery/1"
LISTING_SCHEMA = "entropytrade.family-series-listing/1"
SERIES_LIST_PATH = "/trade-api/v2/series"
# Kalshi category names contain letters, spaces and "&"; anything else is refused locally.
CATEGORY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z &]{0,59}$")
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,59}$")
MAX_CATEGORIES = 12
LISTING_LIMITATIONS = (
    "A series listing shows what the catalog offered when each receipt was fetched; it is not "
    "evidence of labels, liquidity, predictors, fees or settlement quality.",
    "Order is alphabetical by ticker; nothing is ranked, recommended or selected.",
)


class DiscoveryTransport(BoundedTransport):
    """Existing bounded public transport, narrowed to the Kalshi series list only."""

    def permits_path(self, url: httpx.URL) -> bool:
        return url.host == KALSHI_HOST and url.path == SERIES_LIST_PATH


async def discover_series(
    root: Path,
    categories: Sequence[str],
    *,
    inner: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """One unauthenticated GET per category into a NEW directory; every response retained.

    The inherited transport caps requests (20), per-response bytes (2 MB) and run bytes.
    A response over budget, a transport error or a non-200 status is recorded, never retried.
    """
    if (
        not categories
        or len(categories) > MAX_CATEGORIES
        or len(set(categories)) != len(categories)
        or any(not CATEGORY_PATTERN.match(c) for c in categories)
    ):
        raise ScreeningError(f"categories must be 1-{MAX_CATEGORIES} distinct plain names")
    clock = clock or SystemClock()
    root.mkdir(parents=True, exist_ok=False)
    (root / "raw").mkdir()
    calls: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "schema": DISCOVERY_SCHEMA,
        "categories": list(categories),
        "started_at": clock.now().isoformat(),
        "calls": calls,
    }
    transport = DiscoveryTransport(inner)
    url = f"https://{KALSHI_HOST}{SERIES_LIST_PATH}"
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        for category in categories:
            entry: dict[str, Any] = {
                "category": category,
                "url": str(httpx.URL(url, params={"category": category})),
            }
            calls.append(entry)
            try:
                response = await client.get(url, params={"category": category})
            except (httpx.HTTPError, ValueError) as exc:
                entry.update(error=f"{type(exc).__name__}: {exc}", received_at=None)
                continue
            entry["received_at"] = clock.now().isoformat()
            name = f"raw/{len(calls):06d}{'' if response.status_code == 200 else '.error'}.json"
            (root / name).write_bytes(response.content)
            entry.update(
                status=response.status_code,
                path=name,
                bytes=len(response.content),
                sha256="sha256:" + hashlib.sha256(response.content).hexdigest(),
            )
    manifest["finished_at"] = clock.now().isoformat()
    manifest["requests"] = transport.requests
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def run_discovery(root: Path, categories: Sequence[str]) -> dict[str, Any]:
    return asyncio.run(discover_series(root, categories))


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _entry(raw: object, label: str, digest: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ScreeningError(f"{label}: series entry is not an object")
    ticker = raw.get("ticker")
    if not isinstance(ticker, str) or not TICKER_PATTERN.match(ticker):
        raise ScreeningError(f"{label}: series entry without a valid ticker")
    sources = raw.get("settlement_sources") or []
    if not isinstance(sources, list):
        raise ScreeningError(f"{ticker}: settlement_sources is not a list")
    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        raise ScreeningError(f"{ticker}: tags is not a list")
    return {
        "ticker": ticker,
        "title": _text(raw.get("title")),
        "category": _text(raw.get("category")),
        "frequency": _text(raw.get("frequency")),
        "tags": sorted({_text(t) for t in tags if _text(t)}),
        "fee_type": _text(raw.get("fee_type")),
        "settlement_sources": sorted(
            {_text(s.get("name")) for s in sources if isinstance(s, dict) and _text(s.get("name"))}
        ),
        "receipt_sha256": digest,
    }


def list_discovered(roots: Iterable[Path]) -> dict[str, Any]:
    """Verify discovery directories against their manifests and list series deterministically.

    Fails closed on unknown schemas, escaping paths, hash mismatches, malformed bodies and
    conflicting descriptions of one ticker. Non-200 responses are reported, never listed.
    """
    inputs: list[dict[str, Any]] = []
    unusable: list[dict[str, Any]] = []
    series: dict[str, dict[str, Any]] = {}
    for root in roots:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest.get("schema") != DISCOVERY_SCHEMA:
            raise ScreeningError(f"{root}: unknown discovery manifest schema")
        for call in manifest["calls"]:
            if call.get("status") != 200:
                unusable.append(
                    {
                        "category": call.get("category"),
                        "status": call.get("status"),
                        "error": call.get("error"),
                    }
                )
                continue
            target = (root / call["path"]).resolve()
            if root.resolve() not in target.parents:
                raise ScreeningError(f"{root}: receipt path escapes discovery directory")
            body = target.read_bytes()
            digest = "sha256:" + hashlib.sha256(body).hexdigest()
            if digest != call["sha256"]:
                raise ScreeningError(f"{target}: hash does not match discovery manifest")
            try:
                document = json.loads(body)
            except json.JSONDecodeError as exc:
                raise ScreeningError(f"{target}: not JSON") from exc
            entries = document.get("series") if isinstance(document, dict) else None
            if not isinstance(entries, list):
                raise ScreeningError(f"{target}: series list missing")
            for raw in entries:
                item = _entry(raw, str(target), digest)
                previous = series.get(item["ticker"])
                if previous is not None:
                    same = {k: v for k, v in previous.items() if k != "receipt_sha256"}
                    if same != {k: v for k, v in item.items() if k != "receipt_sha256"}:
                        raise ScreeningError(f"{item['ticker']}: conflicting series descriptions")
                    continue
                series[item["ticker"]] = item
            inputs.append(
                {"category": call.get("category"), "sha256": digest, "series": len(entries)}
            )
    if not inputs and not unusable:
        raise ScreeningError("no discovery receipts supplied")
    rows = [series[t] for t in sorted(series)]
    return {
        "schema": LISTING_SCHEMA,
        "inputs": sorted(inputs, key=lambda i: (str(i["category"]), i["sha256"])),
        "unusable_calls": sorted(unusable, key=lambda u: str(u["category"])),
        "counts": {
            "series": len(rows),
            "by_category": dict(sorted(Counter(r["category"] for r in rows).items())),
            "by_frequency": dict(sorted(Counter(r["frequency"] for r in rows).items())),
        },
        "series": rows,
        "limitations": list(LISTING_LIMITATIONS),
    }


def render_listing(listing: dict[str, Any]) -> str:
    lines = [
        f"series={listing['counts']['series']} by_category={listing['counts']['by_category']}",
        f"by_frequency={listing['counts']['by_frequency']}",
    ]
    lines += [f"UNUSABLE {u}" for u in listing["unusable_calls"]]
    lines += [
        "| Ticker | Category | Frequency | Fee type | Settlement sources | Title |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['ticker']} | {r['category']} | {r['frequency']} | {r['fee_type']} | "
        f"{'; '.join(r['settlement_sources'])} | {r['title']} |"
        for r in listing["series"]
    ]
    return "\n".join(lines)
