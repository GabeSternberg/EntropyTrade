"""Bounded read-only acquisition jobs with durable receipts and explicit restart recovery."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import threading
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx

from entropytrade.api.jobs import identifier
from entropytrade.domain.time import utc_now
from entropytrade.features.registry import scientific_hash
from entropytrade.weather.label_partitions import (
    LabelPartitions,
    PartitionBusyError,
    PartitionedBatches,
)
from entropytrade.weather.labels import (
    MAX_BODY,
    MAX_DATES,
    URL,
    LabelBatch,
    LabelReceipt,
    LabelTarget,
    load_batch,
    targets,
)

if TYPE_CHECKING:
    from pathlib import Path


def atomic(path: Path, value: object) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("weather label paths cannot traverse symlinks")
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(".pending-" + str(uuid4()))
    try:
        with pending.open("x") as stream:
            stream.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


class LabelService:
    def __init__(self, workspace: Path, snapshot_lock: threading.Lock | None = None) -> None:
        self.workspace = workspace
        self.root = workspace / "runs/weather-labels"
        self.partitions = LabelPartitions(self.root)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.active_loop: asyncio.AbstractEventLoop | None = None
        self.active_task: asyncio.Task[None] | None = None
        self.active_request: str | None = None
        self.cancel_requested = False
        self.snapshot_lock = snapshot_lock or threading.Lock()
        self.thread = threading.Thread(target=self.loop, name="weather-labels", daemon=True)
        if any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ValueError("weather label paths cannot traverse symlinks")
        from entropytrade.weather.label_schedule import LabelScheduler

        self.scheduler = LabelScheduler(self)

    def selection(self, dataset_id: str) -> dict[str, Any]:
        from entropytrade.weather.history import load_snapshot, snapshot_id

        dataset_id = snapshot_id(dataset_id)
        datasets = self.workspace / "runs/weather-datasets"
        protected = frozenset(
            e
            for parent in (datasets, datasets / ".batches")
            for p in parent.glob("[0-9a-f]" * 64)
            for e in load_snapshot(p)["identity"]["protected_events"]
        )
        return {
            "dataset_id": dataset_id,
            "protected_events": sorted(protected),
            "targets": [
                t.model_dump(mode="json") for t in targets(datasets / dataset_id, protected)
            ],
        }

    def catalog(self, partition_id: str | None = None) -> list[dict[str, Any]]:
        """Full offline catalog, or one bounded browser-selected partition."""
        with self.lock:
            roots = (
                [self.partitions.selected(partition_id)]
                if partition_id is not None
                else self.partitions.roots()
            )
            return [
                self.get(p.stem) for root in roots for p in self.partitions.files(root, "requests")
            ]

    def active_catalog(self) -> list[dict[str, Any]]:
        with self.lock:
            root = self.partitions.roots()[-1]
            if self.partitions.manifest(root):
                return []  # Crash after seal, before creating the successor: nothing to recover.
            return [self.get(p.stem) for p in self.partitions.files(root, "requests")]

    def get(self, request_id: str) -> dict[str, Any]:
        path = self.partitions.locate("requests", identifier(request_id))
        if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > 24_000_000:
            raise ValueError("unsafe weather acquisition request")
        value: dict[str, Any] = json.loads(path.read_text())
        if (
            value["id"] != request_id
            or scientific_hash(value["selection"]) != value["selection_hash"]
        ):
            raise ValueError("weather acquisition request identity mismatch")
        if value["status"] not in {"queued", "running", "completed", "failed", "interrupted"}:
            raise ValueError("invalid weather acquisition status")
        finished = value["status"] in {"completed", "failed", "interrupted"}
        if finished != bool(value["batch_version"]) or finished != bool(value["finished_at"]):
            raise ValueError("weather acquisition completion evidence missing")
        if value["batch_version"]:
            try:
                batch = load_batch(self.batch_path(value["batch_version"]))
            except FileNotFoundError as exc:
                # Only a missing request itself means an unpublished durable plan.
                # Missing terminal dependencies must never mint another acquisition.
                raise ValueError("weather acquisition batch evidence missing") from exc
            if batch != self.batch(value):
                raise ValueError("weather acquisition batch/request mismatch")
            value["result"] = batch.summary()
        return value

    def batch_path(self, version: str) -> Path:
        from entropytrade.weather.history import snapshot_id

        name = snapshot_id(version.removeprefix("sha256:"))
        try:
            return self.partitions.locate("batches", name)
        except FileNotFoundError:
            return self.partitions.writable() / "batches" / (name + ".json")

    def batch(self, request: dict[str, Any]) -> LabelBatch:
        selection = request["selection"]
        return LabelBatch(
            source_dataset="sha256:" + selection["dataset_id"],
            protected_events=tuple(selection["protected_events"]),
            targets=tuple(LabelTarget.model_validate(t) for t in selection["targets"]),
            receipts=tuple(LabelReceipt.model_validate(r) for r in request["receipts"]),
        )

    def create(self, value: object) -> dict[str, Any]:
        from entropytrade.weather.history import snapshot_id

        if not isinstance(value, dict) or set(value) != {"id", "dataset_id"}:
            raise ValueError("provide acquisition id and retained dataset_id only")
        if not all(isinstance(v, str) for v in value.values()):
            raise ValueError("acquisition id and dataset_id must be strings")
        request_id, dataset_id = identifier(value["id"]), snapshot_id(value["dataset_id"])
        with self.lock:
            try:
                previous = self.get(request_id)
            except FileNotFoundError:
                previous = None
            if previous is not None:
                if previous["selection"]["dataset_id"] != dataset_id:
                    raise ValueError("acquisition id already belongs to another dataset")
                return previous
            selection = self.selection(dataset_id)
            if (
                len({t["target_date"] for t in selection["targets"] if not t["refusal"]})
                > MAX_DATES
            ):
                raise ValueError("acquisition exceeds eight dates; opt in to bounded scheduling")
            return self.enqueue(request_id, selection)

    def enqueue(self, request_id: str, selection: dict[str, Any]) -> dict[str, Any]:
        """Internal bounded request creation; HTTP callers cannot supply selections or URLs."""
        with self.lock:
            identifier(request_id)
            try:
                previous = self.get(request_id)
            except FileNotFoundError:
                previous = None
            if previous is not None:
                if previous["selection"] != selection:
                    raise ValueError("acquisition id already belongs to another selection")
                return previous
            rows = self.active_catalog()
            if sum(r["status"] in {"queued", "running"} for r in rows) >= 8:
                raise PartitionBusyError("weather acquisition queue is full")
            if (
                len({t["target_date"] for t in selection["targets"] if not t["refusal"]})
                > MAX_DATES
            ):
                raise ValueError("weather acquisition exceeds eight dates")
            request: dict[str, Any] = {
                "id": request_id,
                "selection": selection,
                "selection_hash": scientific_hash(selection),
                "status": "queued",
                "created_at": utc_now().isoformat(),
                "finished_at": None,
                "receipts": [],
                "batch_version": None,
                "detail": "Waiting for read-only acquisition",
            }
            root = self.partitions.prepare(self)
            atomic(root / "requests" / (request_id + ".json"), request)
            return request

    def save(self, request: dict[str, Any]) -> None:
        with self.lock:
            path = self.partitions.locate("requests", identifier(request["id"]))
            if path.parent.parent != self.partitions.writable():
                raise ValueError("sealed label request cannot be changed")
            atomic(path, request)

    def finish(self, request: dict[str, Any], status: str, detail: str) -> None:
        with self.lock:
            if self.get(request["id"])["status"] in {"completed", "failed", "interrupted"}:
                return  # A stale worker must never replace terminal evidence.
            batch = self.batch(request)
            destination = self.batch_path(batch.version)
            if destination.exists():
                if load_batch(destination) != batch:
                    raise ValueError("immutable weather batch collision")
            else:
                atomic(destination, batch.model_dump(mode="json"))
            request.update(
                status=status,
                detail=detail,
                finished_at=utc_now().isoformat(),
                batch_version=batch.version,
            )
            self.save(request)

    def recover(self) -> None:
        self.partitions.validate()
        for request in self.active_catalog():
            if request["status"] in {"queued", "running"}:
                self.finish(
                    request,
                    "interrupted",
                    "Interrupted by restart; receipts retained. Start a new acquisition to retry.",
                )

    async def acquire(
        self, request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        with self.lock:
            if (
                self.active_request != request["id"]
                or self.active_task is not asyncio.current_task()
            ):
                raise ValueError("weather acquisition requires active request ownership")
            if self.get(request["id"])["status"] != "running":
                return
            if self.cancel_requested or self.stop.is_set():
                raise asyncio.CancelledError
        days = sorted(
            {t["target_date"] for t in request["selection"]["targets"] if not t["refusal"]}
        )
        async with httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=15,
            headers={
                "User-Agent": "EntropyTrade read-only research "
                "(github.com/GabeSternberg/EntropyTrade)",
                "Accept": "application/json",
            },
        ) as client:
            for day in days:
                if self.stop.is_set():
                    self.finish(request, "interrupted", "Stopped; authentic receipts retained")
                    return
                body, error, status, headers = bytearray(), "", None, {}
                try:
                    client.cookies.clear()
                    async with client.stream("GET", URL + day) as response:
                        status = response.status_code
                        headers = {
                            k: v
                            for k, v in response.headers.items()
                            if k in {"date", "last-modified", "etag", "content-type"}
                        }
                        async for chunk in response.aiter_bytes():
                            remaining = MAX_BODY - len(body)
                            body.extend(chunk[:remaining])
                            if len(chunk) > remaining:
                                error = (
                                    "source response exceeds 2 MB; retained prefix is not a label"
                                )
                                break
                except httpx.HTTPError as exc:
                    error = type(exc).__name__ + ": public settlement source unavailable"
                receipt = LabelReceipt(
                    url=URL + day,
                    received_at=utc_now(),
                    status=status,
                    headers=headers,
                    body_base64=base64.b64encode(body).decode(),
                    error=error,
                )
                request["receipts"].append(receipt.model_dump(mode="json"))
                request["detail"] = (
                    f"Retained {len(request['receipts'])}/{len(days)} source responses"
                )
                self.save(request)
        self.finish(
            request,
            "completed",
            "Acquisition finished; inspect verified labels and explicit source refusals",
        )

    def loop(self) -> None:
        while not self.stop.is_set():
            request = None
            try:
                self.scheduler.tick()
                request = next((r for r in self.active_catalog() if r["status"] == "queued"), None)
                if request:
                    asyncio.run(self.bounded(request))
            except (ValueError, OSError, KeyError, TypeError) as exc:
                if request:
                    self.finish(
                        # bounded() owns a reloaded copy. Its receipts may already be
                        # durable even when acquisition or a later save raises.
                        self.get(request["id"]),
                        "failed",
                        type(exc).__name__
                        + ": acquisition failed; retained receipts may be incomplete",
                    )
                else:
                    return  # Corrupt store fails closed; no further network requests.
            self.stop.wait(0.2)

    async def bounded(
        self, request: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        with self.lock:
            # catalog() is only a hint: pause/recovery may have finished that copy.
            request = self.get(request["id"])
            if request["status"] != "queued" or self.stop.is_set() or self.active_task:
                return
            request.update(status="running", detail="Fetching official daily climate reports")
            self.save(request)
            self.active_loop = asyncio.get_running_loop()
            self.active_task = asyncio.current_task()
            self.active_request = request["id"]
            self.cancel_requested = False
        try:
            async with asyncio.timeout(120):
                await self.acquire(request, transport)
        except asyncio.CancelledError:
            self.finish(
                request, "interrupted", "Stopped during acquisition; prior receipts retained"
            )
        except TimeoutError:
            self.finish(
                request, "failed", "120 second acquisition deadline exceeded; receipts retained"
            )

        finally:
            with self.lock:
                self.active_loop = None
                self.active_task = None
                self.active_request = None
                self.cancel_requested = False

    def cancel(self, request_id: str) -> None:
        with self.lock:
            request = self.get(request_id)
            if request["status"] == "queued":
                self.finish(request, "interrupted", "Schedule paused before acquisition")
            elif (
                request["status"] == "running"
                and self.active_request == request_id
                and self.active_loop
                and self.active_task
            ):
                # Cancellation callbacks cannot run until the loop yields. Record intent
                # now so acquisition startup also sees a pause in this interval.
                self.cancel_requested = True
                self.active_loop.call_soon_threadsafe(self.active_task.cancel)

    def close(self) -> None:
        self.stop.set()
        with self.lock:
            if self.active_loop and self.active_task:
                self.cancel_requested = True
                self.active_loop.call_soon_threadsafe(self.active_task.cancel)
        if self.thread.is_alive():
            self.thread.join(timeout=20)
            if self.thread.is_alive():
                raise RuntimeError("weather acquisition did not stop; workspace lease retained")


def batches(workspace: Path) -> PartitionedBatches:
    return PartitionedBatches(LabelPartitions(workspace / "runs/weather-labels"))
