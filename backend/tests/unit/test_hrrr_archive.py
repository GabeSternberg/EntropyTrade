"""The stored HRRR error. No socket and no invented temperature."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.hrrr_archive import hrrr_archive_note, load_hrrr_archive
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "hrrr_archive.py"
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_philadelphia_hrrr_error_does_not_invent_a_temperature() -> None:
    found = load_hrrr_archive(PUBLIC)
    assert found.http_status == 400
    assert "hrrr" in found.reason
    assert found.temperatures_invented is False
    assert found.traded is False
    assert found.promoted is False
    note = hrrr_archive_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| HRRR where available | no stored value |" in text
    assert "No temperature series was invented." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
