"""Immutable server-managed fee evidence, portable to offline decisions/experiments.

The operator reviews official documents locally. Neither a browser, a series payload nor
an LLM can certify a schedule. Receipt/review clocks bound availability; review never
backdates a newly interpreted document. Controlled versions only apply to synthetic data.
"""

import base64
import binascii
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from entropytrade.domain.base import DomainModel
from entropytrade.domain.ids import ContentHash
from entropytrade.domain.time import UtcDatetime
from entropytrade.execution.fee_policy import FeePolicy
from entropytrade.features.registry import scientific_hash

MAX_SOURCE_BYTES = 8 * 1024 * 1024
OFFICIAL_SCHEDULE_URL = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"
OFFICIAL_HOSTS = frozenset(
    {
        "kalshi.com",
        "help.kalshi.com",
        "docs.kalshi.com",
        "api.elections.kalshi.com",
        "kalshi-public-docs.s3.amazonaws.com",
    }
)


class ManualImport(DomainModel):
    """Operator attestation for official bytes downloaded by a human, not by this system.

    Automated clients receive HTTP 429 for the official schedule (issue #6). An operator may
    download it in a browser and import the exact bytes. The system never observed that
    download: ``operator_downloaded_at`` is informational only. Availability is the local
    import clock (the receipt's ``received_at``), so an import can never backdate evidence.
    """

    operator_downloaded_at: UtcDatetime
    original_filename: str = Field(min_length=1, max_length=255)
    note: str = Field(min_length=1, max_length=2000)


class FeeReceipt(DomainModel):
    url: str
    received_at: UtcDatetime
    status: int = Field(ge=100, le=599)
    media_type: str
    body_base64: str = Field(max_length=12 * 1024 * 1024)
    sha256: ContentHash
    # Absent for automated captures. Omitted from serialization when absent so every
    # previously retained receipt and fee version keeps its exact content hash.
    manual_import: ManualImport | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_import(self, handler: SerializerFunctionWrapHandler) -> Any:
        data = handler(self)
        if self.manual_import is None and isinstance(data, dict):
            data.pop("manual_import", None)
        return data

    def body(self) -> bytes:
        try:
            raw = base64.b64decode(self.body_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid fee source bytes") from exc
        if len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("fee source exceeds byte budget")
        return raw

    @model_validator(mode="after")
    def checksum(self) -> "FeeReceipt":
        from hashlib import sha256

        body = self.body()
        if "sha256:" + sha256(body).hexdigest() != self.sha256:
            raise ValueError("fee source checksum mismatch")
        if self.manual_import is not None and (
            self.url != OFFICIAL_SCHEDULE_URL
            or self.status != 200
            or self.media_type != "application/pdf"
            or not body.startswith(b"%PDF-")
            or self.manual_import.operator_downloaded_at > self.received_at
        ):
            raise ValueError(
                "manual imports are limited to official schedule PDF bytes "
                "downloaded before their import clock"
            )
        return self


class FeeCitation(DomainModel):
    source_hash: ContentHash
    locator: str = Field(min_length=1, max_length=1000)
    passage: str = Field(min_length=1, max_length=12000)
    supports: tuple[Literal["coefficient", "rounding", "series", "multiplier", "interval"], ...]


class FeeVersion(DomainModel):
    schema_version: Literal["fee-evidence-v1"] = "fee-evidence-v1"
    evidence_kind: Literal["authentic", "controlled"]
    series: tuple[str, ...] = ()
    sources: tuple[FeeReceipt, ...] = Field(min_length=1, max_length=8)
    policy: FeePolicy | None = None
    reviewed_at: UtcDatetime | None = None
    review: str = Field(default="", max_length=4000)
    citations: tuple[FeeCitation, ...] = ()
    refusal: str = Field(
        default="Unreviewed official source; no certified schedule", max_length=4000
    )
    rounding: Literal["cent_ceiling_per_fill", "unsupported"] = "unsupported"

    @property
    def version(self) -> str:
        return scientific_hash(self.model_dump(mode="json"))

    @property
    def available_at(self) -> datetime:
        return max(
            [s.received_at for s in self.sources] + ([self.reviewed_at] if self.reviewed_at else [])
        )

    @model_validator(mode="after")
    def validate_review(self) -> "FeeVersion":
        if len(set(self.series)) != len(self.series) or any(
            re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*", s) is None for s in self.series
        ):
            raise ValueError("fee applicability needs exact unique series identifiers")
        if self.evidence_kind == "authentic":
            for receipt in self.sources:
                url = urlsplit(receipt.url)
                if (
                    url.scheme != "https"
                    or url.hostname not in OFFICIAL_HOSTS
                    or url.username
                    or url.password
                    or url.port not in {None, 443}
                ):
                    raise ValueError("authentic fee sources require official HTTPS origins")
        if self.policy is not None:
            policy = self.policy
            if not self.reviewed_at or not self.review or not self.series or self.refusal:
                raise ValueError(
                    "fee certification needs explicit server review and series applicability"
                )
            if any(s.status != 200 for s in self.sources):
                raise ValueError("failed source receipts cannot certify fees")
            if self.reviewed_at < max(s.received_at for s in self.sources):
                raise ValueError("fee review precedes source receipt")
            if self.rounding != "cent_ceiling_per_fill":
                raise ValueError("fee engine cannot certify this rounding rule")
            if not policy.certified or policy.available_at != self.available_at:
                raise ValueError(
                    "certified policy availability must include receipt and review clocks"
                )
            if not policy.evidence_hash or policy.evidence_hash != scientific_hash(
                [s.model_dump(mode="json") for s in self.sources]
            ):
                raise ValueError("policy must bind exact source receipts")
            if policy.effective_to is None or policy.effective_to <= policy.effective_from:
                raise ValueError("reviewed fees need a bounded effective interval")
            hashes = {s.sha256 for s in self.sources}
            if any(c.source_hash not in hashes for c in self.citations) or {
                x for c in self.citations for x in c.supports
            } != {"coefficient", "rounding", "series", "multiplier", "interval"}:
                raise ValueError("review must cite source passages for every fee assumption")
            # Series API responses are useful corroboration but never certification.
            if not any("/series/" not in urlsplit(s.url).path for s in self.sources):
                raise ValueError("series metadata alone cannot certify a fee schedule")
            if self.evidence_kind == "authentic" and not any(
                s.url == OFFICIAL_SCHEDULE_URL and s.body().startswith(b"%PDF-")
                for s in self.sources
            ):
                raise ValueError("fee certification requires the retained official schedule PDF")
        return self

    def summary(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "evidence_kind": self.evidence_kind,
            "series": self.series,
            "available_at": self.available_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review": self.review,
            "citations": [c.model_dump(mode="json") for c in self.citations],
            "rounding": self.rounding,
            "refusal": self.refusal,
            "policy": self.policy.model_dump(mode="json") if self.policy else None,
            "sources": [s.model_dump(mode="json", exclude={"body_base64"}) for s in self.sources],
        }


class FeeEvidenceStore:
    def __init__(self, workspace: Path) -> None:
        # Included in the existing bounded workspace backup/restore protocol.
        self.root = workspace / "runs" / "fee-evidence"
        if any(path.is_symlink() for path in (workspace, self.root.parent, self.root)):
            raise ValueError("fee evidence directories must not be symlinks")

    def put(self, version: FeeVersion) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        name = version.version.removeprefix("sha256:")
        destination = self.root / (name + ".json")
        if destination.exists():
            if self.get(version.version) != version:
                raise ValueError("immutable fee version collision")
            return version.version
        staging = self.root / (".pending-" + str(uuid4()))
        try:
            with staging.open("xb") as stream:
                stream.write(version.model_dump_json(indent=2).encode())
                stream.flush()
                os.fsync(stream.fileno())
            # Publish without ever replacing a prior content-addressed version.
            try:
                os.link(staging, destination)
            except FileExistsError:
                if self.get(version.version) != version:
                    raise ValueError("immutable fee version collision") from None
        finally:
            staging.unlink(missing_ok=True)
        return version.version

    def get(self, identifier: str) -> FeeVersion:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", identifier):
            raise ValueError("invalid fee version identifier")
        path = self.root / (identifier.removeprefix("sha256:") + ".json")
        if path.is_symlink() or path.stat().st_size > 96 * 1024 * 1024:
            raise ValueError("unsafe fee version file")
        version = FeeVersion.model_validate_json(path.read_bytes())
        if version.version != identifier:
            raise ValueError("fee version checksum mismatch")
        return version

    def snapshot(self) -> tuple[FeeVersion, ...]:
        return tuple(self.get("sha256:" + p.stem) for p in sorted(self.root.glob("*.json")))


def select_fee(
    versions: tuple[FeeVersion, ...], *, series: str, when: datetime, data_kind: str
) -> tuple[FeePolicy | None, dict[str, Any]]:
    applicable = [v for v in versions if series in v.series]
    known = [v for v in applicable if v.available_at <= when]
    eligible = [
        v
        for v in known
        if v.policy is not None
        and (
            v.evidence_kind == "authentic"
            if data_kind == "real"
            else v.evidence_kind == "controlled"
        )
        and v.policy.effective_to is not None
        and v.policy.effective_from <= when < v.policy.effective_to
    ]
    reason = "missing_fee_evidence"
    if applicable and not known:
        reason = "late_fee_evidence"
    elif versions and not applicable:
        reason = "inapplicable_fee_evidence"
    elif known:
        reason = "uncertified_or_outside_fee_interval"
    if len(eligible) > 1:
        reason = "conflicting_fee_evidence"
    version = eligible[0] if len(eligible) == 1 else None
    audit = {
        "status": "applicable" if version else "refused",
        "reason": None if version else reason,
        "series": series,
        "decision_time": when.isoformat(),
        "version": version.version if version else None,
        "candidates": [v.version for v in applicable],
        "provenance": version.summary() if version else None,
    }
    return (
        version.policy.revalidated(version=version.version) if version and version.policy else None
    ), audit
