"""The stored prediction records do not name a calibration version."""

from pathlib import Path

from entropytrade.weather.provenance import load_calibration_gap

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"
SPEC = Path(__file__).resolve().parents[3] / "docs" / "project-spec.md"


def test_calibration_version_is_empty_on_every_record() -> None:
    gap = load_calibration_gap(ROOT)
    assert gap.records == 39
    assert gap.calibration_version_empty == 39
    assert "calibration version" in SPEC.read_text(encoding="utf-8")
