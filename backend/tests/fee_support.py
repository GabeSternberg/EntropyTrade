"""CONTROLLED fee fixtures only; coefficients and eligible intentions are not empirical."""

import base64
import json
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from entropytrade.execution.fee_evidence import FeeCitation, FeeReceipt, FeeVersion
from entropytrade.features.registry import scientific_hash
from tests.unit.test_tracking import REPO, ready


def controlled_fee() -> FeeVersion:
    _, data, _, policy = ready()
    when = data.samples[0].decision_time - timedelta(days=60)
    raw = b"CONTROLLED fee fixture; not an official document or empirical fee evidence."
    receipt = FeeReceipt(
        url="https://fixture.invalid/CONTROLLED-fee-document",
        received_at=when,
        status=200,
        media_type="text/plain",
        body_base64=base64.b64encode(raw).decode(),
        sha256="sha256:" + sha256(raw).hexdigest(),
    )
    return FeeVersion(
        evidence_kind="controlled",
        series=("MENTIONS",),
        sources=(receipt,),
        reviewed_at=when,
        review="CONTROLLED server review; software evidence only",
        refusal="",
        rounding="cent_ceiling_per_fill",
        citations=(
            FeeCitation(
                source_hash=receipt.sha256,
                locator="CONTROLLED fixture",
                passage=raw.decode(),
                supports=("coefficient", "rounding", "series", "multiplier", "interval"),
            ),
        ),
        policy=policy.revalidated(
            available_at=when,
            effective_from=when,
            effective_to=when + timedelta(days=150),
            evidence_hash=scientific_hash([receipt.model_dump(mode="json")]),
            schedule=policy.schedule.revalidated(quadratic_coefficient=Decimal(".07")),
        ),
    )


def authentic_refusal() -> FeeVersion:
    """Exact original failed official receipt; no newly asserted availability or coefficient."""
    manifest = json.loads((REPO / "data/public/kalshi-fees/manifest.json").read_text())
    item = next(c for c in manifest["calls"] if c["path"].endswith("fee-schedule.error.html"))
    raw = (REPO / "data/public" / item["path"]).read_bytes()
    return FeeVersion.model_validate(
        {
            "evidence_kind": "authentic",
            "series": [],
            "sources": [
                {
                    "url": item["url"],
                    "received_at": item["fetched_at"],
                    "status": item["status"],
                    "media_type": "text/html",
                    "body_base64": base64.b64encode(raw).decode(),
                    "sha256": "sha256:" + sha256(raw).hexdigest(),
                }
            ],
            "refusal": "Official schedule HTTP 429; coefficient, scope and interval "
            "remain unverified",
        }
    )


def retain_cycle(root: Path, decisions: list[dict[str, object]]) -> list[dict[str, object]]:
    from entropytrade.data.sources import file_hash

    root.mkdir(parents=True, exist_ok=True)
    path = root / "decisions.json"
    path.write_text(json.dumps(decisions, sort_keys=True))
    return [{"path": path.name, "sha256": file_hash(path), "bytes": path.stat().st_size}]
