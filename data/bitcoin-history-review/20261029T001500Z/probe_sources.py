"""One bounded, credential-free forward capture; never historical model evidence."""

import asyncio
import json
from pathlib import Path

from entropytrade.families.bitcoin_history import capture_samples
from entropytrade.families.public import capture_public
from entropytrade.weather.collection import WeatherConfig

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


async def main():
    async with asyncio.timeout(100):
        data = await capture_public(
            ROOT / "current-public-bitcoin", family="bitcoin",
            weather=WeatherConfig.model_validate_json(
                (REPO / "configs/data/weather-forward.json").read_text()
            ),
        )
    samples = capture_samples(ROOT / "current-public-bitcoin")
    result = {
        "capture": data.provenance,
        "recognized_samples": [s.model_dump(mode="json") for s in samples],
        "limitation": "A forward source-access check, not historical training or validation.",
    }
    (ROOT / "source-feasibility.json").write_text(json.dumps(result, indent=2) + "\n")


asyncio.run(main())
