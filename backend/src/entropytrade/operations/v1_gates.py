"""Read-only report of the human-attested V1 acceptance gates.

Code and tests cannot satisfy these gates: each needs authentic evidence plus a named human
attestation. This module never writes or fabricates an attestation. A gate is ``open`` unless
``<root>/<gate_id>.json`` exists, parses, names an attester and clock, and every evidence file it
lists exists under ``<root>`` with a matching SHA-256. Anything else is ``invalid`` (fail closed).
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GATES: tuple[tuple[str, str, str], ...] = (
    ("authentic_forward_validation", "Authentic history and forward validation", ""),
    ("certified_fees", "Certified effective fees", "issue #6"),
    ("provider_verification", "Authorized research-provider verification", ""),
    ("second_family", "User-approved second major family", ""),
    ("sustained_operation", "Sustained authentic paper/shadow operation", ""),
    ("storage_runway", "Evidence storage runway decision", "issue #21"),
    ("public_acceptance", "Public acquisition and browser acceptance", "issue #3"),
    ("final_acceptance", "Independent final V1 acceptance", ""),
)
_REQUIRED = ("gate_id", "attested_by", "attested_at", "statement", "evidence")


@dataclass(frozen=True)
class GateStatus:
    gate_id: str
    title: str
    reference: str
    status: str  # open | attested | invalid
    detail: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _check(gate_id: str, root: Path) -> tuple[str, str]:
    path = root / f"{gate_id}.json"
    if not path.is_file():
        return "open", "no attestation file"
    try:
        doc: Any = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return "invalid", f"unreadable attestation: {error}"
    if not isinstance(doc, dict) or any(key not in doc for key in _REQUIRED):
        return "invalid", f"attestation must contain {', '.join(_REQUIRED)}"
    if doc["gate_id"] != gate_id:
        return "invalid", "gate_id does not match the file name"
    if not all(isinstance(doc[k], str) and doc[k].strip() for k in _REQUIRED[1:4]):
        return "invalid", "attested_by, attested_at and statement must be non-empty text"
    evidence = doc["evidence"]
    if not isinstance(evidence, list) or not evidence:
        return "invalid", "evidence must list at least one file"
    base = root.resolve()
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            return "invalid", "each evidence entry needs a path and sha256"
        target = (root / item["path"]).resolve()
        if base not in target.parents or not target.is_file():
            return "invalid", f"evidence missing or outside root: {item['path']}"
        if _sha256(target) != item.get("sha256"):
            return "invalid", f"evidence hash mismatch: {item['path']}"
    return "attested", f"attested by {doc['attested_by']} at {doc['attested_at']}"


def v1_gate_report(root: Path) -> dict[str, Any]:
    gates = [GateStatus(gid, title, ref, *_check(gid, root)).__dict__ for gid, title, ref in GATES]
    open_ids = [g["gate_id"] for g in gates if g["status"] != "attested"]
    return {
        "root": str(root),
        "gates": gates,
        "open": open_ids,
        "v1_complete": not open_ids,
    }
