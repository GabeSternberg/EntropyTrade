"""Authentic portal-byte replay plus explicitly controlled refusal/revision mutations."""

import asyncio
import base64
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from entropytrade.api.jobs import Jobs
from entropytrade.ml.experiment import _examples
from entropytrade.weather.history import build_snapshot, load_snapshot
from entropytrade.weather.label_service import LabelService, batches
from entropytrade.weather.labels import (
    URL,
    LabelReceipt,
    LabelTarget,
    load_batch,
    parse_label,
    targets,
)
from tests.integration.weather_history_retained import REPO, SOURCE, seed_retained

PROBE = REPO / "data/weather-label-review/20261031/probe"


def receipt(day: str = "2026-10-29", body: dict[str, Any] | None = None) -> LabelReceipt:
    metadata = json.loads(
        (
            PROBE / ("primary-29-receipt.json" if day.endswith("29") else "primary-receipt.json")
        ).read_text()
    )
    raw = (
        (PROBE / f"primary-{day}.json").read_bytes() if body is None else json.dumps(body).encode()
    )
    return LabelReceipt(
        url=URL + day,
        status=200,
        received_at=datetime.fromisoformat(metadata["received_at"]),
        headers={"content-type": "application/json"},
        body_base64=base64.b64encode(raw).decode(),
    )


def target() -> LabelTarget:
    return LabelTarget(
        event_id="KXHIGHPHIL-26OCT29",
        station="CLIPHL",
        target_date=date(2026, 10, 29),
        timezone="America/New_York",
        rules_hashes=("controlled-unit-rule",),
    )


def response_body() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(receipt().body())
    return value


def philly(body: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in body["results"] if r["station"]["cliId"] == "PHL")


def test_authentic_portal_high_preserves_unknown_publication_and_real_receipt() -> None:
    source = receipt()
    item = parse_label(target(), source)
    assert item.value == 70
    assert item.published_at is None
    assert item.revised_at is None
    assert item.available_at == item.received_at == source.received_at
    assert item.timing_basis == "received"
    assert item.raw_hash == source.digest
    assert not item.known_at(source.received_at - timedelta(microseconds=1))
    assert item.known_at(source.received_at)
    with pytest.raises(ValueError, match="preliminary"):
        parse_label(target().revalidated(target_date=date(2026, 10, 30)), receipt("2026-10-30"))


@pytest.mark.parametrize(
    "mutation",
    [
        "preliminary",
        "isOfficial",
        "wrong_station",
        "wrong_report_station",
        "timezone",
        "date",
        "response_date",
        "missing",
        "duplicate",
        "float",
        "bool",
        "null",
        "clock_naive",
        "future",
        "wrong_source",
        "protected",
    ],
)
def test_controlled_malformed_or_incompatible_labels_fail_closed(mutation: str) -> None:
    body, chosen = response_body(), target()
    row = philly(body)
    if mutation == "preliminary":
        row["status"] = "preliminary"
    elif mutation == "isOfficial":
        row["data"]["isOfficial"] = False
    elif mutation == "wrong_station":
        row["station"]["icao"] = "KJFK"
    elif mutation == "wrong_report_station":
        row["data"]["stationId"] = "JFK"
    elif mutation == "timezone":
        row["station"]["timezone"] = "UTC"
    elif mutation == "date":
        row["data"]["reportDate"] = "2026-10-28"
    elif mutation == "response_date":
        body["date"] = "2026-10-28"
    elif mutation == "missing":
        body["results"] = []
    elif mutation == "duplicate":
        body["results"].append(row)
    elif mutation == "float":
        row["data"]["maxTemp"] = 70.5
    elif mutation == "bool":
        row["data"]["maxTemp"] = True
    elif mutation == "null":
        row["data"]["maxTemp"] = None
    elif mutation == "clock_naive":
        row["data"]["issueTime"] = "2026-10-30T12:00:00"
    elif mutation == "future":
        row["data"]["issueTime"] = "2027-01-01T00:00:00Z"
    elif mutation == "wrong_source":
        chosen = chosen.revalidated(refusal="NWS cannot substitute for Weather Company")
    elif mutation == "protected":
        chosen = chosen.revalidated(refusal="protected label excluded")
    with pytest.raises(
        ValueError, match=r"preliminary|station|date|Fahrenheit|clock|timezone|substitute|protected"
    ):
        parse_label(chosen, receipt(body=body))


def test_late_and_corrected_labels_never_retime_old_versions() -> None:
    first = parse_label(target(), receipt())
    assert first.received_at is not None
    body = response_body()
    row = philly(body)
    row["status"] = "revised"
    row["data"]["maxTemp"] = 71
    row["data"]["issueTime"] = "2026-10-30T12:00:00Z"
    row["revisedAt"] = "2026-10-31T09:00:00Z"
    later = receipt(body=body).revalidated(received_at=first.received_at + timedelta(hours=1))
    corrected = parse_label(target(), later)
    assert corrected.value == 71
    assert first.value == 70
    assert corrected.revision_id != first.revision_id
    assert corrected.available_at == later.received_at
    assert corrected.published_at == datetime(2026, 10, 30, 12, tzinfo=UTC)
    assert not corrected.known_at(first.received_at)
    assert corrected.revised_at == datetime(2026, 10, 31, 9, tzinfo=UTC)
    with pytest.raises(ValueError, match="clock incompatible"):
        parse_label(
            target(), receipt().revalidated(received_at=datetime(2026, 10, 29, 23, tzinfo=UTC))
        )


@pytest.fixture
def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], LabelService]:
    # Controlled replay clock, never a new authentic receipt claim.
    monkeypatch.setattr(
        "entropytrade.weather.label_service.utc_now", lambda: datetime(2026, 10, 31, 12, tzinfo=UTC)
    )
    workspace = tmp_path / "workspace"
    seed_retained(workspace)
    captures, _, _ = Jobs(workspace).weather_inputs(None, None)
    snapshot = build_snapshot(workspace / "runs/weather-datasets", captures)
    return workspace, snapshot, LabelService(workspace)


def acquire(
    service: LabelService, snapshot: dict[str, Any], *, error: bool = False
) -> dict[str, Any]:
    request = service.create({"id": str(uuid4()), "dataset_id": snapshot["dataset_id"][7:]})

    def source(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.host == "weather.com"
        assert "authorization" not in req.headers
        assert "cookie" not in req.headers
        if error:
            return httpx.Response(503, text="source unavailable")
        day = req.url.params["date"]
        return httpx.Response(
            200, content=receipt(day).body(), headers={"content-type": "application/json"}
        )

    asyncio.run(service.acquire(request, httpx.MockTransport(source)))
    return service.get(request["id"])


def test_restart_idempotency_receipt_replay_and_immutable_dataset(
    setup: tuple[Path, dict[str, Any], LabelService],
) -> None:
    workspace, original, service = setup
    request = acquire(service, original)
    assert request["status"] == "completed"
    assert request["result"]["verified_events"] == 2
    assert request["result"]["refused_events"] == 2
    assert (
        service.create({"id": request["id"], "dataset_id": original["dataset_id"][7:]}) == request
    )
    # A new service is an offline restart. It must not fetch or rewrite complete receipts.
    reopened = LabelService(workspace)
    reopened.recover()
    assert reopened.get(request["id"]) == request
    captures = sorted(SOURCE.glob("*/*/public"))
    updated = build_snapshot(
        workspace / "runs/weather-datasets", captures, scalar_batches=batches(workspace)
    )
    root = workspace / "runs/weather-datasets" / updated["dataset_id"][7:]
    assert updated["readiness"]["scalar_label_events"] == 2
    assert updated["readiness"]["status"] == "insufficient_data"
    assert updated["identity"]["temporal_boundaries"] == original["identity"]["temporal_boundaries"]
    rows = pq.read_table(root / updated["features"] / "features.parquet").to_pylist()
    events = tuple({r["event_id"] for r in rows})
    assert not _examples(rows, events, datetime(2026, 10, 30, tzinfo=UTC))
    assert len(_examples(rows, events, datetime(2026, 11, 1, tzinfo=UTC))) == 2
    assert updated == build_snapshot(
        workspace / "runs/weather-datasets", captures, scalar_batches=batches(workspace)
    )
    assert (
        load_snapshot(workspace / "runs/weather-datasets" / original["dataset_id"][7:]) == original
    )
    batch_path = batches(workspace)[0]
    assert load_batch(batch_path).summary() == request["result"]
    batch_path.write_text(batch_path.read_text().replace('"max_length"', '"tampered"') + " ")
    # Whitespace is not scientific content; a value mutation must change the version.
    value = json.loads(batch_path.read_text())
    value["source_dataset"] = "sha256:" + "0" * 64
    batch_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="identity"):
        reopened.get(request["id"])


def test_interrupted_partial_failure_and_holdout_refusal(
    setup: tuple[Path, dict[str, Any], LabelService],
) -> None:
    workspace, original, service = setup
    pending = service.create({"id": str(uuid4()), "dataset_id": original["dataset_id"][7:]})
    pending["status"] = "running"
    pending["receipts"] = [receipt().model_dump(mode="json")]
    service.save(pending)
    service.recover()
    interrupted = service.get(pending["id"])
    assert interrupted["status"] == "interrupted"
    assert interrupted["receipts"] == pending["receipts"]
    assert interrupted["result"]["verified_events"] == 2
    failed = acquire(service, original, error=True)
    assert failed["result"]["verified_events"] == 0
    assert all("HTTP 503" in r["refusal"] for r in failed["result"]["records"])
    captures = sorted(SOURCE.glob("*/*/public"))
    event = "KXHIGHPHIL-26OCT29"
    protected = build_snapshot(
        workspace / "runs/weather-datasets",
        captures,
        scalar_batches=batches(workspace),
        protected_events=frozenset({event}),
    )
    assert protected["readiness"]["scalar_label_events"] == 1
    # Global protection applies even when acquisition selects an older snapshot.
    new = service.create({"id": str(uuid4()), "dataset_id": original["dataset_id"][7:]})
    t = next(t for t in new["selection"]["targets"] if t["event_id"] == event)
    assert "protected" in t["refusal"]
    root = workspace / "runs/weather-datasets" / protected["dataset_id"][7:]
    assert any(t.refusal for t in targets(root))


def test_request_scope_immutable_ids_and_untrusted_url_denied(
    setup: tuple[Path, dict[str, Any], LabelService],
) -> None:
    _, original, service = setup
    with pytest.raises(ValueError, match="only"):
        service.create(
            {
                "id": str(uuid4()),
                "dataset_id": original["dataset_id"][7:],
                "url": "https://attacker.invalid",
            }
        )
    with pytest.raises(ValueError, match="destination"):
        receipt().revalidated(url="https://attacker.invalid")
    with pytest.raises(ValueError, match="destination"):
        receipt().revalidated(url=URL + "2026-10-29&apiKey=anything")
    value = service.create({"id": str(uuid4()), "dataset_id": original["dataset_id"][7:]})
    with pytest.raises(ValueError, match="another dataset"):
        service.create({"id": value["id"], "dataset_id": "0" * 64})
    value["selection"]["dataset_id"] = "0" * 64
    service.save(value)
    with pytest.raises(ValueError, match="identity"):
        service.get(value["id"])


@pytest.mark.parametrize("mode", ["redirect", "oversize", "unavailable"])
def test_network_failure_redirect_and_byte_budget_are_durable_refusals(
    setup: tuple[Path, dict[str, Any], LabelService], mode: str
) -> None:
    _, snapshot, service = setup
    request = service.create({"id": str(uuid4()), "dataset_id": snapshot["dataset_id"][7:]})
    calls: list[str] = []

    def source(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if mode == "unavailable":
            raise httpx.ConnectError("CONTROLLED unavailable", request=req)
        if mode == "redirect":
            return httpx.Response(302, headers={"location": "https://attacker.invalid"})
        return httpx.Response(200, content=b"x" * 2_000_001)

    asyncio.run(service.acquire(request, httpx.MockTransport(source)))
    result = service.get(request["id"])
    assert result["status"] == "completed"
    assert result["result"]["verified_events"] == 0
    assert result["result"]["refused_events"] == 4
    assert len(calls) == 2
    assert all(r["url"].startswith(URL) for r in result["receipts"])
    assert all(r["refusal"] for r in result["result"]["records"])
    if mode == "oversize":
        assert len(base64.b64decode(result["receipts"][0]["body_base64"])) == 2_000_000


def test_shutdown_cancels_active_network_and_preserves_prior_receipts(
    setup: tuple[Path, dict[str, Any], LabelService], monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    _, snapshot, service = setup
    request = service.create({"id": str(uuid4()), "dataset_id": snapshot["dataset_id"][7:]})
    arrived = threading.Event()
    original = service.acquire

    async def stalled(req: httpx.Request) -> httpx.Response:
        arrived.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def controlled(saved: dict[str, Any]) -> None:
        await original(saved, httpx.MockTransport(stalled))

    monkeypatch.setattr(service, "acquire", controlled)
    service.thread.start()
    try:
        assert arrived.wait(10)
    finally:
        service.close()
    assert not service.thread.is_alive()
    interrupted = service.get(request["id"])
    assert interrupted["status"] == "interrupted"
    assert interrupted["result"]["verified_events"] == 0
    assert interrupted["result"]["refused_events"] == 4


def test_corrected_batch_uses_latest_known_revision_and_replays_original_bytes(
    setup: tuple[Path, dict[str, Any], LabelService],
) -> None:
    workspace, original, service = setup
    first = acquire(service, original)
    first_time = datetime.fromisoformat(first["receipts"][0]["received_at"])
    corrected_body = response_body()
    philly(corrected_body)["status"] = "revised"
    philly(corrected_body)["data"]["maxTemp"] = 71
    corrected = receipt(body=corrected_body).revalidated(
        received_at=first_time + timedelta(hours=1)
    )
    later = service.create({"id": str(uuid4()), "dataset_id": original["dataset_id"][7:]})
    later["receipts"] = [
        corrected.model_dump(mode="json"),
        receipt("2026-10-30").model_dump(mode="json"),
    ]
    service.finish(later, "completed", "CONTROLLED corrected report replay")
    updated = build_snapshot(
        workspace / "runs/weather-datasets",
        sorted(SOURCE.glob("*/*/public")),
        scalar_batches=batches(workspace),
    )
    root = workspace / "runs/weather-datasets" / updated["dataset_id"][7:]
    rows = pq.read_table(root / updated["features"] / "features.parquet").to_pylist()
    event = ("KXHIGHPHIL-26OCT29",)
    early = _examples(rows, event, first_time)
    late = _examples(rows, event, first_time + timedelta(hours=2))
    assert early[0].target_f == 70
    assert late[0].target_f == 71
    assert load_snapshot(root) == updated
    # Rehashing the outer inventory cannot conceal a semantic label/audit mutation.
    manifest = json.loads((root / "dataset/manifest.json").read_text())
    manifest["retained_label_audit"][0]["verified_events"] += 1
    (root / "dataset/manifest.json").write_text(json.dumps(manifest))
    outer = json.loads((root / "snapshot.json").read_text())
    from entropytrade.data.sources import file_hash

    outer["checksums"]["dataset/manifest.json"] = file_hash(root / "dataset/manifest.json")
    (root / "snapshot.json").write_text(json.dumps(outer))
    with pytest.raises(ValueError, match="replay audit"):
        load_snapshot(root)


def test_wrong_rule_batch_is_refused_and_symlink_store_is_denied(
    setup: tuple[Path, dict[str, Any], LabelService], tmp_path: Path
) -> None:
    workspace, snapshot, service = setup
    acquired = acquire(service, snapshot)
    batch = load_batch(service.batch_path(acquired["batch_version"]))
    changed = batch.revalidated(
        targets=tuple(t.revalidated(rules_hashes=("wrong-source-rules",)) for t in batch.targets)
    )
    path = service.batch_path(changed.version)
    path.write_text(changed.model_dump_json())
    result = build_snapshot(
        workspace / "runs/weather-datasets",
        sorted(SOURCE.glob("*/*/public")),
        scalar_batches=[path],
    )
    assert result["readiness"]["scalar_label_events"] == 0
    assert all(
        "differ" in r["refusal"] for r in result["readiness"]["label_acquisition"][0]["records"]
    )
    other = tmp_path / "other"
    other.mkdir()
    unsafe = LabelService(other)
    unsafe.root.mkdir(parents=True)
    (unsafe.root / "requests").symlink_to(service.root / "requests", target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        unsafe.catalog()
