"""Distinct NWS icon strings. No socket and no fetched icons."""

from decimal import Decimal
from pathlib import Path

from entropytrade.weather.informational_rules import PRICE_THRESHOLD
from entropytrade.weather.nws_icon import load_nws_icon, nws_icon_note
from entropytrade.weather.revision_rule import REVISION_MINIMUM_F

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"
NOTE = ROOT / "docs" / "research" / "feature-manifest-coverage.md"
_SOURCE = Path(__file__).resolve().parents[2] / "src" / "entropytrade" / "weather" / "nws_icon.py"
_VALUES = (
    "https://api.weather.gov/icons/land/day/bkn?size=small",
    "https://api.weather.gov/icons/land/day/few?size=small",
    "https://api.weather.gov/icons/land/day/rain_showers,30?size=small",
    "https://api.weather.gov/icons/land/day/rain_showers,40?size=small",
    "https://api.weather.gov/icons/land/day/rain_showers,70?size=small",
    "https://api.weather.gov/icons/land/day/sct?size=small",
    "https://api.weather.gov/icons/land/day/skc?size=small",
    "https://api.weather.gov/icons/land/night/few?size=small",
    "https://api.weather.gov/icons/land/night/ovc?size=small",
    "https://api.weather.gov/icons/land/night/rain_showers,20?size=small",
    "https://api.weather.gov/icons/land/night/rain_showers,70?size=small",
    "https://api.weather.gov/icons/land/night/sct?size=small",
    "https://api.weather.gov/icons/land/night/skc?size=small",
)


def test_the_loader_does_not_open_a_socket() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "import urllib" not in text
    assert "import httpx" not in text
    assert "import socket" not in text
    assert 'period.get("icon")' in text


def test_icon_strings_are_not_fetched() -> None:
    found = load_nws_icon(PUBLIC)
    assert found.periods == 156
    assert found.values == _VALUES
    assert found.skipped == ()
    assert found.traded is False
    assert found.promoted is False
    note = nws_icon_note(PUBLIC)
    text = NOTE.read_text(encoding="utf-8")
    assert note in text
    assert "| NWS forecast | no stored value |" in text
    assert "13 distinct values." in note
    assert "An icon was not fetched." in note
    assert "A string was not rewritten into another word." in note
    assert "The count was not compared to 0.40 or to 2°F." in note
    assert "It is not a threshold." in note
    assert "Nothing was traded." in note
    assert Decimal(2) == REVISION_MINIMUM_F
    assert Decimal("0.4000") == PRICE_THRESHOLD
