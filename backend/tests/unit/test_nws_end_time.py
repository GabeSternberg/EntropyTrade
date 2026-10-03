"""Distinct NWS end times. No socket and no computed duration."""

import hashlib
from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_end_time import load_nws_end_time, nws_end_time_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_end_time.py"
)
_DIGEST = "6a1789c21d3818d361b411153ee7de6ee2e3d3bed2a8ad9f9dee62f875b82276"


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert "import datetime" not in text
    assert "timedelta" not in text
    assert 'period.get("endTime")' in text


def test_end_times_are_not_a_duration() -> None:
    found = load_nws_end_time(PUBLIC)
    assert found.periods == 156
    assert len(found.values) == 156
    assert found.values[0] == "2026-10-03T04:00:00-04:00"
    assert found.values[-1] == "2026-10-09T15:00:00-04:00"
    digest = hashlib.sha256("\n".join(found.values).encode()).hexdigest()
    assert digest == _DIGEST
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_end_time_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "156 distinct values." in note
    assert "A duration was not computed." in note
    assert "A string was not rewritten." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It was not aligned to the CLI decision clock." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
