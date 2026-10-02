# EntropyTrade

Private, single-user research, backtesting and (eventually) automated trading for Kalshi
prediction markets. Not a SaaS product. Phase 0 is complete: domain types, architecture
and an audit of the open-source projects the design builds on. It does not trade. Phase 1
has not been started.

The requirements are in [`docs/project-spec.md`](docs/project-spec.md). Where the project
actually is, and how to resume it, is [`STATUS.md`](STATUS.md).

## Requirements

Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run entropytrade
make check          # ruff, mypy, pytest
```

`entropytrade` prints the version and the default trading mode (`read_only`). A checkout
cannot submit orders.

## Layout

`backend/src/entropytrade/` is the Python package. `domain/` holds venue-neutral types
(exact decimals, UTC timestamps, strategy specs, the order state machine). `exchange/`
defines `ExchangeGateway`; the Kalshi SDK, when it is added in Phase 1, may be imported
only inside `exchange/kalshi/`.

Kalshi's current API docs are checked out as an agent skill at
[`.agents/skills/kalshi-docs/`](.agents/skills/kalshi-docs/SKILL.md), pinned by
[`skills-lock.json`](skills-lock.json). Refresh with `npx skills add ammario/kalshi-docs --skill kalshi-docs -a cursor -y --copy`.
The command in the spec, `npx add-skill`, is the old name of that tool.

## Configuration

`.env.example` lists variable names and nothing else. Copy it to `.env` locally; `.env` is
gitignored. `configs/dev`, `configs/paper` and `configs/live` are mode files. Live mode also
requires `ENTROPYTRADE_LIVE_TRADING_ENABLED=true` in the execution process environment.

## Status

Phase 0 is complete. Phase 1 (read-only gateway and recorder) is next and waits
for an explicit go-ahead. See [`STATUS.md`](STATUS.md) before starting anything else.
The reuse decisions are in [`docs/external-repositories.md`](docs/external-repositories.md).
