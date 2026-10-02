# EntropyTrade

Private, single-user research, backtesting and (eventually) automated trading for Kalshi
prediction markets. Not a SaaS product. Phase 0 is complete: domain types, architecture
and an audit of the open-source projects the design builds on. Phase 1 is a read-only
Kalshi gateway and a SQLite recorder. Phase 2 is paper accounting and the risk gate.
Phase 3 replays recorded books without showing the strategy future rows. Phase 4 scores
daily-high baselines from recorded weather bodies. Phase 5 turns a prompt into
StrategySpecs and backtests the ones that pass the critic and the interpreter.
Phase 6 stores those specs and serves a read-only registry page.
Phase 7 flags executable-price violations and can paper them.
Phase 8 compares a paper or shadow price with the next recorded print.
Phase 9 classifies a submit without opening a socket. The Kalshi gateway
still refuses every submit. None of this sends exchange orders.

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
defines `ExchangeGateway`. The Kalshi SDK (`kalshi-sdk==17.1.0`) is imported only inside
`exchange/kalshi/`.

Kalshi's current API docs are checked out as an agent skill at
[`.agents/skills/kalshi-docs/`](.agents/skills/kalshi-docs/SKILL.md), pinned by
[`skills-lock.json`](skills-lock.json). Refresh with `npx skills add ammario/kalshi-docs --skill kalshi-docs -a cursor -y --copy`.
The command in the spec, `npx add-skill`, is the old name of that tool.

## Configuration

`.env.example` lists variable names and nothing else. Copy it to `.env` locally; `.env` is
gitignored. `configs/dev`, `configs/paper` and `configs/live` are mode files. Live mode also
requires `ENTROPYTRADE_LIVE_TRADING_ENABLED=true` in the execution process environment.

## Status

Phase 9 is complete as a closed gate. Phase 10 (decay detection, no live
order) is next. See [`STATUS.md`](STATUS.md) before starting anything else.
The scanner is described in [`docs/scanner.md`](docs/scanner.md).
The reuse decisions are in [`docs/external-repositories.md`](docs/external-repositories.md).
