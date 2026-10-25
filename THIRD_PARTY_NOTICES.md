# Third-party notices

Phase 0 copies no third-party source into this repository except the Kalshi
documentation skill, which is CC0. Runtime dependencies now include Pydantic, kalshi-sdk, PydanticAI slim,
MLflow and PyArrow; historical planned-pin notes below record the original audit.
Everything else below is recorded so a later copy or dependency has a place
to land, and so the audit's copyright holders are not forgotten.

## Direct dependency (this commit)

### pydantic

- Project: https://github.com/pydantic/pydantic
- License: MIT
- Copyright: © Samuel Colvin and pydantic contributors
- How used: domain models (`entropytrade.domain`). Version floor `>=2.12,<3`,
  resolved in `uv.lock`.

## Documentation reference (this commit)

### Kalshi API docs

- Project: https://github.com/ammario/kalshi-docs
- License: CC0 1.0 Universal (public domain dedication)
- Location: `.agents/skills/kalshi-docs/`
- Pin: `skills-lock.json` content hash
  `9e8a282db429c96e96e10c264f2a8ae8da80fe128304325895fb3f51f378bf77`.
  The audit clone was commit `4582a4209c741a90d47092c00210cd13084c4235`
  (2026-10-01). The skills installer records a content hash, not a git SHA.
- The spec's command `npx add-skill` is the previous name of `npx skills add`.

## Planned dependencies (not installed)

### kalshi-sdk

- Project: https://github.com/TexasCoding/kalshi-python-sdk
- PyPI: `kalshi-sdk`
- License: MIT
- Copyright: © 2026 Texas Coding
- Planned pin: `kalshi-sdk==17.1.0` (commit `6bbc01270d11`, 2026-09-30)
- How it will be used: inside `entropytrade.exchange.kalshi` only, starting
  in Phase 1. Domain types stay SDK-free.
- The OpenAPI documents shipped inside that package are Kalshi's, not the
  SDK author's.

### pydantic-ai-slim

- Project: https://github.com/pydantic/pydantic-ai
- License: MIT
- Copyright: © Pydantic Services Inc. 2024 to present
- Planned pin: `pydantic-ai-slim[anthropic,openai]>=2.53,<3`
  (2.53.0 is commit `6bc07cf18b06`). Not a dependency until Phase 5.
- The full `pydantic-ai` meta-package is intentionally not used.

## Inspected, not copied

These projects were cloned and read for the reuse matrix in
`docs/external-repositories.md`. No source from them is in this tree. If any
file is later copied, it goes under `vendor/` with its `LICENSE` and upstream
commit, and a notice is added here.

| Project | License | Copyright |
| --- | --- | --- |
| karshincheo/kalshi-trading | MIT | © 2026 Kar Shin Cheo |
| mifisher/kalshi-weather-bot | MIT | © 2026 Michael Fisher |
| Quentin-Piot/prediction-market-backtester | MIT | © 2026 Quentin Piot |
| Jon-Becker/prediction-market-analysis (vendored inside the backtester; not re-cloned) | MIT | © 2026 Jonathan Becker |
| Viprasol-Tech/kalshi-trading-bot | MIT | © 2025 Viprasol Tech Private Limited |
| pmxt-dev/pmxt | MIT | © 2026 pmxt.dev (repository root) and © 2026 qoery.com (`core/`) |
| pydantic/pydantic-ai | MIT | © Pydantic Services Inc. 2024 to present |

Development tools (ruff, mypy, pytest, Hypothesis, pre-commit, uv) are
dev-only and are pinned in `uv.lock` or `.pre-commit-config.yaml`.

## R1 analytical dependency

### Apache Arrow / PyArrow

- Project: https://arrow.apache.org/
- License: Apache License 2.0 (Apache Software Foundation).
- Version: `pyarrow>=19,<20`, locked to 19.0.1. Already installed through MLflow;
  R1 makes the dependency explicit for Parquet dataset writing/inspection.
- Used as a package dependency; no upstream implementation source was copied.

R1 continues to use `kalshi-sdk==17.1.0` inside the existing SDK boundary,
including its authentication, connection manager, wire models and pagination
transport. Narrow response compatibility code is our own. No additional
third-party repository implementation was vendored.

## R2 statistical and capture dependencies

R2 makes packages already present in the locked dependency graph explicit dependencies:
scikit-learn (BSD-3-Clause), NumPy (BSD-3-Clause), joblib (BSD-3-Clause), threadpoolctl
(BSD-3-Clause), HTTPX (BSD-3-Clause). Versions remain pinned by `uv.lock`; no implementation
source was copied. scikit-learn supplies imputation, scaling, regularized regression,
histogram gradient boosting, logistic/isotonic calibration and scoring. joblib stores
trusted local models; threadpoolctl bounds numerical worker threads. Existing PyArrow,
SQLite and MLflow handle analytical data, application state and experiment tracking.

Forecast source attribution: [Open-Meteo](https://open-meteo.com/) GFS seamless forecasts
and [NOAA/National Weather Service](https://www.weather.gov/documentation/services-web-api)
hourly forecasts. Source URLs, grid/units and actual receipt provenance remain in the raw
archive. Open-Meteo data is offered under CC BY 4.0 with API usage terms; check current
provider terms when changing deployment or usage. These are forecast products, not an
interchangeable settlement authority for Weather Company contracts.
