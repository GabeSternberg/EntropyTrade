"""Local fee administration. No browser certification, credentials or trading transport.

Capture official bytes now, then explicitly review source passages and all assumptions.
Review timestamps are assigned here, never imported from a review request.
"""

import argparse
import asyncio
import base64
import json
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

from entropytrade.api.workspace import workspace_lease, workspace_path
from entropytrade.domain.time import utc_now
from entropytrade.execution.fee_evidence import (
    MAX_SOURCE_BYTES,
    FeeEvidenceStore,
    FeeReceipt,
    FeeVersion,
)
from entropytrade.execution.fee_policy import FeePolicy
from entropytrade.features.registry import scientific_hash

DOCUMENTS = {
    "schedule": "https://kalshi.com/docs/kalshi-fee-schedule.pdf",
    "rounding": "https://docs.kalshi.com/getting_started/fee_rounding",
}


# Unattended capture cadence. A successful official copy is refetched at most daily; a failed
# attempt (e.g. HTTP 429/403) may be retried sooner. Every stored attempt is a new immutable
# receipt, so these bounds keep repeated scheduled runs from flooding the workspace.
SUCCESS_INTERVAL = timedelta(hours=24)
FAILURE_INTERVAL = timedelta(hours=3)


async def capture(
    document: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> FeeVersion:
    url = DOCUMENTS[document]
    async with (
        httpx.AsyncClient(
            timeout=20, trust_env=False, follow_redirects=False, transport=transport
        ) as client,
        client.stream("GET", url) as response,
    ):
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > MAX_SOURCE_BYTES:
                raise ValueError("fee source exceeds byte budget")
        receipt = FeeReceipt(
            url=url,
            received_at=utc_now(),
            status=response.status_code,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            body_base64=base64.b64encode(raw).decode(),
            sha256="sha256:" + sha256(raw).hexdigest(),
        )
    return FeeVersion(evidence_kind="authentic", sources=(receipt,))


def _attempts(store: FeeEvidenceStore, url: str) -> list[FeeReceipt]:
    """Retained unreviewed authentic receipts for one official URL, oldest first."""
    return sorted(
        (
            source
            for version in store.snapshot()
            if version.evidence_kind == "authentic" and version.policy is None
            for source in version.sources
            if source.url == url
        ),
        key=lambda source: source.received_at,
    )


def _receipt_report(receipt: FeeReceipt) -> dict[str, Any]:
    body = receipt.body()
    return {
        "received_at": receipt.received_at.isoformat(),
        "status": receipt.status,
        "media_type": receipt.media_type,
        "bytes": len(body),
        "sha256": receipt.sha256,
        # A 200 can still be an interstitial page; only real PDF bytes can support review.
        "is_pdf": body.startswith(b"%PDF-"),
    }


def capture_due(
    store: FeeEvidenceStore,
    document: str,
    *,
    now: datetime,
    transport: httpx.AsyncBaseTransport | None = None,
    success_interval: timedelta = SUCCESS_INTERVAL,
    failure_interval: timedelta = FAILURE_INTERVAL,
) -> dict[str, Any]:
    """Capture one official document when the retained copy is stale; never certify it.

    The result is an unreviewed authentic version (or nothing). Transport errors store
    nothing because no bytes were received; they are reported, not raised, so unattended
    collection continues. Review remains the separate local operator attestation.
    """
    url = DOCUMENTS[document]
    attempts = _attempts(store, url)
    ok = [a for a in attempts if a.status == 200]
    report: dict[str, Any] = {
        "document": document,
        "url": url,
        "retained_attempts": len(attempts),
        "retained_successes": len(ok),
        "latest_success": _receipt_report(ok[-1]) if ok else None,
    }
    if ok and now - ok[-1].received_at < success_interval:
        return report | {"action": "skipped_recent_success"}
    if (
        attempts
        and attempts[-1].status != 200
        and now - attempts[-1].received_at < (failure_interval)
    ):
        return report | {
            "action": "skipped_recent_failure",
            "latest": _receipt_report(attempts[-1]),
        }
    try:
        version = asyncio.run(capture(document, transport=transport))
    except (httpx.HTTPError, ValueError) as exc:
        return report | {"action": "error", "error": f"{type(exc).__name__}: {exc}"[:500]}
    store.put(version)
    receipt = version.sources[0]
    return report | {
        "action": "captured",
        "version": version.version,
        "latest": _receipt_report(receipt),
        "certified": False,
        "refusal": version.refusal,
    }


def review(store: FeeEvidenceStore, request: dict[str, Any]) -> FeeVersion:
    if set(request) != {
        "source_versions",
        "series",
        "schedule",
        "effective_from",
        "effective_to",
        "review",
        "citations",
        "rounding",
    }:
        raise ValueError(
            "review requires exact fields; certification and clocks are server managed"
        )
    sources = tuple(s for name in request["source_versions"] for s in store.get(name).sources)
    if not sources or any(
        store.get(name).evidence_kind != "authentic" for name in request["source_versions"]
    ):
        raise ValueError("operator review requires retained authentic source versions")
    when = utc_now()
    return FeeVersion.model_validate(
        {
            "evidence_kind": "authentic",
            "sources": sources,
            "series": request["series"],
            "policy": FeePolicy.model_validate(
                {
                    "schedule": request["schedule"],
                    "version": "server-reviewed-v1",
                    "available_at": max(when, *(s.received_at for s in sources)),
                    "effective_from": request["effective_from"],
                    "effective_to": request["effective_to"],
                    "evidence": request["review"],
                    "evidence_hash": scientific_hash([s.model_dump(mode="json") for s in sources]),
                    "certified": True,
                }
            ),
            "reviewed_at": when,
            "review": request["review"],
            "citations": request["citations"],
            "rounding": request["rounding"],
            "refusal": "",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--capture", choices=tuple(DOCUMENTS))
    action.add_argument("--review", type=Path)
    action.add_argument("--list", action="store_true")
    action.add_argument(
        "--capture-due",
        nargs="+",
        choices=tuple(DOCUMENTS),
        help="unattended: capture each document only when its retained copy is stale",
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    root = workspace_path(repo, args.workspace)
    with workspace_lease(root):
        store = FeeEvidenceStore(root)
        if args.list:
            result: object = [v.summary() for v in store.snapshot()]
        elif args.capture_due:
            now = utc_now()
            result = [capture_due(store, document, now=now) for document in args.capture_due]
        else:
            version = (
                asyncio.run(capture(args.capture))
                if args.capture
                else review(store, json.loads(args.review.read_text()))
            )
            store.put(version)
            result = version.summary()
        print(json.dumps(result, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
