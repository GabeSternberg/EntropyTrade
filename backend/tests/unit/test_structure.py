"""Stored KXHIGHPHIL strikes. A print is not a ladder price. No order."""

from pathlib import Path

from entropytrade.weather.structure import load_structural_scan

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "structure.py"


def test_the_scan_does_not_submit() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "PaperBroker" not in text
    assert ".submit(" not in text
    assert "urllib" not in text


def test_stored_thresholds_are_not_traded_from_prints() -> None:
    scanned = load_structural_scan(ROOT)
    assert scanned.orders_submitted == 0
    assert scanned.executable_thresholds == 4
    assert scanned.monotonic == ()
    assert len(scanned.non_executable) == 240
    assert all(item.kind == "non_executable" for item in scanned.non_executable)
