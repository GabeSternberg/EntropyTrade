"""Chicago CLI days are not rows in the CLIPHL feature manifest."""

from dataclasses import fields
from pathlib import Path

from entropytrade.weather.feature_coverage import ChicagoManifestGap, load_chicago_manifest_gap

ROOT = Path(__file__).resolve().parents[3] / "data" / "public"


def test_chicago_has_no_prediction_record() -> None:
    gap = load_chicago_manifest_gap(ROOT)
    assert gap.chicago_label_days == 40
    assert gap.manifest_rows == 39
    assert gap.manifest_station == "CLIPHL"
    assert gap.chicago_prediction_records == 0
    assert "probability" not in {item.name for item in fields(ChicagoManifestGap)}
