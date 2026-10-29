"""Read-only legacy check. CONTROLLED evidence; never infer missing model provenance."""

import json
from pathlib import Path

from entropytrade.data.sources import file_hash
from entropytrade.tracking.replay import reproduce, verify

root = Path(
    "data/shadow-review/20261029/controlled-workspaces/"
    "test_multi_cycle_receipts_offi0/shadow/64d1e3b2-445d-4d8c-a6d5-fea49a9d159a"
)
original = root / "6c646be0-5683-4fdd-9852-d8e55ec81e11"
tampered = root / "a91a18a1-e277-4406-960b-7ec453e308ab"
before = {p: file_hash(p) for p in root.rglob("*") if p.is_file()}
inputs = json.loads((original / "decision-inputs.json").read_text())
assert "data_kind" not in inputs["bundle"]["model_metadata"]
rows = reproduce(inputs)
assert len(rows) == 2
assert all(
    r["status"] == "blocked"
    and "model_dataset_provenance" in r["reasons"]
    and r["intent"] is None
    and r["risk"] is None
    for r in rows
)
for specimen, expected in (
    (original, "shadow decisions differ from retained result"),
    (tampered, "shadow artifact checksum/path mismatch"),
):
    try:
        verify(specimen)
    except ValueError as exc:
        assert str(exc) == expected
        print(json.dumps({"specimen": str(specimen), "expected_refusal": str(exc)}))
    else:
        raise AssertionError("legacy/tampered input unexpectedly verified")
assert {p: file_hash(p) for p in before} == before
print(json.dumps({"legacy_decisions_blocked": len(rows), "original_files_unchanged": True}))
