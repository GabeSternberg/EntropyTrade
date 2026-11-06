"""Unattended official fee capture: bounded cadence, immutable receipts, never certified."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from entropytrade.execution import fee_admin
from entropytrade.execution.fee_admin import DOCUMENTS, capture_due
from entropytrade.execution.fee_evidence import FeeEvidenceStore, select_fee

PDF = b"%PDF-1.7\nofficial schedule bytes"


def transport(status: int, body: bytes, calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(status, content=body, headers={"content-type": "application/pdf"})

    return httpx.MockTransport(handler)


def clock(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(fee_admin, "utc_now", lambda: when)


def test_capture_due_retains_unreviewed_pdf_and_skips_recent_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FeeEvidenceStore(tmp_path)
    calls: list[str] = []
    start = datetime(2026, 11, 6, 12, tzinfo=UTC)
    clock(monkeypatch, start)
    first = capture_due(store, "schedule", now=start, transport=transport(200, PDF, calls))
    assert first["action"] == "captured"
    assert first["certified"] is False
    assert first["latest"]["is_pdf"] is True
    assert first["latest"]["status"] == 200
    assert calls == [DOCUMENTS["schedule"]]
    (version,) = store.snapshot()
    assert version.policy is None
    assert version.refusal
    assert version.sources[0].body() == PDF
    assert version.sources[0].received_at == start

    later = start + timedelta(hours=23)
    second = capture_due(store, "schedule", now=later, transport=transport(200, PDF, calls))
    assert second["action"] == "skipped_recent_success"
    assert second["latest_success"]["sha256"] == version.sources[0].sha256
    assert len(calls) == 1
    assert len(store.snapshot()) == 1

    # After the interval a new immutable receipt is added; the first is never replaced.
    next_day = start + timedelta(hours=25)
    clock(monkeypatch, next_day)
    third = capture_due(store, "schedule", now=next_day, transport=transport(200, PDF, calls))
    assert third["action"] == "captured"
    assert third["retained_successes"] == 1
    assert len(store.snapshot()) == 2
    assert store.get(version.version) == version


def test_unreviewed_capture_never_selects_a_fee(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FeeEvidenceStore(tmp_path)
    when = datetime(2026, 11, 6, tzinfo=UTC)
    clock(monkeypatch, when)
    capture_due(store, "schedule", now=when, transport=transport(200, PDF, []))
    policy, audit = select_fee(
        store.snapshot(), series="KXHIGHPHIL", when=when + timedelta(days=1), data_kind="real"
    )
    assert policy is None
    assert audit["status"] == "refused"


def test_failures_are_retained_throttled_and_not_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FeeEvidenceStore(tmp_path)
    calls: list[str] = []
    start = datetime(2026, 11, 6, 12, tzinfo=UTC)
    clock(monkeypatch, start)
    page = b"<html>Too many requests</html>"
    first = capture_due(store, "schedule", now=start, transport=transport(429, page, calls))
    assert first["action"] == "captured"
    assert first["latest"] == first["latest"] | {"status": 429, "is_pdf": False}
    assert first["latest_success"] is None

    soon = start + timedelta(hours=1)
    second = capture_due(store, "schedule", now=soon, transport=transport(429, page, calls))
    assert second["action"] == "skipped_recent_failure"
    assert len(calls) == 1

    retry = start + timedelta(hours=4)
    clock(monkeypatch, retry)
    third = capture_due(store, "schedule", now=retry, transport=transport(200, PDF, calls))
    assert third["action"] == "captured"
    assert third["retained_attempts"] == 1
    assert len(calls) == 2
    assert len(store.snapshot()) == 2


def test_transport_error_stores_nothing(tmp_path: Path) -> None:
    store = FeeEvidenceStore(tmp_path)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("proxy refused", request=request)

    result = capture_due(
        store,
        "rounding",
        now=datetime(2026, 11, 6, tzinfo=UTC),
        transport=httpx.MockTransport(refuse),
    )
    assert result["action"] == "error"
    assert "ConnectError" in result["error"]
    assert not store.root.exists() or store.snapshot() == ()


def test_documents_are_tracked_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FeeEvidenceStore(tmp_path)
    when = datetime(2026, 11, 6, tzinfo=UTC)
    clock(monkeypatch, when)
    calls: list[str] = []
    capture_due(store, "schedule", now=when, transport=transport(200, PDF, calls))
    result = capture_due(
        store, "rounding", now=when, transport=transport(200, b"<html>rounding</html>", calls)
    )
    assert result["action"] == "captured"
    assert calls == [DOCUMENTS["schedule"], DOCUMENTS["rounding"]]
