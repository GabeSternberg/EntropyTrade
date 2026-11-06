"""Operator manual import of the official schedule PDF (issue #6).

Explicit provenance, import-time availability, never certified on import, unchanged hashes
for every previously retained receipt, and no effect on the unattended capture cadence.
"""

import base64
import json
import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import httpx
import pytest

from entropytrade.execution import fee_admin
from entropytrade.execution.fee_admin import (
    MANUAL_IMPORT_REFUSAL,
    capture_due,
    import_schedule,
    review,
)
from entropytrade.execution.fee_evidence import (
    OFFICIAL_SCHEDULE_URL,
    FeeEvidenceStore,
    FeeReceipt,
    FeeVersion,
    ManualImport,
    select_fee,
)

PDF = b"%PDF-1.7\noperator-downloaded official schedule bytes"
REPO = Path(__file__).resolve().parents[3]
RETAINED = REPO / "data/fee-evidence-review/20261030"
IMPORTED_AT = datetime(2026, 11, 6, 15, tzinfo=UTC)
DOWNLOADED_AT = datetime(2026, 11, 6, 14, 30, tzinfo=UTC)


def clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(fee_admin, "utc_now", lambda: when)


def pdf_file(tmp_path: Path, body: bytes = PDF, name: str = "kalshi-fee-schedule.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(body)
    return path


def imported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FeeVersion:
    clock(monkeypatch, IMPORTED_AT)
    return import_schedule(
        pdf_file(tmp_path),
        downloaded_at=DOWNLOADED_AT,
        original_filename="kalshi-fee-schedule.pdf",
        note="Downloaded in a desktop browser from the official kalshi.com URL",
    )


def test_import_retains_exact_bytes_with_explicit_provenance_and_import_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = imported(tmp_path, monkeypatch)
    (receipt,) = version.sources
    assert receipt.body() == PDF
    assert receipt.sha256 == "sha256:" + sha256(PDF).hexdigest()
    assert receipt.url == OFFICIAL_SCHEDULE_URL
    assert receipt.manual_import is not None
    assert receipt.manual_import.operator_downloaded_at == DOWNLOADED_AT
    # Availability is the import clock, never the earlier operator-attested download time.
    assert receipt.received_at == IMPORTED_AT
    assert version.available_at == IMPORTED_AT
    assert version.policy is None
    assert version.refusal == MANUAL_IMPORT_REFUSAL

    store = FeeEvidenceStore(tmp_path / "workspace")
    identifier = store.put(version)
    reloaded = store.get(identifier)
    assert reloaded == version
    assert reloaded.sources[0].manual_import == receipt.manual_import
    summary = version.summary()
    assert summary["sources"][0]["manual_import"]["note"].startswith("Downloaded")
    assert "body_base64" not in summary["sources"][0]

    policy, audit = select_fee(
        store.snapshot(),
        series="KXHIGHPHIL",
        when=IMPORTED_AT + timedelta(days=1),
        data_kind="real",
    )
    assert policy is None
    assert audit["status"] == "refused"


def test_previously_retained_versions_keep_their_exact_hashes() -> None:
    raw = (RETAINED / "fresh-source-version.json").read_bytes()
    recorded = json.loads((RETAINED / "fresh-capture.json").read_text())
    version = FeeVersion.model_validate_json(raw)
    assert version.version == recorded["version"]
    assert "manual_import" not in version.model_dump(mode="json")["sources"][0]
    assert "manual_import" not in version.model_dump_json()


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"<!DOCTYPE html><html>Too Many Requests</html>", "only PDF"),
        (b"", "only PDF"),
    ],
)
def test_import_refuses_non_pdf_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, message: str
) -> None:
    clock(monkeypatch, IMPORTED_AT)
    with pytest.raises(ValueError, match=message):
        import_schedule(
            pdf_file(tmp_path, body),
            downloaded_at=DOWNLOADED_AT,
            original_filename="x.pdf",
            note="n",
        )


def test_import_refuses_relative_symlink_missing_and_oversized_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock(monkeypatch, IMPORTED_AT)
    real = pdf_file(tmp_path)
    link = tmp_path / "link.pdf"
    link.symlink_to(real)
    big = pdf_file(tmp_path, b"%PDF-" + b"0" * (8 * 1024 * 1024), "big.pdf")
    kwargs = {"downloaded_at": DOWNLOADED_AT, "original_filename": "x.pdf", "note": "n"}
    with pytest.raises(ValueError, match="absolute"):
        import_schedule(Path("relative.pdf"), **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-symlink"):
        import_schedule(link, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-symlink"):
        import_schedule(tmp_path / "missing.pdf", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="byte budget"):
        import_schedule(big, **kwargs)  # type: ignore[arg-type]


def test_import_refuses_download_time_after_import_and_naive_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock(monkeypatch, IMPORTED_AT)
    with pytest.raises(ValueError, match="before their import clock"):
        import_schedule(
            pdf_file(tmp_path),
            downloaded_at=IMPORTED_AT + timedelta(seconds=1),
            original_filename="x.pdf",
            note="n",
        )
    with pytest.raises(ValueError, match="naive datetime"):
        import_schedule(
            pdf_file(tmp_path),
            downloaded_at=datetime(2026, 11, 6, 14),  # noqa: DTZ001 - intentionally naive
            original_filename="x.pdf",
            note="n",
        )


def receipt_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "url": OFFICIAL_SCHEDULE_URL,
        "received_at": IMPORTED_AT,
        "status": 200,
        "media_type": "application/pdf",
        "body_base64": base64.b64encode(PDF).decode(),
        "sha256": "sha256:" + sha256(PDF).hexdigest(),
        "manual_import": ManualImport(
            operator_downloaded_at=DOWNLOADED_AT, original_filename="x.pdf", note="n"
        ),
    }
    return payload | changes


@pytest.mark.parametrize(
    "changes",
    [
        {"url": "https://docs.kalshi.com/getting_started/fee_rounding"},
        {"status": 429},
        {"media_type": "text/html"},
        {
            "body_base64": base64.b64encode(b"<html>").decode(),
            "sha256": "sha256:" + sha256(b"<html>").hexdigest(),
        },
    ],
)
def test_manual_provenance_cannot_be_attached_to_other_sources(
    changes: dict[str, object],
) -> None:
    FeeReceipt.model_validate(receipt_payload())
    with pytest.raises(ValueError, match="manual imports are limited"):
        FeeReceipt.model_validate(receipt_payload(**changes))


def test_imports_do_not_satisfy_or_delay_unattended_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FeeEvidenceStore(tmp_path / "workspace")
    store.put(imported(tmp_path, monkeypatch))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(429, content=b"<html>429</html>")

    later = IMPORTED_AT + timedelta(minutes=5)
    clock(monkeypatch, later)
    report = capture_due(store, "schedule", now=later, transport=httpx.MockTransport(handler))
    assert report["action"] == "captured"
    assert report["retained_attempts"] == 0
    assert report["retained_successes"] == 0
    assert calls == [OFFICIAL_SCHEDULE_URL]
    assert len(store.snapshot()) == 2


def test_operator_review_of_an_import_is_later_than_the_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FeeEvidenceStore(tmp_path / "workspace")
    source = store.put(imported(tmp_path, monkeypatch))
    reviewed_at = IMPORTED_AT + timedelta(hours=2)
    clock(monkeypatch, reviewed_at)
    sha = store.get(source).sources[0].sha256
    request = {
        "source_versions": [source],
        "series": ["KXHIGHPHIL"],
        "schedule": {
            "fee_type": "quadratic",
            "fee_multiplier": "1",
            "maker_pays": False,
            "quadratic_coefficient": "0.07",
        },
        "effective_from": "2026-11-01T00:00:00Z",
        "effective_to": "2026-12-01T00:00:00Z",
        "review": "Controlled test review of imported bytes",
        "citations": [
            {
                "source_hash": sha,
                "locator": "p.1",
                "passage": "test passage",
                "supports": ["coefficient", "rounding", "series", "multiplier", "interval"],
            }
        ],
        "rounding": "cent_ceiling_per_fill",
    }
    version = review(store, request)
    assert version.sources[0].manual_import is not None
    assert version.reviewed_at == reviewed_at
    assert version.available_at == reviewed_at
    store.put(version)
    # The certified policy is unknown before its review clock, even though the operator
    # attests an earlier download.
    policy, audit = select_fee(
        store.snapshot(),
        series="KXHIGHPHIL",
        when=reviewed_at - timedelta(minutes=1),
        data_kind="real",
    )
    assert policy is None
    assert audit["reason"] == "late_fee_evidence"
    policy, audit = select_fee(
        store.snapshot(), series="KXHIGHPHIL", when=reviewed_at, data_kind="real"
    )
    assert policy is not None
    assert audit["status"] == "applicable"


def test_cli_requires_attestation_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["fee_admin", "--workspace", str(tmp_path), "--import-schedule", str(pdf_file(tmp_path))],
    )
    with pytest.raises(SystemExit):
        fee_admin.main()
    assert "requires --downloaded-at and --note" in capsys.readouterr().err
    monkeypatch.setattr(
        sys, "argv", ["fee_admin", "--workspace", str(tmp_path), "--list", "--note", "x"]
    )
    with pytest.raises(SystemExit):
        fee_admin.main()
    assert "apply only to --import-schedule" in capsys.readouterr().err
