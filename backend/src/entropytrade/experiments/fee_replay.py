"""Offline deterministic experiment replay from retained inputs; no source/model requests."""

import argparse
import json
from pathlib import Path
from typing import Any

from entropytrade.data.sources import file_hash
from entropytrade.domain.strategy import StrategySpec
from entropytrade.experiments.data import ExperimentData, PredictionBundle
from entropytrade.experiments.engine import ExperimentConfig, evaluate_candidate


class FrozenPredictions:
    def __init__(self, bundles: dict[str, Any]) -> None:
        self.bundles = bundles

    def prepare(self, spec: StrategySpec, family: str) -> PredictionBundle:
        key = str((family, spec.spec_hash()))
        value = self.bundles[key]
        if isinstance(value, str):
            raise ValueError(value)
        return PredictionBundle.model_validate(value)


def reproduce(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    if inputs["schema"] != "experiment-replay-v1":
        raise ValueError("unknown experiment replay schema")
    data = ExperimentData.model_validate(inputs["data"])
    config = ExperimentConfig.model_validate(inputs["config"])
    predictor = FrozenPredictions(inputs["predictions"])
    research = inputs["research"]
    return [
        evaluate_candidate(c, research, data, predictor, config) for c in research["candidates"]
    ]


def verify(root: Path) -> dict[str, Any]:
    for name, digest in json.loads((root / "checksums.json").read_text()).items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or file_hash(path) != digest:
            raise ValueError("experiment replay artifact checksum/path mismatch")
    result = json.loads((root / "results.json").read_text())
    actual = reproduce(json.loads((root / "replay-inputs.json").read_text()))
    expected = [
        {k: v for k, v in c.items() if k not in {"rank", "ranking_basis"}}
        for c in result["candidates"]
    ]
    actual = [{k: v for k, v in c.items() if k != "rank"} for c in actual]
    if json.loads(json.dumps(actual)) != expected:
        raise ValueError("experiment differs from retained result")
    return {
        "verified": True,
        "candidates": len(actual),
        "submission_enabled": False,
        "limitation": "Software repeatability only; no certification of performance "
        "or source truth",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.experiment), sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
