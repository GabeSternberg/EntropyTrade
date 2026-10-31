"""Append-only label partitions. Sealing publishes hashes without moving original evidence.

The legacy flat store is partition 00000000. A seal is the commit record; an interrupted
rollover needs no repair or new request identity. Only the final unsealed partition is writable.
"""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from entropytrade.api.jobs import identifier
from entropytrade.data.sources import file_hash
from entropytrade.domain.time import utc_now
from entropytrade.features.registry import scientific_hash

if TYPE_CHECKING:
    from entropytrade.weather.label_service import LabelService

SIZE = 128
MAX_BATCHES = 256  # Includes an orphan batch from an interrupted terminal-request publication.
SCHEMA = "weather-label-partition-v1"
TERMINAL = {"completed", "failed", "interrupted"}


def safe(path: Path) -> Path:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("label partition paths cannot traverse symlinks")
    return path


class PartitionBusyError(ValueError):
    """Temporary backpressure; retain the durable request plan and retry after draining."""


class LabelPartitions:
    def __init__(self, root: Path) -> None:
        self.root = safe(root)
        self._manifests: dict[Path, tuple[tuple[int, ...], dict[str, Any]]] = {}

    def roots(self) -> list[Path]:
        parent = safe(self.root / "partitions")
        children = sorted(parent.iterdir()) if parent.exists() else []
        if any(not re.fullmatch(r"[0-9]{8}", p.name) or not safe(p).is_dir() for p in children):
            raise ValueError("invalid label partition directory")
        if [p.name for p in children] != [f"{n:08d}" for n in range(1, len(children) + 1)]:
            raise ValueError("noncontiguous label partitions")
        roots = [self.root, *children]
        previous = None
        for n, root in enumerate(roots):
            manifest = self.manifest(root)
            if manifest:
                if manifest["partition_id"] != f"{n:08d}" or manifest["previous"] != previous:
                    raise ValueError("label partition chain mismatch")
                previous = manifest["version"]
            elif n != len(roots) - 1:
                raise ValueError("unsealed earlier label partition")
        return roots

    @staticmethod
    def files(root: Path, directory: str) -> list[Path]:
        parent = safe(root / directory)
        paths = sorted(parent.iterdir()) if parent.exists() else []
        # Atomic-write remnants are never published evidence.
        paths = [p for p in paths if not p.name.startswith(".pending-")]
        for p in paths:
            safe(p)
            if p.suffix != ".json" or not p.is_file():
                raise ValueError("invalid label partition member")
        limit = SIZE if directory == "requests" else MAX_BATCHES
        if len(paths) > limit:
            raise ValueError("label partition member budget exceeded")
        return paths

    def manifest(self, root: Path) -> dict[str, Any] | None:
        path = safe(root / "partition.json")
        if not path.exists():
            return None
        if path.stat().st_size > 256_000:
            raise ValueError("label partition manifest too large")
        # Cached immutable metadata avoids reopening every archived inventory for every
        # active request. File hashes are still checked on access and in full at restore.
        signature: list[int] = []
        for member in (path, root / "requests", root / "batches"):
            safe(member)
            info = member.stat() if member.exists() else None
            signature.extend(
                (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                if info
                else (0,) * 4
            )
        stamp = tuple(signature)
        cached = self._manifests.get(root)
        if cached and cached[0] == stamp:
            return cached[1]
        value: dict[str, Any] = json.loads(path.read_bytes())
        if value.get("schema") != SCHEMA or value.get("version") != scientific_hash(
            {k: v for k, v in value.items() if k != "version"}
        ):
            raise ValueError("label partition manifest digest mismatch")
        if not isinstance(value["requests"], dict) or not isinstance(value["batches"], dict):
            raise ValueError("invalid label partition inventory")
        for key in ("requests", "batches"):
            paths = LabelPartitions.files(root, key)
            if {p.stem for p in paths} != set(value[key]):
                raise ValueError("sealed label partition inventory mismatch")
            for name in value[key]:
                identifier(name) if key == "requests" else batch_id(name)
        self._manifests[root] = (stamp, value)
        return value

    def locate(self, directory: str, name: str) -> Path:
        identifier(name) if directory == "requests" else batch_id(name)
        found: list[Path] = []
        for root in self.roots():
            path = safe(root / directory / (name + ".json"))
            if path.exists():
                manifest = self.manifest(root)
                if manifest and file_hash(path) != manifest[directory].get(name):
                    raise ValueError("sealed label partition member checksum mismatch")
                found.append(path)
        if not found:
            raise FileNotFoundError(name)
        if len(found) > 1 and (directory == "requests" or len({file_hash(p) for p in found}) != 1):
            raise ValueError("duplicate label partition identity")
        return found[0]

    def writable(self) -> Path:
        root = self.roots()[-1]
        if self.manifest(root):
            raise ValueError("label partition is sealed")
        return root

    def prepare(self, service: "LabelService") -> Path:
        """Called under the service lock, after global request idempotency lookup."""
        from entropytrade.weather.label_service import atomic

        roots = self.roots()
        root = roots[-1]
        manifest = self.manifest(root)
        if not manifest and len(self.files(root, "requests")) == SIZE:
            rows = [service.get(p.stem) for p in self.files(root, "requests")]
            if any(r["status"] not in TERMINAL for r in rows):
                raise PartitionBusyError(
                    "label partition full with unfinished requests; waiting for drain"
                )
            # Validate batches, including retained crash-window orphans, before sealing.
            from entropytrade.weather.labels import load_batch

            for path in self.files(root, "batches"):
                load_batch(path)
            previous = self.manifest(roots[-2]) if len(roots) > 1 else None
            manifest = {
                "schema": SCHEMA,
                "partition_id": f"{len(roots) - 1:08d}",
                "previous": previous["version"] if previous else None,
                "sealed_at": utc_now().isoformat(),
                **{
                    key: {p.stem: file_hash(p) for p in self.files(root, key)}
                    for key in ("requests", "batches")
                },
            }
            manifest["version"] = scientific_hash(manifest)
            atomic(root / "partition.json", manifest)
        if manifest:
            root = self.root / "partitions" / f"{len(roots):08d}"
            safe(root).mkdir(parents=True, exist_ok=True)
        return root

    def catalog(self) -> list[dict[str, Any]]:
        rows = []
        for n, root in enumerate(self.roots()):
            manifest = self.manifest(root)
            rows.append(
                {
                    "partition_id": f"{n:08d}",
                    "status": "sealed" if manifest else "active",
                    "version": manifest["version"] if manifest else None,
                    "sealed_at": manifest["sealed_at"] if manifest else None,
                    "requests": len(self.files(root, "requests")),
                    "batches": len(self.files(root, "batches")),
                    "request_limit": SIZE,
                    "submission_enabled": False,
                }
            )
        return rows

    def selected(self, partition_id: str) -> Path:
        if not re.fullmatch(r"[0-9]{8}", partition_id):
            raise ValueError("invalid label partition ID")
        roots = self.roots()
        number = int(partition_id)
        if number >= len(roots):
            raise ValueError("unknown label partition")
        return roots[number]

    def validate(self) -> None:
        seen: set[str] = set()
        for root in self.roots():
            manifest = self.manifest(root)
            for key in ("requests", "batches"):
                for path in self.files(root, key):
                    if manifest and file_hash(path) != manifest[key][path.stem]:
                        raise ValueError("sealed label partition member checksum mismatch")
                    if key == "requests":
                        if path.stem in seen:
                            raise ValueError("duplicate label partition request identity")
                        seen.add(path.stem)
                        row = json.loads(path.read_bytes())
                        if manifest and row["status"] not in TERMINAL:
                            raise ValueError("sealed label partition has unfinished request")


def batch_id(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid label partition batch identity")
    return value


class PartitionedBatches(tuple[Path, ...]):
    """Verified bounded groups for streaming snapshot assembly under its existing byte cap."""

    def __new__(cls, store: LabelPartitions) -> Self:
        from entropytrade.weather.labels import load_batch

        paths: list[Path] = []
        store.validate()
        versions: set[str] = set()
        for root in store.roots():
            for path in store.files(root, "batches"):
                batch = load_batch(path)
                if batch.version not in versions:
                    paths.append(path)
                    versions.add(batch.version)
        return super().__new__(cls, sorted(paths, key=lambda p: p.stem))
