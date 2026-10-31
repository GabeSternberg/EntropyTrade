"""Local fee administration. No browser certification, credentials or trading transport.

Capture official bytes now, then explicitly review source passages and all assumptions.
Review timestamps are assigned here, never imported from a review request.
"""

import argparse
import asyncio
import base64
import json
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


async def capture(document: str) -> FeeVersion:
    url = DOCUMENTS[document]
    async with (
        httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client,
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
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    root = workspace_path(repo, args.workspace)
    with workspace_lease(root):
        store = FeeEvidenceStore(root)
        if args.list:
            result: object = [v.summary() for v in store.snapshot()]
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
