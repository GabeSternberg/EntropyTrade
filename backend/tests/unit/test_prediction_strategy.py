"""cli-aligned is the name on the records. It is not a stored StrategySpec."""

from pathlib import Path

from entropytrade.agents.fixture import demo_specs
from entropytrade.weather.provenance import load_prediction_strategy

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "data" / "public"


def test_cli_aligned_has_no_stored_spec() -> None:
    named = load_prediction_strategy(PUBLIC)
    assert named.records == 39
    assert named.strategy_id == "cli-aligned"
    assert named.strategy_version == 1
    specs = {spec.strategy_id for spec in demo_specs()}
    assert specs == {
        "phl-copy-rejected",
        "phl-kelly",
        "phl-probability-055",
        "phl-probability-090",
    }
    assert named.strategy_id not in specs
    hits = [
        path
        for path in PUBLIC.rglob("*.json")
        if named.strategy_id in path.read_text(encoding="utf-8")
    ]
    assert hits == [PUBLIC / "features" / "cli-rescore-predictions.json"]
