"""Exact acquired research features for bounded forward paper decisions.

PFM daytime maxima and CLI reference errors retain their original definitions. Hourly
forecast maxima never substitute for them. The cycle owns its response bytes/datasets;
this module cannot read or write the separate canonical collector chain.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from entropytrade.data.schema import Observation
from entropytrade.domain.enums import MarketStatus, MarketType
from entropytrade.domain.market import Market
from entropytrade.domain.time import Clock, SystemClock
from entropytrade.experiments.data import ExperimentData
from entropytrade.features.registry import scientific_hash
from entropytrade.research.acquire import (
    ADAPTERS,
    MAX_RESPONSE_BYTES,
    USER_AGENT,
    AcquisitionError,
    BudgetExceededError,
    Fetched,
    RawStore,
    Receipt,
    adapter_params,
    load_records,
    publish,
)
from entropytrade.research.materialize import decision_times, materialize
from entropytrade.research.model import DecisionPoint
from entropytrade.research.registry import FeatureDefinition, FeatureRegistry
from entropytrade.research.sources import SourceDescriptor, load_catalog
from entropytrade.research.store import reject_collector_chain

MAX_REQUESTS = 8
MAX_BYTES = 32_000_000
MAX_SECONDS = 60
SUPPORTED = frozenset({"nws_pfm_max_f", "nws_pfm_revision_f", "nws_cli_bias_f"})
SCHEMA = "research-forward-features-v1"


class SourceTransport(httpx.AsyncBaseTransport):
    """One reviewed source's bounded anonymous HTTPS GET boundary."""

    def __init__(self, source: SourceDescriptor, inner: httpx.AsyncBaseTransport | None) -> None:
        self.source = source
        self.owns_inner = inner is None
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        paths = {rule.host: rule.paths for rule in self.source.hosts}
        if (
            request.method != "GET"
            or url.scheme != "https"
            or url.port not in {None, 443}
            or url.userinfo
            or not any(
                url.path == path or url.path.startswith(path.rstrip("/") + "/")
                for path in paths.get(url.host, ())
            )
            or any(
                name.lower() in {"authorization", "cookie"} or "api-key" in name.lower()
                for name in request.headers
            )
        ):
            raise AcquisitionError(
                "paper feature source is outside its reviewed GET allowlist", transient=False
            )
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        if self.owns_inner:
            await self.inner.aclose()


@dataclass
class ForwardFeatureEvidence:
    root: Path
    definitions: tuple[FeatureDefinition, ...]
    records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    manifests: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    requests: int = 0
    bytes: int = 0
    summary: dict[str, Any] = field(default_factory=dict)


def _definitions(binding: dict[str, Any]) -> tuple[FeatureDefinition, ...]:
    if binding.get("kind") != "research_weather_v1":
        raise ValueError("not an acquired-research weather binding")
    if binding.get("status") != "bound" or scientific_hash(
        {key: value for key, value in binding.items() if key != "binding_hash"}
    ) != binding.get("binding_hash"):
        raise ValueError("forward research model binding is unverified")
    snapshot = binding["snapshot"]
    registry = FeatureRegistry()
    result = tuple(FeatureDefinition.model_validate(item) for item in snapshot["features"])
    if not result or len({item.feature_id for item in result}) != len(result):
        raise ValueError("forward research feature definitions are missing or repeated")
    if tuple(item.feature_id for item in result) != tuple(snapshot["feature_names"]):
        raise ValueError("forward research feature order differs from frozen model")
    if (
        scientific_hash([item.model_dump(mode="json") for item in result])
        != snapshot["feature_schema_hash"]
    ):
        raise ValueError("forward research feature schema hash mismatch")
    for item in result:
        if item.feature_id not in SUPPORTED or registry.get(item.feature_id) != item:
            raise ValueError("unsupported or changed exact forward research feature definition")
    return result


def _fail(evidence: ForwardFeatureEvidence, source: str, reason: str) -> None:
    evidence.failures.append({"source": source, "reason": reason})


async def acquire_research_features(
    root: Path,
    repo: Path,
    data: ExperimentData,
    binding: dict[str, Any],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Clock | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ForwardFeatureEvidence:
    """Acquire reviewed PFM/CLI inputs before the final book/decision clock is captured.

    A frozen one-minute decision window bounds work to the model's trained lead. Outside
    that window no IEM requests are made. At most eight GETs/32 MB/60 seconds are permitted.
    Raw failures remain evidence; missing inputs never receive a local fallback.
    """
    reject_collector_chain(root)
    root.mkdir(parents=True, exist_ok=False)
    now = (clock or SystemClock()).now
    evidence = ForwardFeatureEvidence(root, _definitions(binding))
    snapshot = binding["snapshot"]
    point = DecisionPoint.model_validate(snapshot["selected_schedule"])
    delay = int(snapshot["max_decision_delay_seconds"])
    if not 0 <= delay <= 60:
        raise ValueError("unsupported forward research decision delay")
    locations = snapshot["series_locations"]
    protected = set(snapshot.get("protected_events", []))
    selected: dict[str, tuple[str, Any]] = {}
    for sample in data.samples:
        location = locations.get(sample.family)
        if location is None or f"{location['entity']}:{sample.target_date}" in protected:
            continue
        scheduled = decision_times(sample.target_date, [point], location["timezone"])[0]
        if scheduled <= now() <= scheduled + timedelta(seconds=delay):
            selected[location["entity"]] = (sample.family, sample.target_date)
    if not selected:
        _fail(evidence, "schedule", "No unprotected contract is inside the frozen decision window")
    catalog = load_catalog(repo)
    raw = RawStore(root)
    wanted = {item.feature_id for item in evidence.definitions}
    source_ids = ("iem-nws-pfm", "iem-nws-cli") if "nws_cli_bias_f" in wanted else ("iem-nws-pfm",)
    last_request: float | None = None
    try:
        async with asyncio.timeout(MAX_SECONDS):
            for entity, (series, target) in selected.items():
                for source_id in source_ids:
                    source = catalog[source_id]
                    if (
                        source.access != "public_anonymous"
                        or source.cost != "free"
                        or entity not in source.entities
                        or source.adapter not in ADAPTERS
                    ):
                        _fail(
                            evidence,
                            source_id,
                            "No reviewed anonymous source mapping for this station",
                        )
                        continue
                    span = 21 if "nws_cli_bias_f" in wanted else 0
                    start = target - timedelta(days=span)
                    end = target - timedelta(days=1) if source_id == "iem-nws-cli" else target
                    params = adapter_params(
                        source, entity=entity, series=series, start=start, end=end
                    )
                    adapter = ADAPTERS[str(source.adapter)]
                    fetched = []
                    failures = []
                    async with httpx.AsyncClient(
                        transport=SourceTransport(source, transport),
                        timeout=15,
                        follow_redirects=False,
                        trust_env=False,
                        headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
                    ) as client:
                        for url in adapter.requests(params):
                            if evidence.requests >= MAX_REQUESTS:
                                raise AcquisitionError(
                                    "paper feature request budget exhausted", transient=False
                                )
                            loop = asyncio.get_running_loop()
                            if last_request is not None:
                                wait = source.rate_limit_seconds - (loop.time() - last_request)
                                if wait > 0:
                                    await sleep(wait)
                            last_request = loop.time()
                            evidence.requests += 1
                            try:
                                body = bytearray()
                                async with client.stream("GET", url) as response:
                                    async for chunk in response.aiter_bytes():
                                        body.extend(chunk)
                                        evidence.bytes += len(chunk)
                                        if (
                                            len(body) > MAX_RESPONSE_BYTES
                                            or evidence.bytes > MAX_BYTES
                                        ):
                                            raise BudgetExceededError(
                                                "paper feature byte budget exhausted"
                                            )
                                    at = now()
                                    digest = raw.put(bytes(body))
                                    receipt = Receipt(
                                        url,
                                        response.status_code,
                                        at,
                                        digest,
                                        len(body),
                                        {
                                            k: v
                                            for k, v in response.headers.items()
                                            if k.lower()
                                            in {"date", "content-type", "etag", "last-modified"}
                                        },
                                    )
                                evidence.receipts.append(receipt.record())
                                if receipt.status != 200:
                                    raise AcquisitionError(
                                        "paper feature source returned HTTP failure",
                                        transient=False,
                                    )
                                fetched.append(Fetched(receipt, bytes(body)))
                            except (httpx.HTTPError, AcquisitionError) as exc:
                                if isinstance(exc, BudgetExceededError):
                                    raise
                                reason = (
                                    exc.reason
                                    if isinstance(exc, AcquisitionError)
                                    else type(exc).__name__
                                )
                                _fail(evidence, source_id, reason)
                                failures.append({"url": url, "error": reason})
                    try:
                        parsed = adapter.parse(fetched, params, now())
                        manifest = publish(
                            root,
                            source,
                            adapter,
                            params,
                            fetched,
                            parsed,
                            failures,
                            created_at=now(),
                        )
                        evidence.manifests.append(manifest)
                        evidence.records.setdefault(entity, []).extend(parsed.records)
                    except (ValueError, TypeError, KeyError):
                        _fail(evidence, source_id, "Source products failed exact PFM/CLI parsing")
    except (TimeoutError, AcquisitionError) as exc:
        _fail(
            evidence,
            "budget",
            "Paper feature acquisition time or request budget exhausted"
            if isinstance(exc, TimeoutError)
            else exc.reason,
        )
    summary = {
        "schema": SCHEMA,
        "transport": "live" if transport is None else "controlled_injected_transport",
        "datasets": [item["dataset_id"] for item in evidence.manifests],
        "receipts": evidence.receipts,
        "failures": evidence.failures,
        "requests": evidence.requests,
        "bytes": evidence.bytes,
        "feature_schema_hash": snapshot["feature_schema_hash"],
        "definitions": [item.model_dump(mode="json") for item in evidence.definitions],
        "observed_at": now().isoformat(),
        "submission_enabled": False,
    }
    (root / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2))
    evidence.summary = summary
    return evidence


def materialize_research_features(
    data: ExperimentData,
    evidence: ForwardFeatureEvidence,
    markets: dict[str, Market],
    binding: dict[str, Any],
    *,
    persist: bool = True,
) -> ExperimentData:
    """Reuse the registry's exact transforms at the final receipt-bounded decision clock."""
    reject_collector_chain(evidence.root)
    definitions = _definitions(binding)
    if evidence.definitions != definitions:
        raise ValueError("acquired and materialized forward definitions differ")
    # Every dataset and original byte is checked again at its point of use. No joblib,
    # executable model or caller-selected source path is loaded.
    from entropytrade.research.modeling import _dataset

    verified_records: dict[str, list[dict[str, Any]]] = {}
    for manifest in evidence.manifests:
        _dataset(evidence.root, manifest["dataset_id"], "real")
        for raw in load_records(evidence.root, manifest["dataset_id"]):
            record = Observation.model_validate(raw)
            if record.unit != "degF" or record.source_id not in {"nws-pfm", "nws-cli"}:
                raise ValueError("unsupported research paper source type or units")
            verified_records.setdefault(record.entity_id, []).append(raw)
    snapshot = binding["snapshot"]
    locations = snapshot["series_locations"]
    protected = set(snapshot.get("protected_events", []))
    samples = []
    lineage = {}
    for sample in data.samples:
        location = locations.get(sample.family)
        entity = location["entity"] if location else ""
        if f"{entity}:{sample.target_date}" in protected:
            continue
        features: dict[str, Decimal | None] = {item.feature_id: None for item in definitions}
        clocks = []
        details = {}
        records = [
            record
            for record in verified_records.get(entity, [])
            if f"{entity}:{record['valid_on']}" not in protected
        ]
        if location and not evidence.failures:
            local = sample.decision_time.astimezone(ZoneInfo(location["timezone"]))
            point = DecisionPoint(
                day_offset=(local.date() - sample.target_date).days,
                local_time=local.timetz().replace(tzinfo=None),
            )
            for definition in definitions:
                row = materialize(
                    definition,
                    entity=entity,
                    timezone=location["timezone"],
                    schedule=[point],
                    window=(sample.target_date, sample.target_date),
                    inputs={"forecast": records, "observation": records},
                )[0]
                if row["value"] is not None:
                    # Publication is a historical evidence clock. This paper decision must
                    # also wait for the actual acquisition receipt of every used product.
                    issued = datetime.fromisoformat(row["inputs_available_at"])
                    receipts = [
                        datetime.fromisoformat(item["received_at"])
                        for item in records
                        if item["received_at"] is not None
                    ]
                    available = max([issued, *receipts])
                    if available <= sample.decision_time:
                        features[definition.feature_id] = Decimal(row["value"])
                        clocks.append(available)
                        details[definition.feature_id] = row | {
                            "paper_available_at": available.isoformat()
                        }
        complete = all(value is not None for value in features.values())
        market = markets.get(sample.ticker)
        text = (
            (market.rules.rules_primary + market.rules.rules_secondary).casefold()
            if market is not None
            else ""
        )
        authorities = (
            " ".join(source.name.casefold() for source in market.rules.settlement_sources)
            if market is not None
            else ""
        )
        semantic = (
            market is not None
            and market.market_type is MarketType.BINARY
            and market.status is MarketStatus.ACTIVE
            and market.ticker == sample.ticker
            and market.event_ticker == sample.event_id
            and market.series_ticker == sample.family
            and market.rules.captured_at <= sample.decision_time
            and market.open_time <= sample.decision_time < market.close_time
            and location is not None
            and location["name"].casefold() in text
            and market.rules.settlement_basis == "contract_text"
            and market.rules.settlement_target_date == sample.target_date
            and market.strike is not None
            and market.strike.is_evaluable
            and "weather company" in authorities
            and "weather company" in text
            and "national weather service" not in authorities
            and "nws" not in authorities
            and ("fahrenheit" in text or "°f" in text)
        )
        identity = {
            "previous": sample.feature_hash,
            "decision": sample.decision_time.isoformat(),
            "schema": snapshot["feature_schema_hash"],
            "datasets": [item["dataset_id"] for item in evidence.manifests],
            "features": {
                name: str(value) if value is not None else None for name, value in features.items()
            },
            "lineage": details,
        }
        sources = set(sample.sources) - {"verified-research-features"}
        if complete:
            sources.add("verified-research-features")
        samples.append(
            sample.revalidated(
                features=features,
                versions={item.feature_id: item.version for item in definitions},
                feature_hash=scientific_hash(identity),
                features_available_at=max(clocks, default=sample.decision_time),
                sources=tuple(sorted(sources)),
                eligible=complete and semantic and sample.rules_known,
            )
        )
        lineage[sample.ticker] = details
    schema = {
        "schema": SCHEMA,
        "feature_schema_hash": snapshot["feature_schema_hash"],
        "features": [item.model_dump(mode="json") for item in definitions],
    }
    summary = evidence.summary | {"lineage": lineage}
    materialization = json.dumps(summary, sort_keys=True, indent=2)
    materialization_hash = "sha256:" + sha256(materialization.encode()).hexdigest()
    if persist:
        (evidence.root / "materialization.json").write_text(materialization)
    elif (evidence.root / "materialization.json").read_text() != materialization:
        raise ValueError("saved research feature materialization differs from verified inputs")
    return data.revalidated(
        samples=tuple(samples),
        feature_definitions=schema,
        feature_version=scientific_hash(
            {
                "schema": schema,
                "source": data.feature_version,
                "materialization": materialization_hash,
            }
        ),
        provenance=data.provenance
        | {
            "adapter": "research-forward-v1:weather",
            "research_features": summary,
            "feature_schema_hash": snapshot["feature_schema_hash"],
        },
    )


def load_research_evidence(root: Path, binding: dict[str, Any]) -> ForwardFeatureEvidence:
    """Read a committed cycle's immutable evidence without polling or changing its files."""
    from entropytrade.research.modeling import _dataset

    definitions = _definitions(binding)
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("paper research evidence cannot traverse symlinks")
    summary: dict[str, Any] = json.loads((root / "summary.json").read_text())
    if (
        summary.get("schema") != SCHEMA
        or summary.get("feature_schema_hash") != binding["snapshot"]["feature_schema_hash"]
        or summary.get("definitions") != [item.model_dump(mode="json") for item in definitions]
    ):
        raise ValueError("paper research source summary/schema mismatch")
    raw = RawStore(root)
    for receipt in summary["receipts"]:
        if len(raw.get(receipt["sha256"])) != receipt["bytes"]:
            raise ValueError("paper research raw receipt length mismatch")
    manifests = []
    for identifier in summary["datasets"]:
        _dataset(root, identifier, "real")
        path = root / "datasets" / ("sha256-" + identifier.removeprefix("sha256:"))
        manifests.append(json.loads((path / "manifest.json").read_text()))
    return ForwardFeatureEvidence(
        root=root,
        definitions=definitions,
        manifests=manifests,
        receipts=summary["receipts"],
        failures=summary["failures"],
        requests=summary["requests"],
        bytes=summary["bytes"],
        summary=summary,
    )


def reconstruct_research_data(
    root: Path, public: ExperimentData, result: dict[str, Any], execution: dict[str, Any]
) -> ExperimentData:
    """Rebuild exact receipt-clock research features for offline recovery/prospective use."""
    from entropytrade.data.schema import MarketEvidence
    from entropytrade.domain.strategy import StrategySpec
    from entropytrade.exchange.kalshi.recorded import public_book_from_body
    from entropytrade.research.paper_models import PortableResearchModel, paper_window

    binding = result["model_binding"]
    model = PortableResearchModel.model_validate(binding["snapshot"])
    inputs = json.loads((root / "decision-inputs.json").read_text())
    spec = StrategySpec.model_validate(inputs["spec"])
    universe = spec.market_universe
    at = datetime.fromisoformat(execution["decision_time"])
    window_at = datetime.fromisoformat(result["research_window_at"])
    if window_at.utcoffset() is None or window_at > at:
        raise ValueError("research paper window selection clock is invalid")
    protected = set(public.protected_events) | set(model.protected_events)
    protected.update(
        sample.event_id
        for sample in public.samples
        if model.protects(
            series=sample.family, target_date=sample.target_date, event_id=sample.event_id
        )
    )
    samples = []
    markets = {}
    for line in (root / "public/markets.jsonl").read_text().splitlines():
        market = MarketEvidence.model_validate_json(line).market
        markets[market.ticker] = market
    for original in public.samples:
        if (
            original.event_id in protected
            or paper_window(binding, window_at, original.family) != original.target_date
            or not (
                original.ticker in universe.market_tickers
                or original.event_id in universe.event_tickers
                or original.family in universe.series_tickers
            )
        ):
            continue
        features = {
            **original.features,
            "hours_to_close": Decimal(str((original.close_time - at).total_seconds()))
            / Decimal(3600),
        }
        matching = [
            receipt
            for receipt in execution["receipts"]
            if receipt["status"] == 200
            and receipt["path"] == f"/trade-api/v2/markets/{original.ticker}/orderbook"
        ]
        if len(matching) > 1:
            raise ValueError("research paper book has ambiguous original receipts")
        book = None
        if matching:
            receipt = matching[0]
            path = root / receipt["raw_ref"]
            if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
                raise ValueError("research paper receipt path escaped the cycle")
            book = public_book_from_body(
                json.loads(path.read_text()),
                ticker=original.ticker,
                received_at=datetime.fromisoformat(receipt["received_at"]),
            )
        samples.append(
            original.revalidated(
                decision_time=at,
                features=features,
                versions={**original.versions, "hours_to_close": "1"},
                feature_hash=scientific_hash(
                    {
                        "source_features": original.feature_hash,
                        "decision": at.isoformat(),
                        "features": {key: str(value) for key, value in features.items()},
                    }
                ),
                rules_known=original.rules_known and original.ticker not in result["changed_terms"],
                book=book,
                fidelity="order_book" if book is not None else "missing",
            )
        )
    data = public.revalidated(
        samples=tuple(samples),
        protected_events=frozenset(protected),
        provenance=public.provenance | {"deployment_created_at": result["deployment_created_at"]},
    )
    evidence = load_research_evidence(root / "research-features", binding)
    if evidence.summary != result["research_features"]:
        raise ValueError("research feature source summary differs from committed cycle")
    return materialize_research_features(data, evidence, markets, binding, persist=False)
