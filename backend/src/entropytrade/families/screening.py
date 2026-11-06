"""Read-only market-family screening over retained public Kalshi catalog receipts.

The screen summarizes, per series, catalog coverage, finalized binary outcome balance,
contract structure, rule wording and traded volume so a user can compare candidate
market families before approving one. It never selects a family.

Catalog fields describe each market as observed when its receipt was fetched. They do
not establish point-in-time predictor availability, executable depth, effective fees or
profitability; those remain separate gates in the existing research workflow.
"""

import asyncio
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any

import httpx

from entropytrade.domain.time import Clock, SystemClock, ensure_utc
from entropytrade.families.public import BoundedTransport

SCHEMA = "entropytrade.family-screen/1"
FETCH_SCHEMA = "entropytrade.family-catalog-fetch/1"
# Mirrors the existing binary-family fitting minimum (bitcoin_models: 40 events, 20 dates,
# both outcomes). Meeting it only says enough finalized labels exist to *attempt* a fit.
MIN_LABELED_EVENTS = 40
MIN_LABELED_DATES = 20
KALSHI_HOST = "api.elections.kalshi.com"
SERIES_PATTERN = re.compile(r"^[A-Z0-9]{2,40}$")
LABELED_STATUSES = frozenset({"finalized", "settled"})
# Fields that identify a contract must agree across receipts of one ticker. Live and
# historical endpoints and repeated polls can share one updated_time while cumulative
# trading fields or unrelated fields (open interest, quotes) differ.
IDENTITY_FIELDS = (
    "series_ticker",
    "event_ticker",
    "close_time",
    "market_type",
    "strike_type",
    "rules_primary",
)
LIMITATIONS = (
    "Catalog fields are as observed at receipt fetch time; they are not point-in-time "
    "availability evidence for any predictor or price.",
    "Volume is lifetime traded contracts reported by the catalog; it is not executable depth "
    "at any decision time.",
    "Rule examples are verbatim text; no settlement authority is inferred from them.",
    "Meeting the label-history minimum does not establish predictive skill, effective fees, "
    "realistic validation or profitability.",
    "This screen never selects a market family; selection requires user approval.",
)


class ScreeningError(ValueError):
    """Receipts are malformed, ambiguous or fail integrity checks; nothing is screened."""


@dataclass(frozen=True)
class ReceiptInput:
    path: str
    sha256: str
    markets: int
    series_metadata: str | None = None


@dataclass
class Catalog:
    inputs: list[ReceiptInput] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    markets: dict[str, dict[str, Any]] = field(default_factory=dict)
    series: dict[str, dict[str, Any]] = field(default_factory=dict)
    revised_tickers: set[str] = field(default_factory=set)
    merged_tickers: set[str] = field(default_factory=set)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _updated(market: dict[str, Any]) -> datetime | None:
    value = market.get("updated_time")
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ScreeningError(f"{market['ticker']}: invalid updated_time {value!r}")
    try:
        return ensure_utc(datetime.fromisoformat(value))
    except ValueError as exc:
        raise ScreeningError(f"{market['ticker']}: invalid updated_time {value!r}") from exc


def _retain_market(catalog: Catalog, market: object, source: str) -> None:
    if not isinstance(market, dict):
        raise ScreeningError(f"{source}: market entry is not an object")
    ticker, event = market.get("ticker"), market.get("event_ticker")
    if not isinstance(ticker, str) or not ticker or not isinstance(event, str) or not event:
        raise ScreeningError(f"{source}: market without ticker/event_ticker")
    # Validate even unique or subsequently superseded observations, before any are discarded.
    _updated(market)
    _close_date(market)
    _volume(market)
    catalog.observations.append(market)


def _revision_key(market: dict[str, Any]) -> tuple[bool, datetime, str]:
    updated = _updated(market)
    return updated is None, updated or datetime.min.replace(tzinfo=UTC), _canonical(market)


def _add_market(catalog: Catalog, market: dict[str, Any]) -> None:
    ticker = market["ticker"]
    previous = catalog.markets.get(ticker)
    if previous is None:
        catalog.markets[ticker] = market
        return
    if _canonical(previous) == _canonical(market):
        return
    old, new = _updated(previous), _updated(market)
    if old is not None and new is not None and old != new:
        catalog.revised_tickers.add(ticker)
        if new > old:
            catalog.markets[ticker] = market
        return
    catalog.markets[ticker] = _merge_tie(previous, market)
    catalog.merged_tickers.add(ticker)


def _merge_tie(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Combine two receipts of one ticker that carry no ordering clock.

    Identity fields must agree and two different final outcomes refuse. A final outcome
    is kept over an unresolved one; lifetime volume, which never decreases, keeps its
    maximum. Every other field is left as in the first receipt and is not screened.
    """
    ticker = first["ticker"]
    for key in IDENTITY_FIELDS:
        if first.get(key) != second.get(key):
            raise ScreeningError(f"{ticker}: receipts disagree on {key} without ordering")
    merged = dict(first)
    left, right = _label(first), _label(second)
    if left and right and left != right:
        raise ScreeningError(f"{ticker}: receipts report different final results")
    if right and not left:
        merged["status"], merged["result"] = second.get("status"), second.get("result")
    if any("volume_fp" in item or "volume" in item for item in (first, second)):
        key = "volume_fp" if "volume_fp" in first or "volume_fp" in second else "volume"
        merged[key] = _number(max(_volume(first), _volume(second)))
    return merged


def _add_body(catalog: Catalog, body: bytes, label: str) -> None:
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    try:
        document = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ScreeningError(f"{label}: not JSON") from exc
    series_name: str | None = None
    if isinstance(document, list):
        markets: object = document
    elif isinstance(document, dict) and isinstance(document.get("series"), dict):
        metadata = document["series"]
        ticker = metadata.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            raise ScreeningError(f"{label}: series metadata without ticker")
        if ticker in catalog.series and _canonical(catalog.series[ticker]) != _canonical(metadata):
            raise ScreeningError(f"{ticker}: conflicting series metadata receipts")
        catalog.series[ticker] = metadata
        series_name, markets = ticker, []
    elif isinstance(document, dict) and "markets" in document:
        markets = document["markets"]
    else:
        raise ScreeningError(f"{label}: neither a markets list nor series metadata")
    if not isinstance(markets, list):
        raise ScreeningError(f"{label}: markets is not a list")
    for market in markets:
        _retain_market(catalog, market, label)
    catalog.inputs.append(ReceiptInput(label, digest, len(markets), series_name))


def load_catalog(receipts: Iterable[Path] = (), fetched: Iterable[Path] = ()) -> Catalog:
    """Load loose receipt files and verified fetch directories; fail closed on any defect."""
    catalog = Catalog()
    for path in receipts:
        _add_body(catalog, path.read_bytes(), str(path))
    for root in fetched:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest.get("schema") != FETCH_SCHEMA:
            raise ScreeningError(f"{root}: unknown fetch manifest schema")
        for call in manifest["calls"]:
            if call.get("status") != 200:
                continue  # Retained for audit, never screened.
            target = (root / call["path"]).resolve()
            if root.resolve() not in target.parents:
                raise ScreeningError(f"{root}: receipt path escapes fetch directory")
            body = target.read_bytes()
            if "sha256:" + hashlib.sha256(body).hexdigest() != call["sha256"]:
                raise ScreeningError(f"{target}: hash does not match fetch manifest")
            _add_body(catalog, body, str(root / call["path"]))
    if not catalog.inputs:
        raise ScreeningError("no receipts supplied")
    # Resolve dated revisions first, then conservatively combine unclocked observations.
    # Streaming ties can otherwise lend an undated result an arbitrary earlier clock and
    # let a later unresolved receipt erase it, depending on input-file order.
    for market in sorted(catalog.observations, key=_revision_key):
        _add_market(catalog, market)
    catalog.observations.clear()
    return catalog


def _decimal(value: object) -> Decimal:
    if value is None or value == "":
        return Decimal(0)
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ScreeningError(f"invalid numeric field {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ScreeningError(f"invalid numeric field {value!r}")
    return result


def _volume(market: dict[str, Any]) -> Decimal:
    return _decimal(market.get("volume_fp", market.get("volume")))


def _close_date(market: dict[str, Any]) -> date | None:
    value = market.get("close_time")
    if not isinstance(value, str) or not value:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(value)).date()
    except ValueError as exc:
        raise ScreeningError(f"{market['ticker']}: invalid close_time {value!r}") from exc


def _label(market: dict[str, Any]) -> str | None:
    result = market.get("result")
    if market.get("status") in LABELED_STATUSES and result in {"yes", "no"}:
        return str(result)
    return None


_MONTHS = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?=\s|\d|$)",
    re.IGNORECASE,
)


def _template(rule: str) -> str:
    """Rule wording with dates and numbers masked, so only wording changes count."""
    return _MONTHS.sub("<month>", re.sub(r"\d+(?:\.\d+)?", "#", rule)).strip()


METADATA_FIELDS = (
    "title",
    "category",
    "frequency",
    "fee_type",
    "fee_multiplier",
    "settlement_sources",
    "contract_url",
)


def _metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if metadata is None else {key: metadata.get(key) for key in METADATA_FIELDS}


def _series_key(market: dict[str, Any]) -> str:
    value = market.get("series_ticker")
    if isinstance(value, str) and value:
        return value
    return str(market["event_ticker"]).split("-", 1)[0]


def _number(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def _screen_series(
    name: str, markets: list[dict[str, Any]], metadata: dict[str, Any] | None
) -> dict[str, Any]:
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for market in markets:
        events[str(market["event_ticker"])].append(market)
    labels = Counter(_label(m) for m in markets)
    labeled_events = {event for event, members in events.items() if all(_label(m) for m in members)}
    close_dates = {d for m in markets if (d := _close_date(m)) is not None}
    labeled_dates = {
        d for event in labeled_events for m in events[event] if (d := _close_date(m)) is not None
    }
    event_volumes = sorted(sum((_volume(m) for m in ms), Decimal(0)) for ms in events.values())
    total_volume = sum(event_volumes, Decimal(0))
    templates = Counter(_template(str(m.get("rules_primary", ""))) for m in markets)
    reasons = []
    if len(labeled_events) < MIN_LABELED_EVENTS:
        reasons.append(f"{len(labeled_events)}/{MIN_LABELED_EVENTS} finalized binary events")
    if len(labeled_dates) < MIN_LABELED_DATES:
        reasons.append(f"{len(labeled_dates)}/{MIN_LABELED_DATES} finalized close dates")
    if not labels["yes"] or not labels["no"]:
        reasons.append("finalized outcomes do not include both YES and NO")
    ordered = sorted(markets, key=lambda m: (str(m.get("close_time") or ""), str(m["ticker"])))
    return {
        "series": name,
        "markets": len(markets),
        "events": len(events),
        "close_dates": len(close_dates),
        "first_close_date": min(close_dates).isoformat() if close_dates else None,
        "last_close_date": max(close_dates).isoformat() if close_dates else None,
        "markets_per_event_median": median(len(ms) for ms in events.values()),
        "labeled_markets": {"yes": labels["yes"], "no": labels["no"]},
        "unlabeled_markets": labels[None],
        "labeled_events": len(labeled_events),
        "labeled_dates": len(labeled_dates),
        "market_types": dict(sorted(Counter(str(m.get("market_type")) for m in markets).items())),
        "strike_types": dict(sorted(Counter(str(m.get("strike_type")) for m in markets).items())),
        "traded_market_fraction": str(
            (Decimal(sum(1 for m in markets if _volume(m) > 0)) / len(markets)).quantize(
                Decimal("0.001")
            )
        ),
        "total_volume": _number(total_volume),
        "event_volume_median": _number(Decimal(str(median(event_volumes)))),
        "rule_templates": len(templates),
        "rule_examples": {
            "earliest_close": str(ordered[0].get("rules_primary", "")),
            "latest_close": str(ordered[-1].get("rules_primary", "")),
        },
        "series_metadata": _metadata(metadata),
        "label_history_minimum": {
            "required_events": MIN_LABELED_EVENTS,
            "required_dates": MIN_LABELED_DATES,
            "met": not reasons,
            "shortfalls": reasons,
        },
    }


def screen(catalog: Catalog) -> dict[str, Any]:
    """Deterministic per-series report; no wall-clock values are introduced."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ticker in sorted(catalog.markets):
        grouped[_series_key(catalog.markets[ticker])].append(catalog.markets[ticker])
    names = sorted(set(grouped) | set(catalog.series))
    return {
        "schema": SCHEMA,
        "inputs": [vars(item) for item in catalog.inputs],
        "unique_markets": len(catalog.markets),
        "revised_tickers": len(catalog.revised_tickers),
        "merged_tickers": len(catalog.merged_tickers),
        "series": [
            _screen_series(name, grouped[name], catalog.series.get(name))
            if grouped[name]
            else {
                "series": name,
                "markets": 0,
                "series_metadata": _metadata(catalog.series[name]),
                "label_history_minimum": {
                    "required_events": MIN_LABELED_EVENTS,
                    "required_dates": MIN_LABELED_DATES,
                    "met": False,
                    "shortfalls": ["no market receipts"],
                },
            }
            for name in names
        ],
        "limitations": list(LIMITATIONS),
    }


def render_table(report: dict[str, Any]) -> str:
    """Compact Markdown comparison table for docs and terminal review."""
    lines = [
        "| Series | Markets | Events | Close dates | Labeled events/dates | YES/NO | "
        "Traded share | Volume | Rule templates | Label minimum |",
        "|---|---:|---:|---|---|---|---:|---:|---:|---|",
    ]
    for row in report["series"]:
        if not row["markets"]:
            lines.append(f"| {row['series']} | 0 | 0 | — | — | — | — | — | — | no markets |")
            continue
        gate = row["label_history_minimum"]
        lines.append(
            f"| {row['series']} | {row['markets']} | {row['events']} | "
            f"{row['first_close_date']}…{row['last_close_date']} ({row['close_dates']}) | "
            f"{row['labeled_events']}/{row['labeled_dates']} | "
            f"{row['labeled_markets']['yes']}/{row['labeled_markets']['no']} | "
            f"{row['traded_market_fraction']} | {row['total_volume']} | "
            f"{row['rule_templates']} | {'met' if gate['met'] else 'not met'} |"
        )
    return "\n".join(lines)


class CatalogTransport(BoundedTransport):
    """Existing bounded public transport, narrowed to Kalshi catalog reads only."""

    def permits_path(self, url: httpx.URL) -> bool:
        if url.host != KALSHI_HOST:
            return False
        path = url.path
        if path in {"/trade-api/v2/markets", "/trade-api/v2/historical/markets"}:
            return True
        prefix = "/trade-api/v2/series/"
        return path.startswith(prefix) and bool(SERIES_PATTERN.match(path[len(prefix) :]))


async def fetch_catalog(
    root: Path,
    series: Sequence[str],
    *,
    max_pages: int = 3,
    inner: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Unauthenticated GETs into a NEW directory; every response is retained, none trusted.

    The inherited transport caps requests (20) and bytes per run. Non-200 responses and
    transport errors are recorded and stop that series; nothing is retried or fabricated.
    """
    if not series or any(not SERIES_PATTERN.match(s) for s in series):
        raise ScreeningError("series tickers must be 2-40 uppercase letters/digits")
    if not 1 <= max_pages <= 5:
        raise ScreeningError("max_pages must be between 1 and 5")
    clock = clock or SystemClock()
    root.mkdir(parents=True, exist_ok=False)
    (root / "raw").mkdir()
    calls: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "schema": FETCH_SCHEMA,
        "series": list(series),
        "max_pages": max_pages,
        "started_at": clock.now().isoformat(),
        "calls": calls,
    }
    transport = CatalogTransport(inner)
    base = f"https://{KALSHI_HOST}/trade-api/v2"

    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:

        async def get(url: str, params: dict[str, str]) -> dict[str, Any] | None:
            entry: dict[str, Any] = {"url": str(httpx.URL(url, params=params))}
            calls.append(entry)
            try:
                response = await client.get(url, params=params)
            except (httpx.HTTPError, ValueError) as exc:
                entry.update(error=f"{type(exc).__name__}: {exc}", received_at=None)
                return None
            entry["received_at"] = clock.now().isoformat()
            name = f"raw/{len(calls):06d}{'' if response.status_code == 200 else '.error'}.json"
            (root / name).write_bytes(response.content)
            entry.update(
                status=response.status_code,
                path=name,
                bytes=len(response.content),
                sha256="sha256:" + hashlib.sha256(response.content).hexdigest(),
            )
            if response.status_code != 200:
                return None
            try:
                body = response.json()
            except json.JSONDecodeError:
                entry["error"] = "response is not JSON"
                return None
            return body if isinstance(body, dict) else None

        for name in series:
            if await get(f"{base}/series/{name}", {}) is None:
                continue
            for endpoint in ("markets", "historical/markets"):
                cursor = ""
                for _ in range(max_pages):
                    params = {"limit": "200", "series_ticker": name}
                    if cursor:
                        params["cursor"] = cursor
                    body = await get(f"{base}/{endpoint}", params)
                    if body is None:
                        break
                    cursor = str(body.get("cursor") or "")
                    if not cursor:
                        break
    manifest["finished_at"] = clock.now().isoformat()
    manifest["requests"] = transport.requests
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def run_fetch(root: Path, series: Sequence[str], max_pages: int = 3) -> dict[str, Any]:
    return asyncio.run(fetch_catalog(root, series, max_pages=max_pages))
