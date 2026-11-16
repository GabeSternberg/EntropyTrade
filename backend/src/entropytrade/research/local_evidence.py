"""Copy verified retained workspace execution receipts into immutable research datasets.

Only ``workspace/runs/weather-datasets`` is consumed. No caller-selected source path,
collector-chain access, network request, monitor start, or exchange order is possible.
Source-protected events and calendar partitions are inherited before any record is copied.
"""

import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlsplit

from entropytrade.data.schema import MarketEvidence, MarketState
from entropytrade.data.sources import file_hash
from entropytrade.domain.enums import MarketResult, MarketStatus
from entropytrade.exchange.kalshi.recorded import market_from_body
from entropytrade.exchange.settlement import ticker_target_date
from entropytrade.experiments.data import ExperimentData
from entropytrade.families.public import forward_data
from entropytrade.features.registry import scientific_hash
from entropytrade.research.acquire import Adapter, Fetched, Parsed, RawStore, Receipt, publish
from entropytrade.research.model import DataKind
from entropytrade.research.sources import load_catalog
from entropytrade.tracking.history import verified_inputs
from entropytrade.weather.history import load_snapshot

ADAPTER = "local_restored_execution"
MAX_SNAPSHOTS = 128
MAX_SOURCE_BYTES = 256_000_000


class LocalExecutionAdapter(Adapter):
    adapter_id = ADAPTER
    version = "2"


def _safe(path: Path, workspace: Path) -> Path:
    if not path.resolve().is_relative_to(workspace.resolve()) or any(
        part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(workspace)
    ):
        raise ValueError("local execution evidence cannot traverse symlinks or escape workspace")
    return path


def _clock(value: str, now: datetime) -> datetime:
    at = datetime.fromisoformat(value)
    if at.utcoffset() is None or at > now:
        raise ValueError("original execution receipt has an unknown or future clock")
    return at


def _metadata(path: Path, workspace: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(_safe(path / "snapshot.json", workspace).read_text())
    if (
        value.get("schema") != "retained-weather-v1"
        or scientific_hash(value["identity"]) != value["dataset_id"]
        or path.name != value["dataset_id"].removeprefix("sha256:")
    ):
        raise ValueError("local weather snapshot identity mismatch")
    boundaries = value["identity"]["temporal_boundaries"]
    parsed = [date.fromisoformat(day) for day in boundaries]
    if len(parsed) != 3 or not parsed[0] < parsed[1] < parsed[2]:
        raise ValueError("local weather snapshot partition mismatch")
    return value


def _receipt(path: Path, value: dict[str, Any], workspace: Path, now: datetime) -> Fetched:
    body = _safe(path, workspace).read_bytes()
    digest = value.get("sha256", value.get("hash"))
    if value["status"] != 200 or file_hash(path) != digest:
        raise ValueError("local execution raw receipt checksum/status mismatch")
    original = str(value["path"])
    url = (
        original
        if original.startswith("https://")
        else "https://api.elections.kalshi.com" + original
    )
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname != "api.elections.kalshi.com"
        or parts.username
        or parts.password
        or not parts.path.startswith("/trade-api/v2/markets")
    ):
        raise ValueError("local execution receipt is not an approved public market source")
    return Fetched(
        Receipt(url, 200, _clock(value["received_at"], now), str(digest), len(body), {}), body
    )


def _market(fetched: Fetched, ticker: str, raw_ref: str) -> MarketEvidence:
    value = json.loads(fetched.body)
    candidates = value.get("markets", [value.get("market")])
    matching = [m for m in candidates if isinstance(m, dict) and m.get("ticker") == ticker]
    if len(matching) != 1:
        raise ValueError("market receipt lacks unique original contract")
    raw = matching[0]
    market = market_from_body(
        raw, captured_at=fetched.receipt.received_at, series=ticker.split("-")[0]
    )
    created = raw.get("created_time")
    return MarketEvidence(
        market=market,
        created_at=_clock(created, fetched.receipt.received_at) if created else None,
        capture_basis="receipt",
        raw_ref=raw_ref,
        raw_hash=fetched.receipt.sha256,
    )


def _collect(
    snapshot: Path,
    workspace: Path,
    protected: set[str],
    holdout: date,
    now: datetime,
) -> tuple[
    list[dict[str, Any]], list[Fetched], dict[tuple[DataKind, str, str, str], dict[str, set[str]]]
]:
    records: dict[str, dict[str, Any]] = {}
    fetched: dict[tuple[str, str], Fetched] = {}
    slices: dict[tuple[DataKind, str, str, str], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    def excluded(ticker: str, event: str = "") -> bool:
        target = ticker_target_date(ticker)
        return event in protected or target is None or target >= holdout

    def add_market(item: MarketEvidence, response: Fetched) -> None:
        if excluded(item.market.ticker, item.market.event_ticker):
            return
        record = {
            "record_type": "market_evidence",
            **item.model_dump(mode="json", exclude_computed_fields=True),
        }
        records[scientific_hash(record)] = record
        fetched[(response.receipt.sha256, response.receipt.received_at.isoformat())] = response
        target = ticker_target_date(item.market.ticker)
        assert target is not None  # noqa: S101 - excluded above
        series = item.market.series_ticker
        if series is None:
            raise ValueError("original market lacks a series identifier")
        slices[(DataKind.MARKET_CONTRACTS, "contract_terms", "kalshi", "receipt")][series].add(
            target.isoformat()
        )

    for capture in sorted((snapshot / "receipts").glob("*")):
        _safe(capture, workspace)
        data = forward_data(capture)
        if data.data_kind != "real" or data.provenance["capture"]["family"] != "weather":
            raise ValueError("only authentic weather captures support local execution import")
        receipts = json.loads((capture / "capture.json").read_text())["receipts"]
        for line in (capture / "markets.jsonl").read_text().splitlines():
            serialized = json.loads(line)
            identity = serialized["market"]
            ticker = identity["ticker"]
            matches = [
                r
                for r in receipts
                if r["raw_ref"] == serialized["raw_ref"] and r.get("hash") == serialized["raw_hash"]
            ]
            if len(matches) != 1:
                raise ValueError("normalized market lacks unique original receipt")
            response = _receipt(capture / serialized["raw_ref"], matches[0], workspace, now)
            if excluded(ticker, identity["event_ticker"]):
                # Only an identity shell enters replay cutoff calculations. Source
                # integrity verification may hash the raw bytes; no protected outcome,
                # rule, feature, or probability is deserialized by this projection.
                day = ticker_target_date(ticker)
                if day is None:
                    continue
                shell = {
                    "record_type": "protected_identity",
                    "ticker": ticker,
                    "series": identity["series_ticker"],
                    "target_date": day.isoformat(),
                    "close_time": identity["close_time"],
                    "raw_hash": serialized["raw_hash"],
                    "raw_ref": serialized["raw_ref"],
                }
                records[scientific_hash(shell)] = shell
                fetched[(response.receipt.sha256, response.receipt.received_at.isoformat())] = (
                    response
                )
                continue
            saved = MarketEvidence.model_validate(serialized)
            item = _market(response, saved.market.ticker, saved.raw_ref)
            if item.market != saved.market or saved.capture_basis != "receipt":
                raise ValueError("normalized market differs from original raw response")
            add_market(item, response)

    replay_path = snapshot / "shadow-replay.json"
    if replay_path.is_file():
        replay = json.loads(replay_path.read_text())
        for cycle in replay["cycles"]:
            cycle_root = _safe(snapshot / cycle["evidence"], workspace)
            inputs = verified_inputs(cycle_root)
            data = ExperimentData.model_validate(inputs["data"])
            if data.data_kind != "real":
                raise ValueError("synthetic shadow evidence cannot become authentic execution data")
            summary = json.loads((cycle_root / "execution/summary.json").read_text())
            for sample in data.samples:
                if sample.book is None or excluded(sample.ticker, sample.event_id):
                    continue
                matches = [
                    r
                    for r in summary["receipts"]
                    if r["status"] == 200
                    and r["path"] == f"/trade-api/v2/markets/{sample.ticker}/orderbook"
                ]
                if len(matches) != 1:
                    raise ValueError("sized book lacks unique verified original receipt")
                receipt = matches[0]
                response = _receipt(cycle_root / receipt["raw_ref"], receipt, workspace, now)
                book = sample.book
                if book.received_at != response.receipt.received_at:
                    raise ValueError("book clock differs from original receipt")
                state = MarketState(
                    market_ticker=sample.ticker,
                    event_time=book.exchange_ts or book.received_at,
                    available_at=book.received_at,
                    received_at=book.received_at,
                    ingested_at=book.received_at,
                    fidelity="order_book",
                    payload=book.model_dump(mode="json"),
                    raw_ref=receipt["raw_ref"],
                    raw_hash=response.receipt.sha256,
                )
                record = {"record_type": "market_state", **state.model_dump(mode="json")}
                records[scientific_hash(record)] = record
                fetched[(response.receipt.sha256, response.receipt.received_at.isoformat())] = (
                    response
                )
                if book.bids and book.asks and not book.is_crossed:
                    for kind, variable in (
                        (DataKind.DECISION_QUOTES, "yes_quotes"),
                        (DataKind.ORDER_BOOK_DEPTH, "yes_book"),
                    ):
                        slices[(kind, variable, "kalshi", "receipt")][sample.family].add(
                            sample.target_date.isoformat()
                        )

    for summary_path in sorted((snapshot / "labels").glob("*/summary.json")):
        summary = json.loads(_safe(summary_path, workspace).read_text())
        for outcome in summary["outcomes"]:
            if excluded(outcome["ticker"]):
                continue
            receipt = outcome["receipt"]
            path = summary_path.parent / Path(receipt["raw_ref"]).name
            response = _receipt(path, receipt, workspace, now)
            item = _market(response, outcome["ticker"], receipt["raw_ref"])
            market = item.market
            raw = json.loads(response.body)["market"]
            if (
                market.status is not MarketStatus.FINALIZED
                or market.result not in {MarketResult.YES, MarketResult.NO}
                or market.settlement_ts is None
                or not market.close_time <= market.settlement_ts <= response.receipt.received_at
                or market.settlement_value != (1 if market.result is MarketResult.YES else 0)
                or raw.get("is_provisional") not in {None, False}
                or outcome["available_at"] != receipt["received_at"]
                or outcome["result"] != market.result.value
            ):
                raise ValueError("local finalized outcome lacks matching original receipt")
            add_market(item, response)
    return (
        [records[k] for k in sorted(records)],
        [fetched[k] for k in sorted(fetched)],
        dict(slices),
    )


def local_execution_evidence(
    workspace: Path, *, now: datetime, max_bytes: int = 96_000_000
) -> dict[str, Any]:
    """Consume only copied snapshots in this configured research workspace; never the chain."""
    if now.utcoffset() is None or max_bytes < 0:
        raise ValueError("local evidence requires an aware clock and nonnegative byte budget")
    if any(p.name == "chain" or (p / ".chain").exists() for p in (workspace, *workspace.parents)):
        raise ValueError("research cannot consume the canonical collector chain directly")
    if any(p.is_symlink() for p in (workspace, *workspace.parents)):
        raise ValueError("research workspace cannot traverse symlinks")
    root = workspace / "research"
    for output in (root, root / "raw", root / "datasets"):
        _safe(output, workspace)
    result: dict[str, Any] = {
        "dataset_ids": [],
        "source_snapshots": [],
        "problems": [],
        "imported_bytes": 0,
        "inherited_boundaries": {},
        "protected_events": [],
        "block_modeling": False,
    }
    source = workspace / "runs/weather-datasets"
    _safe(source, workspace)
    paths = sorted(source.glob("[0-9a-f]" * 64)) if source.is_dir() else []
    if len(paths) > MAX_SNAPSHOTS:
        result["problems"].append(
            {
                "type": "SnapshotBudget",
                "reason": "Local snapshot count exceeds the bounded import limit",
            }
        )
        result["block_modeling"] = True
        return result
    manifests = []
    try:
        manifests = [(path, _metadata(path, workspace)) for path in paths]
    except (ValueError, OSError, KeyError, TypeError):
        result["problems"].append(
            {
                "type": "InvalidSnapshot",
                "reason": "Local weather snapshot metadata failed verification",
            }
        )
        result["block_modeling"] = True
        return result
    candidates: list[tuple[str, dict[str, str]]] = []
    current_ids: set[str] = set()
    # The copied immutable dataset is self-contained; later calls need not reparse source
    # raw receipts to reuse it. Modeling independently verifies its checksums before use.
    from entropytrade.research.modeling import _dataset

    for directory in sorted((root / "datasets").glob("sha256-*")):
        try:
            parameters = json.loads(_safe(directory / "parameters.json", workspace).read_text())
            if parameters.get("adapter") != ADAPTER:
                continue
            identifier = "sha256:" + directory.name.removeprefix("sha256-")
            _dataset(root, identifier, "real")
            params = parameters["params"]
            candidates.append((identifier, params))
            if parameters.get("version") == LocalExecutionAdapter.version:
                current_ids.add(identifier)
        except (ValueError, OSError, KeyError, TypeError):
            result["problems"].append(
                {
                    "type": "InvalidLocalDataset",
                    "reason": "Previously copied local execution dataset failed verification",
                }
            )
            result["block_modeling"] = True
            return result
    if not manifests and not candidates:
        result["dataset_ids"] = ()
        return result
    # Only fully verified or self-contained, previously verified source metadata can
    # install durable modeling protection. Invalid new snapshots block modeling rather
    # than poisoning the global boundary table with unverified clocks.
    verified_source_bytes = 0
    try:
        for path, metadata in manifests:
            reused = any(
                params["source_snapshot"] == metadata["dataset_id"]
                and params["source_manifest_hash"] == file_hash(path / "snapshot.json")
                for _, params in candidates
            )
            if not reused:
                source_size = sum(
                    _safe(path / name, workspace).stat().st_size for name in metadata["checksums"]
                )
                verified_source_bytes += source_size
                if max_bytes == 0 or verified_source_bytes > MAX_SOURCE_BYTES:
                    raise ValueError("local evidence byte budget exhausted")
                if load_snapshot(path) != metadata:
                    raise ValueError("local snapshot changed during verification")
    except (ValueError, OSError, KeyError, TypeError):
        result["problems"].append(
            {
                "type": "InvalidSnapshot",
                "reason": "New local snapshot could not be verified within the import budget",
            }
        )
        result["block_modeling"] = True
        return result
    cuts = [m["identity"]["temporal_boundaries"] for _, m in manifests] + [
        json.loads(params["temporal_boundaries"]) for _, params in candidates
    ]
    boundaries = [min(c[i] for c in cuts) for i in range(3)]
    protected = {event for _, m in manifests for event in m["identity"]["protected_events"]} | {
        event for _, params in candidates for event in json.loads(params["protected_events"])
    }
    protected_dates = [ticker_target_date(event) for event in protected]
    if any(day is None or day < date.fromisoformat(boundaries[2]) for day in protected_dates):
        result["problems"].append(
            {
                "type": "SourceProtectionConflict",
                "reason": "Inherited protected events precede the shared source holdout; "
                "automatic modeling is refused without a compatible protection partition",
            }
        )
        result["block_modeling"] = True
        return result
    result["inherited_boundaries"] = {"weather": boundaries}
    result["protected_events"] = sorted(protected)
    protection_hash = scientific_hash({"boundaries": boundaries, "protected": sorted(protected)})
    cache = {
        params["source_snapshot"]: identifier
        for identifier, params in candidates
        if params["protection_hash"] == protection_hash and identifier in current_ids
    }
    if not manifests:
        result["dataset_ids"] = tuple(sorted(set(cache.values())))
        result["source_snapshots"] = sorted(cache)
        return result
    present = {metadata["dataset_id"] for _, metadata in manifests}
    for identifier, params in candidates:
        if params["source_snapshot"] not in present:
            result["dataset_ids"].append(identifier)
            result["source_snapshots"].append(params["source_snapshot"])
    descriptor = load_catalog(Path(__file__).resolve().parents[4])[
        "kalshi-orderbook-forward"
    ].revalidated(
        source_id="local-restored-execution", name="Verified restored local execution receipts"
    )
    for path, metadata in manifests:
        version = metadata["dataset_id"]
        if version in cache:
            result["dataset_ids"].append(cache[version])
            result["source_snapshots"].append(version)
            continue
        try:
            # Reject unbounded sources before expensive parsing or copying. Manifest file
            # paths are verified by load_snapshot before any source payload is consumed.
            records, responses, slices = _collect(
                path, workspace, protected, date.fromisoformat(boundaries[2]), now
            )
            if (
                any(
                    file_hash(_safe(path / name, workspace)) != digest
                    for name, digest in metadata["checksums"].items()
                )
                or json.loads(_safe(path / "snapshot.json", workspace).read_text()) != metadata
            ):
                raise ValueError("local snapshot changed while preparing immutable copy")
            if not records:
                continue
            unique_raw = {f.receipt.sha256: f.body for f in responses}
            new_raw = sum(
                len(body)
                for digest, body in unique_raw.items()
                if not (
                    root
                    / "raw"
                    / digest.removeprefix("sha256:")[:2]
                    / digest.removeprefix("sha256:")
                ).exists()
            )
            # Serialize the complete immutable dataset before copying any raw bytes.
            # Coverage/parameters can grow with protected events: a fixed metadata
            # estimate is not a hard budget. Temporary planning output is removed.
            root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=".local-stage-", dir=root) as temporary:
                staged_root = Path(temporary)
                manifest = publish(
                    staged_root,
                    descriptor,
                    LocalExecutionAdapter(),
                    {
                        "source_snapshot": version,
                        "source_manifest_hash": file_hash(path / "snapshot.json"),
                        "protection_hash": scientific_hash(
                            {"boundaries": boundaries, "protected": sorted(protected)}
                        ),
                        "temporal_boundaries": json.dumps(boundaries),
                        "protected_events": json.dumps(sorted(protected)),
                    },
                    responses,
                    Parsed(
                        records,
                        slices,
                        notes=[
                            "Original public receipt clocks retained; "
                            "local copy is not prospective validation."
                        ],
                    ),
                    [],
                    created_at=now,
                    fidelity_by_kind={
                        DataKind.DECISION_QUOTES: "order_book",
                        DataKind.ORDER_BOOK_DEPTH: "order_book",
                    },
                )
                name = "sha256-" + manifest["dataset_id"].removeprefix("sha256:")
                staged = staged_root / "datasets" / name
                target = _safe(root / "datasets" / name, workspace)
                if target.exists():
                    _dataset(root, manifest["dataset_id"], "real")
                else:
                    dataset_bytes = sum(p.stat().st_size for p in staged.iterdir())
                    if new_raw + dataset_bytes > max_bytes - result["imported_bytes"]:
                        raise ValueError("local evidence byte budget exhausted")
                    raw_store = RawStore(root)
                    for digest, body in unique_raw.items():
                        hexdigest = digest.removeprefix("sha256:")
                        raw_path = _safe(root / "raw" / hexdigest[:2] / hexdigest, workspace)
                        existed = raw_path.exists()
                        if raw_store.put(body) != digest:
                            raise ValueError("raw receipt changed during local copy")
                        if not existed:
                            result["imported_bytes"] += len(body)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    staged.rename(target)
                    result["imported_bytes"] += dataset_bytes
            result["dataset_ids"].append(manifest["dataset_id"])
            result["source_snapshots"].append(version)
        except (ValueError, OSError, KeyError, TypeError):
            result["problems"].append(
                {
                    "type": "LocalEvidenceRefused",
                    "reason": "Local execution snapshot failed verification "
                    "or exceeded the import budget",
                }
            )
    result["dataset_ids"] = tuple(sorted(set(result["dataset_ids"])))
    return result
