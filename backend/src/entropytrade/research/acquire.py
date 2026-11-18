"""Read-only acquisition through approved adapters into immutable, versioned datasets.

Every response is preserved byte-for-byte in a content-addressed raw store with its receipt
clock and hash. Adapters parse those bytes with deterministic, fail-closed parsers. Retrieved
content is data only: it can never choose a URL, run a command or touch configuration.
"""

import base64
import json
import re
import shutil
import time
from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

import httpx

from entropytrade.features.registry import scientific_hash
from entropytrade.research.model import DataKind
from entropytrade.research.sources import SourceDescriptor

USER_AGENT = "EntropyTrade research (github.com/GabeSternberg/EntropyTrade)"
MAX_RESPONSE_BYTES = 8_000_000
DATASET_SCHEMA = "entropytrade-research-dataset-v1"
_HEADERS = ("date", "last-modified", "etag", "content-type")


class AcquisitionError(Exception):
    """A request or parse failed. ``transient`` failures may be retried within budget."""

    def __init__(self, reason: str, *, transient: bool) -> None:
        super().__init__(reason)
        self.reason, self.transient = reason, transient


class BudgetExceededError(AcquisitionError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason, transient=False)


class AllowlistTransport(httpx.BaseTransport):
    """HTTPS GET only, to catalog host/path prefixes, no credentials, bounded bodies."""

    def __init__(self, source: SourceDescriptor, inner: httpx.BaseTransport | None = None) -> None:
        self.rules = {rule.host: rule.paths for rule in source.hosts}
        self.inner = inner or httpx.HTTPTransport(retries=0)

    def permits(self, url: httpx.URL) -> bool:
        paths = self.rules.get(url.host, ())
        return (
            url.scheme == "https"
            and url.port in {None, 443}
            and not url.userinfo
            and any(url.path == p or url.path.startswith(p.rstrip("/") + "/") for p in paths)
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.method != "GET"
            or not self.permits(request.url)
            or any(
                name.lower() in {"authorization", "cookie"} or "api-key" in name.lower()
                for name in request.headers
            )
        ):
            raise AcquisitionError(
                "destination or method outside the source allowlist", transient=False
            )
        response = self.inner.handle_request(request)
        body = bytearray()
        try:
            # iter_bytes decodes any content encoding, so the stored bytes are the body itself.
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise AcquisitionError(
                        "response exceeds the per-response byte budget", transient=False
                    )
        finally:
            response.close()
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in {"content-encoding", "content-length"}
        }
        return httpx.Response(
            response.status_code, headers=headers, content=bytes(body), request=request
        )


@dataclass
class Receipt:
    url: str
    status: int | None
    received_at: datetime
    sha256: str
    size: int
    headers: dict[str, str]
    error: str = ""

    def record(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "received_at": self.received_at.isoformat(),
            "sha256": self.sha256,
            "bytes": self.size,
            "headers": self.headers,
            "error": self.error,
        }


@dataclass
class Fetched:
    receipt: Receipt
    body: bytes


@dataclass
class Parsed:
    records: list[dict[str, Any]]
    slices: dict[tuple[DataKind, str, str, str], dict[str, set[str]]]
    notes: list[str] = field(default_factory=list)
    refused: int = 0


class RawStore:
    """Write-once, content-addressed response bytes."""

    def __init__(self, root: Path) -> None:
        self.root = root / "raw"

    def put(self, body: bytes) -> str:
        digest = sha256(body).hexdigest()
        path = self.root / digest[:2] / digest
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(digest + ".tmp-" + uuid4().hex)
            temporary.write_bytes(body)
            temporary.replace(path)
        elif sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("raw evidence store is corrupted")
        return "sha256:" + digest

    def get(self, digest: str) -> bytes:
        hexdigest = digest.removeprefix("sha256:")
        if not re.fullmatch(r"[0-9a-f]{64}", hexdigest):
            raise ValueError("invalid raw evidence digest")
        body = (self.root / hexdigest[:2] / hexdigest).read_bytes()
        if sha256(body).hexdigest() != hexdigest:
            raise ValueError("raw evidence checksum mismatch")
        return body


@dataclass
class Fetcher:
    """Bounded GETs with per-host pacing, transient retries and cooperative cancellation."""

    source: SourceDescriptor
    raw: RawStore
    clock: Callable[[], datetime]
    budget_requests: int
    budget_bytes: int
    cancelled: Callable[[], bool]
    transport: httpx.BaseTransport | None = None
    sleep: Callable[[float], None] = time.sleep
    requests: int = 0
    bytes: int = 0
    _last: float = 0.0

    def get(self, url: str, *, attempts: int = 3) -> Fetched:
        for attempt in range(attempts):
            if self.cancelled():
                raise AcquisitionError("cancelled", transient=False)
            if self.requests >= self.budget_requests:
                raise BudgetExceededError("the job's HTTP request budget is exhausted")
            wait = self.source.rate_limit_seconds - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                with httpx.Client(
                    transport=AllowlistTransport(self.source, self.transport),
                    follow_redirects=False,
                    trust_env=False,
                    timeout=30,
                    headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                ) as client:
                    response = client.get(url)
            except httpx.HTTPError as exc:
                if attempt + 1 < attempts:
                    self.sleep(2.0 * (attempt + 1))
                    continue
                raise AcquisitionError(
                    f"network error ({type(exc).__name__})", transient=True
                ) from exc
            received = self.clock()
            body = response.content
            self.bytes += len(body)
            if self.bytes > self.budget_bytes:
                raise BudgetExceededError("the job's byte budget is exhausted")
            digest = self.raw.put(body)
            receipt = Receipt(
                url=url,
                status=response.status_code,
                received_at=received,
                sha256=digest,
                size=len(body),
                headers={k: response.headers[k] for k in _HEADERS if k in response.headers},
            )
            if response.status_code == 429 or response.status_code >= 500:
                receipt.error = f"HTTP {response.status_code}"
                if attempt + 1 < attempts:
                    self.sleep(2.0 * (attempt + 1))
                    continue
                raise AcquisitionError(
                    f"source returned HTTP {response.status_code}", transient=True
                )
            if response.status_code != 200:
                raise AcquisitionError(
                    f"source returned HTTP {response.status_code}", transient=False
                )
            return Fetched(receipt=receipt, body=body)
        raise AcquisitionError("request attempts exhausted", transient=True)


# ----------------------------------------------------------------- NWS text products
_TZ = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6, "PST": -8, "PDT": -7}
_MONTHS = {
    m: i
    for i, m in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        start=1,
    )
}
_WMO = re.compile(r"^([A-Z]{4}\d{2}) ([A-Z]{4}) (\d{2})(\d{2})(\d{2})", re.MULTILINE)
_ISSUED = re.compile(
    r"^(\d{1,2})(\d{2}) (AM|PM) ([A-Z]{3}) [A-Z]{3} ([A-Z]{3}) (\d{1,2}) (\d{4})\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def products(text: str) -> Iterator[str]:
    """IEM concatenates products, each starting with a control-A or a blank header line."""
    for chunk in re.split(r"\x01", text):
        if _WMO.search(chunk):
            yield chunk


def issuance(product: str) -> tuple[datetime, str]:
    """UTC issuance from the issuance line, cross-checked with the WMO header."""
    header = _WMO.search(product)
    issued = _ISSUED.search(product)
    if header is None or issued is None:
        raise ValueError("product has no WMO header or issuance line")
    hour, minute = int(issued.group(1)) % 12, int(issued.group(2))
    if issued.group(3).upper() == "PM":
        hour += 12
    zone = issued.group(4).upper()
    if zone not in _TZ:
        raise ValueError("unknown issuance timezone")
    local = datetime(
        int(issued.group(7)),
        _MONTHS[issued.group(5).upper()],
        int(issued.group(6)),
        hour,
        minute,
        tzinfo=timezone(timedelta(hours=_TZ[zone])),
    ).astimezone(UTC)
    day, hh, mm = (int(header.group(i)) for i in (3, 4, 5))
    if local.day != day or abs((local.hour * 60 + local.minute) - (hh * 60 + mm)) > 5:
        raise ValueError("WMO header and issuance line disagree")
    # Use the later of the two clocks: availability can never precede either.
    stamped = local.replace(hour=hh, minute=mm)
    return max(local, stamped), f"{header.group(1)} {header.group(2)} {day:02d}{hh:02d}{mm:02d}"


def _tokens(line: str, pattern: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(pattern, line)]


def pfm_maxima(product: str, point: str, lat: str, lon: str) -> dict[date, Decimal]:
    """Daytime maxima for one PFM point, keyed by local target date. Fails closed."""
    issued, _ = issuance(product)
    lines = product.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == point)
    except StopIteration as exc:
        raise ValueError("PFM point not present in product") from exc
    location = re.match(r"\s*([\d.]+)N\s+([\d.]+)W", lines[start + 1])
    if (
        location is None
        or abs(float(location.group(1)) - float(lat)) > 0.03
        or abs(float(location.group(2)) - float(lon)) > 0.03
    ):
        raise ValueError("PFM point location does not match the configured station")
    end = next((i for i in range(start, len(lines)) if lines[i].strip() == "$$"), len(lines))
    block = lines[start:end]
    result: dict[date, Decimal] = {}
    running: date | None = None
    for index, line in enumerate(block):
        if not line.startswith("Date"):
            continue
        local_line = block[index + 1] if index + 1 < len(block) else ""
        utc_line = block[index + 2] if index + 2 < len(block) else ""
        if not re.match(r"^[A-Z]{3} \dhrly", local_line) or not utc_line.startswith("UTC"):
            raise ValueError("PFM table header is malformed")
        hours = _tokens(local_line[9:], r"\d{2}")
        utc = _tokens(utc_line[9:], r"\d{2}")
        if [h[:2] for h in hours] != [u[:2] for u in utc] or not hours:
            raise ValueError("PFM local and UTC columns are misaligned")
        labels = _tokens(line, r"(\d{1,2})/(\d{1,2})(?:/(\d{2}))?")
        if not labels:
            raise ValueError("PFM table has no date label")
        first = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2}))?", labels[0][2])
        if first is None:
            raise ValueError("PFM date label is malformed")
        month, day = int(first.group(1)), int(first.group(2))
        year = 2000 + int(first.group(3)) if first.group(3) else issued.year
        candidate = date(year, month, day)
        if not first.group(3) and running is not None and candidate < running - timedelta(days=200):
            candidate = date(year + 1, month, day)
        running = candidate
        dates: list[date] = []
        previous: int | None = None
        for _, _, text in hours:
            hour = int(text)
            if previous is not None and hour < previous:
                running += timedelta(days=1)
            dates.append(running)
            previous = hour
        row = next(
            (b for b in block[index + 3 : index + 6] if b.startswith(("Min/Max", "Max/Min"))), None
        )
        if row is None:
            continue
        ends = {start_col + 9 + 2: i for i, (start_col, _, _) in enumerate(hours)}
        for _, end_col, text in _tokens(row[9:], r"-?\d{1,3}"):
            column = ends.get(end_col + 9)
            if column is None:
                raise ValueError("PFM extreme value is not aligned to a time column")
            if utc[column][2] == "00":
                value = Decimal(text)
                if not -60 <= value <= 140:
                    raise ValueError("PFM maximum outside the plausible range")
                result[dates[column]] = value
            elif utc[column][2] != "12":
                raise ValueError("PFM extreme value sits under an unexpected hour")
    if not result:
        raise ValueError("PFM point has no daytime maxima")
    return result


def _iem_url(pil: str, start: date, end: date) -> str:
    query = urlencode(
        {
            "pil": pil,
            "sdate": start.isoformat(),
            "edate": end.isoformat(),
            "limit": 9999,
            "fmt": "text",
        }
    )
    return "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?" + query


def _chunks(start: date, end: date, days: int) -> list[tuple[date, date]]:
    result = []
    cursor = start
    while cursor < end:
        result.append((cursor, min(end, cursor + timedelta(days=days))))
        cursor += timedelta(days=days)
    return result


def _observation(**values: Any) -> dict[str, Any]:
    from entropytrade.data.schema import Observation

    return Observation.model_validate(values).model_dump(mode="json")


def _slice() -> dict[str, set[str]]:
    return defaultdict(set)


class Adapter:
    adapter_id = ""
    version = "1"

    def requests(self, params: dict[str, str]) -> list[str]:
        raise NotImplementedError

    def follow(self, fetched: Fetched, params: dict[str, str]) -> list[str]:
        del fetched, params
        return []

    def parse(self, fetched: list[Fetched], params: dict[str, str], now: datetime) -> Parsed:
        raise NotImplementedError


class PfmAdapter(Adapter):
    adapter_id = "iem_afos_pfm"

    def requests(self, params: dict[str, str]) -> list[str]:
        start = date.fromisoformat(params["start"]) - timedelta(days=4)
        end = date.fromisoformat(params["end"]) + timedelta(days=1)
        return [_iem_url(params["pil"], a, b) for a, b in _chunks(start, end, 7)]

    def parse(self, fetched: list[Fetched], params: dict[str, str], now: datetime) -> Parsed:
        start, end = date.fromisoformat(params["start"]), date.fromisoformat(params["end"])
        vintages: dict[str, set[str]] = defaultdict(set)
        records: list[dict[str, Any]] = []
        parsed = Parsed(records=records, slices={})
        seen: set[tuple[str, str]] = set()
        for item in fetched:
            text = item.body.decode("utf-8", errors="replace")
            for product in products(text):
                try:
                    issued, header = issuance(product)
                    maxima = pfm_maxima(product, params["point"], params["lat"], params["lon"])
                except ValueError as exc:
                    parsed.refused += 1
                    parsed.notes.append(str(exc))
                    continue
                for target, value in maxima.items():
                    if not start <= target <= end or target < issued.date() - timedelta(days=1):
                        continue
                    key = (target.isoformat(), header)
                    if key in seen:
                        continue
                    seen.add(key)
                    vintages[target.isoformat()].add(header)
                    records.append(
                        _observation(
                            source_id="nws-pfm",
                            entity_id=params["entity"],
                            variable="daytime_max_f",
                            valid_on=target,
                            value=value,
                            unit="degF",
                            model="NWS " + params["pil"],
                            revision_id=header,
                            issued_at=issued,
                            published_at=issued,
                            available_at=issued,
                            received_at=item.receipt.received_at,
                            ingested_at=max(now, item.receipt.received_at),
                            timing_basis="provider_publication",
                            evidence="Issuance from the product's WMO header and issuance line "
                            f"({header}); archived product text via IEM AFOS.",
                            role="feature",
                            raw_ref="raw:" + item.receipt.sha256,
                            raw_hash=item.receipt.sha256,
                        )
                    )
        entity = params["entity"]
        parsed.slices[(DataKind.FORECAST_VINTAGES, "daytime_max_f", "iem-nws-pfm", "issuance")] = {
            entity: set(vintages)
        }
        parsed.slices[(DataKind.FORECAST_REVISIONS, "daytime_max_f", "iem-nws-pfm", "issuance")] = {
            entity: {d for d, headers in vintages.items() if len(headers) >= 2}
        }
        return parsed


class CliAdapter(Adapter):
    adapter_id = "iem_afos_cli"

    def requests(self, params: dict[str, str]) -> list[str]:
        start = date.fromisoformat(params["start"])
        end = date.fromisoformat(params["end"]) + timedelta(days=3)
        return [_iem_url(params["pil"], a, b) for a, b in _chunks(start, end, 15)]

    def parse(self, fetched: list[Fetched], params: dict[str, str], now: datetime) -> Parsed:
        from entropytrade.weather.recorded import RecordedBodyError, parse_cli_daily_high

        start, end = date.fromisoformat(params["start"]), date.fromisoformat(params["end"])
        records: list[dict[str, Any]] = []
        parsed = Parsed(records=records, slices={})
        covered: set[str] = set()
        seen: set[str] = set()
        for item in fetched:
            for product in products(item.body.decode("utf-8", errors="replace")):
                try:
                    issued, header = issuance(product)
                    high = parse_cli_daily_high(
                        product, station=params["pil"], available_at=issued, ingested_at=issued
                    )
                except (ValueError, RecordedBodyError):
                    parsed.refused += 1  # same-day preliminary reports are refused here
                    continue
                if not start <= high.valid_on <= end or header in seen:
                    continue
                seen.add(header)
                covered.add(high.valid_on.isoformat())
                records.append(
                    _observation(
                        source_id="nws-cli",
                        entity_id=params["entity"],
                        variable="daily_high_f",
                        valid_on=high.valid_on,
                        value=high.high_f,
                        unit="degF",
                        revision_id=header,
                        issued_at=issued,
                        published_at=issued,
                        available_at=issued,
                        received_at=item.receipt.received_at,
                        ingested_at=max(now, item.receipt.received_at),
                        timing_basis="provider_publication",
                        evidence=f"Final NWS CLI report issued {header}; reference observation, "
                        "not the contract's settlement source.",
                        role="observation",
                        raw_ref="raw:" + item.receipt.sha256,
                        raw_hash=item.receipt.sha256,
                    )
                )
        if parsed.refused:
            parsed.notes.append(f"{parsed.refused} same-day or unparsable CLI products refused")
        parsed.slices[
            (DataKind.REFERENCE_OBSERVATIONS, "daily_high_f", "iem-nws-cli", "issuance")
        ] = {params["entity"]: covered}
        return parsed


class WeatherCompanyAdapter(Adapter):
    adapter_id = "weather_company_labels"

    def requests(self, params: dict[str, str]) -> list[str]:
        from entropytrade.weather.labels import URL

        start, end = date.fromisoformat(params["start"]), date.fromisoformat(params["end"])
        return [
            URL + (start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)
        ]

    def parse(self, fetched: list[Fetched], params: dict[str, str], now: datetime) -> Parsed:
        from entropytrade.weather.labels import (
            STATIONS,
            URL,
            LabelReceipt,
            LabelTarget,
            parse_label,
        )

        del now
        station = params["entity"]
        timezone_name = STATIONS[station][2]
        records: list[dict[str, Any]] = []
        parsed = Parsed(records=records, slices={})
        covered: set[str] = set()
        reasons: dict[str, int] = defaultdict(int)
        for item in fetched:
            day = date.fromisoformat(item.receipt.url.removeprefix(URL))
            receipt = LabelReceipt(
                url=item.receipt.url,
                received_at=item.receipt.received_at,
                status=item.receipt.status,
                headers=item.receipt.headers,
                body_base64=base64.b64encode(item.body).decode(),
            )
            target = LabelTarget(
                event_id=f"{params['series']}-{day.isoformat()}",
                station=station,
                target_date=day,
                timezone=timezone_name,
                rules_hashes=(),
            )
            try:
                observation = parse_label(target, receipt)
            except (ValueError, KeyError, TypeError) as exc:
                reasons[str(exc)[:120]] += 1
                parsed.refused += 1
                continue
            covered.add(day.isoformat())
            records.append(
                observation.model_dump(mode="json")
                | {"raw_ref": "raw:" + item.receipt.sha256, "raw_hash": item.receipt.sha256}
            )
        parsed.notes.extend(f"{n} refused: {reason}" for reason, n in sorted(reasons.items()))
        parsed.slices[
            (DataKind.SETTLEMENT_LABELS, "daily_high_f", "weather-company", "receipt")
        ] = {station: covered}
        return parsed


class KalshiSettledAdapter(Adapter):
    adapter_id = "kalshi_settled_markets"
    base = "https://api.elections.kalshi.com/trade-api/v2/markets"

    def _url(self, params: dict[str, str], cursor: str = "") -> str:
        start = datetime.combine(date.fromisoformat(params["start"]), datetime.min.time(), UTC)
        end = datetime.combine(date.fromisoformat(params["end"]), datetime.min.time(), UTC)
        query = {
            "series_ticker": params["series"],
            "status": "settled",
            "min_close_ts": int(start.timestamp()),
            "max_close_ts": int((end + timedelta(days=2)).timestamp()),
            "limit": 200,
        }
        if cursor:
            query["cursor"] = cursor
        return self.base + "?" + urlencode(query)

    def requests(self, params: dict[str, str]) -> list[str]:
        return [self._url(params)]

    def follow(self, fetched: Fetched, params: dict[str, str]) -> list[str]:
        cursor = json.loads(fetched.body).get("cursor") or ""
        if not isinstance(cursor, str) or not re.fullmatch(r"[A-Za-z0-9_=+/-]{1,512}", cursor):
            return []
        return [self._url(params, cursor)]

    def parse(self, fetched: list[Fetched], params: dict[str, str], now: datetime) -> Parsed:
        from entropytrade.exchange.kalshi.recorded import market_from_body
        from entropytrade.exchange.settlement import ticker_target_date

        del now
        start, end = date.fromisoformat(params["start"]), date.fromisoformat(params["end"])
        series = params["series"]
        records: list[dict[str, Any]] = []
        parsed = Parsed(records=records, slices={})
        contracts: set[str] = set()
        results: set[str] = set()
        for item in fetched:
            for row in json.loads(item.body).get("markets", []):
                try:
                    market = market_from_body(
                        row, captured_at=item.receipt.received_at, series=series
                    )
                except (ValueError, TypeError, KeyError):
                    parsed.refused += 1
                    continue
                target = ticker_target_date(market.ticker)
                if (
                    target is None
                    or not start <= target <= end
                    or not market.ticker.startswith(series + "-")
                ):
                    continue
                result = str(row.get("result") or "")
                contracts.add(target.isoformat())
                if result in {"yes", "no"}:
                    results.add(target.isoformat())
                records.append(
                    {
                        "record_type": "contract",
                        "ticker": market.ticker,
                        "event_ticker": market.event_ticker,
                        "target_date": target.isoformat(),
                        "strike": market.strike.model_dump(mode="json") if market.strike else None,
                        "close_time": market.close_time.isoformat(),
                        "result": result or None,
                        "status": market.status.value,
                        "rules_hash": market.rules.rules_hash,
                        "settlement_basis": market.rules.settlement_basis,
                        "settlement_sources": [s.name for s in market.rules.settlement_sources],
                        "rules_basis": "retrieved_after_settlement",
                        "received_at": item.receipt.received_at.isoformat(),
                        "raw_hash": item.receipt.sha256,
                    }
                )
        parsed.slices[(DataKind.MARKET_CONTRACTS, "contract_terms", "kalshi", "receipt")] = {
            series: contracts
        }
        parsed.slices[(DataKind.SETTLEMENT_LABELS, "binary_result", "kalshi", "receipt")] = {
            series: results
        }
        return parsed


ADAPTERS: dict[str, Adapter] = {
    a.adapter_id: a
    for a in (PfmAdapter(), CliAdapter(), WeatherCompanyAdapter(), KalshiSettledAdapter())
}


def adapter_params(
    source: SourceDescriptor, *, entity: str, series: str, start: date, end: date
) -> dict[str, str]:
    params = {
        "entity": entity,
        "series": series,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    params.update(source.entities.get(entity, {}))
    return params


def acquisition_key(source: SourceDescriptor, params: dict[str, str]) -> str:
    adapter = ADAPTERS[str(source.adapter)]
    return scientific_hash(
        {
            "source": source.source_id,
            "adapter": adapter.adapter_id,
            "version": adapter.version,
            "params": params,
        }
    )


def run_acquisition(
    root: Path,
    source: SourceDescriptor,
    params: dict[str, str],
    fetcher: Fetcher,
    *,
    now: Callable[[], datetime],
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Fetch, preserve, parse and publish one immutable dataset. Returns its manifest."""
    adapter = ADAPTERS[str(source.adapter)]
    queue = adapter.requests(params)
    fetched: list[Fetched] = []
    failures: list[dict[str, str]] = []
    pages = 0
    while queue:
        url = queue.pop(0)
        try:
            item = fetcher.get(url)
        except BudgetExceededError:
            raise
        except AcquisitionError as exc:
            if exc.reason == "cancelled":
                raise
            failures.append({"url": url, "error": exc.reason, "transient": str(exc.transient)})
            continue
        fetched.append(item)
        pages += 1
        if pages < 40:
            try:
                queue.extend(adapter.follow(item, params))
            except (ValueError, TypeError, KeyError) as exc:
                failures.append(
                    {
                        "url": url,
                        "error": f"pagination stopped ({type(exc).__name__})",
                        "transient": "False",
                    }
                )
        if progress is not None:
            progress(len(fetched), len(fetched) + len(queue))
    if not fetched:
        transient = all(f["transient"] == "True" for f in failures)
        raise AcquisitionError(
            "no source responses were retrieved: " + "; ".join(f["error"] for f in failures[:3]),
            transient=transient and bool(failures),
        )
    try:
        parsed = adapter.parse(fetched, params, now())
    except (ValueError, TypeError, KeyError) as exc:
        # Raw bytes stay preserved; nothing is published from an unparsable response.
        raise AcquisitionError(
            f"source response failed deterministic validation ({type(exc).__name__})",
            transient=False,
        ) from exc
    return publish(root, source, adapter, params, fetched, parsed, failures, created_at=now())


def publish(
    root: Path,
    source: SourceDescriptor,
    adapter: Adapter,
    params: dict[str, str],
    fetched: list[Fetched],
    parsed: Parsed,
    failures: list[dict[str, str]],
    *,
    created_at: datetime,
    fidelity_by_kind: Mapping[DataKind, Literal["any", "quote", "order_book"]] | None = None,
    data_kind: Literal["authentic", "synthetic"] = "authentic",
) -> dict[str, Any]:
    """Write a dataset directory atomically; identical content resolves to the same ID."""
    from entropytrade.data.sources import file_hash

    if data_kind not in {"authentic", "synthetic"}:
        raise ValueError("unsupported acquisition evidence kind")
    datasets = root / "datasets"
    datasets.mkdir(parents=True, exist_ok=True)
    staging = datasets / (".building-" + uuid4().hex)
    staging.mkdir()
    try:
        (staging / "records.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in parsed.records)
        )
        (staging / "receipts.jsonl").write_text(
            "".join(json.dumps(f.receipt.record(), sort_keys=True) + "\n" for f in fetched)
        )
        (staging / "parameters.json").write_text(
            json.dumps(
                {
                    "source_id": source.source_id,
                    "adapter": adapter.adapter_id,
                    "version": adapter.version,
                    "params": params,
                    # Synthetic fixtures must never collide with genuine responses,
                    # even when the supplied bytes and source descriptor are identical.
                    **({"data_kind": data_kind} if data_kind != "authentic" else {}),
                    **(
                        {
                            "fidelity_by_kind": {
                                kind.value: fidelity for kind, fidelity in fidelity_by_kind.items()
                            }
                        }
                        if fidelity_by_kind
                        else {}
                    ),
                },
                sort_keys=True,
            )
        )
        checksums = {
            name: file_hash(staging / name)
            for name in ("records.jsonl", "receipts.jsonl", "parameters.json")
        }
        content_hash = scientific_hash(checksums)
        dataset_id = content_hash
        records = [
            {
                "record_id": f"{dataset_id}#{kind.value}:{variable}:{source_id}",
                "dataset_id": dataset_id,
                "origin": "research_acquisition",
                "data_kind": data_kind,
                "kind": kind.value,
                "variable": variable,
                "family": "weather" if "weather" in source.families else source.families[0],
                "source_id": source_id,
                "clock": clock,
                "fidelity": (fidelity_by_kind or {}).get(kind, "any"),
                "coverage": {e: sorted(d) for e, d in coverage.items()},
                "created_at": created_at.isoformat(),
                "content_hash": content_hash,
                "path": f"research/datasets/sha256-{content_hash.removeprefix('sha256:')}",
                "verified": True,
                "detail": (
                    f"{source.name}: {len(parsed.records)} records from {len(fetched)} responses"
                ),
            }
            for (kind, variable, source_id, clock), coverage in parsed.slices.items()
        ]
        manifest = {
            "schema": DATASET_SCHEMA,
            "dataset_id": dataset_id,
            "content_hash": content_hash,
            "checksums": checksums,
            "source_id": source.source_id,
            "adapter": adapter.adapter_id,
            "adapter_version": adapter.version,
            "params": params,
            "created_at": created_at.isoformat(),
            "record_count": len(parsed.records),
            "responses": len(fetched),
            "refused": parsed.refused,
            "notes": parsed.notes[:40],
            "failures": failures,
            "raw_hashes": sorted({f.receipt.sha256 for f in fetched}),
            "data_kind": data_kind,
            "records": records,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=1))
        target = datasets / ("sha256-" + content_hash.removeprefix("sha256:"))
        if target.exists():
            existing = json.loads((target / "manifest.json").read_text())
            if existing["checksums"] != checksums or existing.get("data_kind") != data_kind:
                raise ValueError("existing dataset has different content for the same identity")
            shutil.rmtree(staging)
            return dict(existing)
        staging.replace(target)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def load_records(root: Path, dataset_id: str) -> list[dict[str, Any]]:
    """Records of a verified research dataset."""
    from entropytrade.data.sources import file_hash

    path = root / "datasets" / ("sha256-" + dataset_id.removeprefix("sha256:"))
    manifest = json.loads((path / "manifest.json").read_text())
    for name, digest in manifest["checksums"].items():
        if file_hash(path / name) != digest:
            raise ValueError("research dataset checksum mismatch")
    return [json.loads(line) for line in (path / "records.jsonl").read_text().splitlines() if line]


def host_of(url: str) -> str:
    return urlsplit(url).hostname or ""
