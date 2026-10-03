"""Ensemble control rank. No socket and no threshold."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.ensemble_rank import ensemble_rank_note, load_ensemble_rank
from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "ensemble_rank.py"
)
_RANKS = (
    10,
    14,
    20,
    22,
    24,
    24,
    22,
    24,
    22,
    20,
    18,
    12,
    13,
    19,
    29,
    30,
    30,
    28,
    26,
    26,
    23,
    23,
    21,
    16,
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text


def test_ensemble_control_rank_is_not_a_threshold() -> None:
    found = load_ensemble_rank(PUBLIC)
    assert len(found.hours) == 24
    assert found.skipped == ()
    assert found.hours[0].time == "2026-10-03T00:00"
    assert found.hours[-1].time == "2026-10-03T23:00"
    assert tuple(hour.rank for hour in found.hours) == _RANKS
    assert all(isinstance(hour.rank, int) for hour in found.hours)
    assert found.traded is False
    assert found.promoted is False
    note = ensemble_rank_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| GFS ensemble | no stored value |" in text
    assert "The rank was not divided and is not a probability." in note
    assert "A tie does not increase the rank." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
