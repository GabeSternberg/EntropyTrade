---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 0 checkpoint

Date: 2026-10-02. Phase 0 is complete. Phase 1 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions that need another
look, and the exact plan for Phase 1.

A copy of this file is in the repository at `docs/phase-reports/phase-0.md`.
The reuse matrix, with the claim-by-claim corrections, is
`docs/external-repositories.md`.

## What was built

A Python 3.12 package (`entropytrade`) that does not trade. It defines the
venue-neutral types later phases have to share, the `ExchangeGateway`
protocol, the trading-mode guard, and the documentation of an audit of every
repository named in spec section 2.

No order is submitted. No Kalshi credential is read. `kalshi-sdk` and
PydanticAI are not installed. The default trading mode is `read_only`.
`live` is accepted only when the environment is production and
`ENTROPYTRADE_LIVE_TRADING_ENABLED` is exactly `true`.

The domain types enforce the invariants the spec asked Phase 0 to lock in:

- UTC-aware timestamps. Naive datetimes are rejected. `Clock` is a protocol;
  `SimulatedClock` only moves forward.
- Money is `Decimal` on fixed grids: prices 4 decimal places in `[0, 1]`,
  order prices strictly inside `(0, 1)`, quantities 2 decimal places, money
  6 decimal places. Floats and bools are rejected. `notional` of a 4 dp price
  and a 2 dp quantity is exact on the 6 dp grid.
- Content hashes are `sha256:` of canonical JSON. Floats inside hashed content
  raise. `StrategySpec.spec_hash()` is a method, not a computed field, so it
  does not hash itself.
- `StrategySpec` is data: a market universe, predicates (`feature`, comparison,
  threshold), sizing with a Kelly fraction in `(0, 0.5]`, and
  `risk_overrides_allowed` fixed to `"none"`. An agent-authored spec requires
  a `generation_run_id`. There is no executable strategy code.
- Order states follow spec §18, including `unknown` only via reconciliation.
  Fills are monotone and cannot exceed the requested quantity. Terminal states
  are `filled`, `cancelled` and `rejected`.
- `RiskDecision` is fail-closed: approved only when every named check passed
  and the approved quantity is positive.
- Point-in-time selection returns the latest record per key with
  `available_at <= decision_time`. A record published later cannot change an
  earlier decision. Forecast `run_time` cannot be after `available_at`.
- Strike meaning matches live Kalshi contracts checked on 2026-10-02:
  `greater` with floor 89 is "value > 89", `less` with cap 82 is "value < 82",
  `between` is inclusive on both ends. `functional`, `custom` and `structured`
  are not evaluable.
- The order book is on a YES-price scale. NO bids become YES asks via
  `1 - price`. A crossed book is detected. Midpoint is not an executable price.
- Lifecycle transitions that increase capital rank require a `HumanApproval`
  recorded before the transition. An agent cannot apply one even if it holds
  an approval object. Downward moves need no approval.
- `ExchangeGateway` is a protocol. `submit_order` and `cancel_order` are on it
  so there is one seam, and `require_order_submission` raises
  `OrderSubmissionForbiddenError` unless the mode is `demo` or `live`. There
  is no `KalshiGateway` class and no streaming method yet. Ruff bans importing
  `kalshi` outside `exchange/kalshi/` and `pydantic_ai` outside `agents/`.
  An AST test walks the tree for the same rule.

`configs/{dev,paper,live}` exist as YAML. Nothing parses them yet (no PyYAML
dependency). `docker-compose.yml` defines api, collector, research and
execution, all on profile `app`, all running the version command. The image
was not built: this environment has no `docker` binary.

## Relevant architecture

```text
research agents  ->  StrategySpec  ->  backtest / validation  ->  human approval
                                                                    |
                                                                    v
strategy evaluator  ->  OrderIntent  ->  risk engine  ->  ApprovedOrderIntent
                                                                    |
                                                                    v
                                          execution engine  ->  ExchangeGateway  ->  Kalshi
```

Agents never get an order tool and never see a trading key. The risk engine
is the only thing that can mint an `ApprovedOrderIntent`. The execution
process is the only thing that can turn that into a submit.

Phase 0 adjusted the spec's credential sentence. Kalshi authenticates every
WebSocket, including public market data. The collector therefore needs its
own read-scoped key. The trading key still lives only in execution.

SDK models must not leave `exchange/kalshi/`. A successful order response
that fails SDK validation is an unknown outcome, reconciled by
`client_order_id`, not a clean rejection. That rule is documented and tested
only as a type invariant; the adapter that has to obey it is Phase 1 and
later.

One book and one money type are shared by the future live, paper and backtest
paths. That is why the SDK order book and the SDK's float-coercing decimals
were reimplemented instead of reused.

## Files added or changed

Already on `main` before this phase: the seed commit. The previous local
commit added `STATUS.md` and a verbatim `docs/project-spec.md`.

This phase adds:

- Domain and gateway: `backend/src/entropytrade/domain/` (`base`, `time`,
  `numeric`, `enums`, `ids`, `modes`, `lifecycle`, `market`, `market_data`,
  `signals`, `risk`, `orders`, `portfolio`, `observations`, `strategy`,
  `fees`, `runs`, `limits`) and `backend/src/entropytrade/exchange/gateway.py`.
  `exchange/kalshi/` is a docstring marking the only future SDK import site.
- Package placeholders with no behaviour: `api`, `agents`, `backtest`, `data`,
  `execution`, `features`, `ml`, `monitoring`, `portfolio`, `research`, `risk`,
  `strategies`, `strategy_registry`, `storage`, `weather`.
- Tests: `backend/tests/unit/test_numeric_time_ids.py`,
  `test_markets_books_accounting.py`, `test_orders_risk_lifecycle.py`,
  `test_strategy_and_pit.py`, `test_gateway.py`,
  `backend/tests/property/test_invariants.py`,
  `backend/tests/architecture/test_boundaries.py`, `backend/tests/support.py`.
- Tooling: `pyproject.toml`, `uv.lock`, `Makefile`, `.pre-commit-config.yaml`,
  `.gitignore`, `Dockerfile`, `docker-compose.yml`, `.env.example`,
  `configs/{dev,paper,live}/config.yaml`.
- Docs: `docs/architecture.md`, `data-model.md`, `backtesting.md`,
  `execution.md`, `risk.md`, `strategy-spec.md`, `security.md`,
  `external-repositories.md`, this report, `README.md`, `STATUS.md`,
  `THIRD_PARTY_NOTICES.md`, `vendor/README.md`.
- Layout placeholders: `frontend/src/README.md`, `data/{raw,normalized,features,backtests,cache}/.gitkeep`,
  `research/{notebooks,reports}/.gitkeep`. `vendor/` contains only the README.
- Kalshi docs: `.agents/skills/kalshi-docs/` (331 files, about 4 MB, CC0) and
  `skills-lock.json`. The copy matches audit commit
  `4582a4209c741a90d47092c00210cd13084c4235` (2026-10-01). The lock file stores
  a content hash, not that git SHA. The spec's `npx add-skill` is the old
  name; the working command is
  `npx skills add ammario/kalshi-docs --skill kalshi-docs -a cursor -y --copy`.

## Tests and results

`make check` on 2026-10-02:

- `ruff check` and `ruff format --check`: clean
- `mypy` strict, with the pydantic plugin: success, 48 source files
- `pytest`: 57 passed in 0.78s

Property tests cover complement as an involution, exact notional, float
rejection, the greater/less/between strike partition, YES+NO settlement
payout equalling the quantity in dollars, the net-edge identity, no exit
from a terminal order state, capital increases requiring approval, and
`select_as_of` ignoring records that were not yet available.

Not run: Docker image build (no `docker` binary), pre-commit hook installation
into `.git/hooks` (the config is committed; hooks are local), any test that
talks to Kalshi. The live GETs in the audit were public, unauthenticated,
and were not repeated as part of `make check`.

## External code and dependencies reused

Runtime dependency: pydantic `>=2.12,<3` (resolved in `uv.lock`). Dev:
Hypothesis, mypy, pre-commit, pytest, pytest-cov, ruff.

No third-party application source was vendored. The Kalshi docs skill is a
CC0 reference copy, not a library.

Planned, not installed:

- `kalshi-sdk==17.1.0` (MIT © 2026 Texas Coding, commit `6bbc01270d11`) in
  Phase 1, import allowed only under `exchange/kalshi/`.
- `pydantic-ai-slim[anthropic,openai]>=2.53,<3` (MIT © Pydantic Services Inc.)
  in Phase 5, import allowed only under `agents/`.

Everything else in spec section 2 was inspected and is reference or reject.
The matrix is `docs/external-repositories.md`. Copyright holders for projects
we did not copy are listed in `THIRD_PARTY_NOTICES.md` so a later copy has a
place to be recorded.

## Known weaknesses

- Config YAML is documentation. The process does not load it. Selecting
  `configs/live/config.yaml` does nothing until a later phase parses it and
  still has to pass `resolve_trading_mode`.
- `ExchangeGateway` has submit and cancel on the protocol, and no
  implementation. A future adapter that forgets `require_order_submission`
  would compile. The guard is a function the adapter must call, plus tests
  that a fake gateway does call it. Phase 1 should keep submit unimplemented
  for the read-only class, not merely uncalled.
- Streaming is intentionally absent from the protocol. Phase 1 has to extend
  it without leaking SDK message types.
- Fee math is not implemented. `FeeModelRef` is an identity (version,
  `fee_type`, multiplier, whether makers pay, effective time). Hard-coding
  0.07 would be wrong for KXHIGH, where makers pay 0.
- `docker-compose.yml` and the `Dockerfile` are untested here.
- The SDK pin will rot. That package shipped 17 majors in about five months
  with one human maintainer. Exact pin plus a thin gateway is the mitigation,
  and it is a treadmill.
- `skills-lock.json` does not pin a git SHA. The SHA is written in
  `docs/external-repositories.md` and `THIRD_PARTY_NOTICES.md`. A later
  `npx skills add` can move the docs without the lock file making that obvious
  beyond the content hash.
- Historical versus live endpoints are not in the code. A recorder that only
  calls `/markets` will miss settled markets older than the cutoff.
- Exchange sharding and per-shard collateral are recorded as `exchange_index`
  on the event and are otherwise unhandled.

## Decisions that need reconsideration

These are the places the spec's architecture looks wrong, or incomplete,
after the audit. I built Phase 0 to the corrected version. They need your
input before Phase 1 locks them in.

1. **Weather settlement is The Weather Company, not NWS, for current KXHIGH
   contracts.** Verified live on 2026-10-02 for `KXHIGHPHIL` (Philadelphia,
   station CLIPHL): "according to The Weather Company" (`https://weather.com/kalshi`)
   for the contracts whose target date is on or after 2026-08-14. The spec's
   weather vertical and mifisher's bot both assume NWS CLI. I version rules by
   the source in the contract text and refuse to evaluate a strike type we
   cannot parse. Confirm that Phase 4 should label history with NWS CLI before
   that date and TWC after it, and that Philadelphia is in the first vertical.
2. **The collector needs a credential.** "Execution is the only credential
   holder" is false for WebSocket market data. I restated it as two keys: a
   read-scoped key in the collector, a trading key only in execution. Confirm
   that split.
3. **Pin `kalshi-sdk==17.1.0` and accept the upgrade treadmill, or plan to
   fork.** I am not treating FIX support as a reason to adopt the SDK. The
   reasons to adopt it are REST coverage, async, Decimal wire types, and a
   maintained spec map. The reasons to be nervous are 17 majors in ~143 days
   and a bus factor of one.
4. **Do not vendor any of the bots or the backtester.** The spec says they
   already implement paper trading, risk, walk-forward, reconciliation and a
   research sandbox. Those claims are partial or false, and several of the
   implementations are unsafe (label leakage presented as forecasts, an
   escapable sandbox, a backtester that fills at the order's own limit, a
   REST client that 404s because it doubles `/trade-api/v2`). I kept the
   ideas and rejected the code. Say if you wanted a literal vendor copy anyway.
5. **PydanticAI stays out until Phase 5, and the pin is `<3`.** V2's own
   policy allows a V3 any time after about 2026-09-23. The meta-package pulls
   ~99 dependencies including the Logfire SDK; slim with Anthropic and OpenAI
   is ~28. Telemetry must stay off, or `include_content=False`.
6. **pmxt is rejected for V1, including its Kalshi adapter.** Buy is hard-wired
   to YES, money is float, and the Python SDK sends the private key to a Node
   sidecar. A few schema ideas (venue, outcome as its own side, build then
   submit) are already in our types.
7. **Fees are per series, not a global 0.07.** KXHIGH is `quadratic` with
   multiplier 1, so makers pay nothing. Charging taker fees on maker fills is
   conservative and wrong as a model. `FeeModelRef` is only an identity until
   you confirm the versioning key: `fee_type`, `fee_multiplier`, maker-pays,
   effective time.
8. **Strike semantics are the live ones, which the spec did not pin.** `less`
   is strict. `between` is inclusive. `greater` is strict above the floor.
   Encoded in `Strike.resolves_yes` and tested. This will change labels in
   every weather backtest if we had used "≤ cap".
9. **Exchange sharding is real and absent from the spec.** Collateral is
   per shard. Weather was not in the published shard table as of the 2026-09-03
   doc, so I store `exchange_index` and assume shard 0 until Kalshi says
   otherwise. Funding shards matters before any live order, not before Phase 1
   reads.
10. **A recorder that only hits `/markets` misses older settled markets.**
    They live under `/historical/*` once past `market_settled_ts` (around
    2026-08-02 when checked). Phase 1 should read `GET /historical/cutoff` and
    store which endpoint a row came from. Positions, later, have to be queried
    on both and deduped.
11. **Unknown order outcomes.** When we eventually submit, a non-4xx and a
    pydantic `ValidationError` on a 201 both mean "unknown, reconcile by
    `client_order_id`". The SDK drops Kalshi's error `code`. I want that in
    the execution design now so Phase 9 does not rediscover it. No submit code
    exists yet.
12. **Strategies stay a DSL.** The karshincheo generated-Python sandbox is not
    safe, and its forecast pipeline is label leakage. I would not revisit
    generated code unless you explicitly want a V2 agent that writes Python
    inside a real container. Spec section 10 already prefers the spec-first
    path for V1.
13. **Order book and decimals were reimplemented** so backtest and live share
    one book and so floats are rejected. The SDK book is a reasonable design
    reference and a poor dependency for replay.
14. **`configs/live` is inert.** It declares `trading_mode: live` and is not
    loaded. Live still requires the env flag and an explicit mode resolution.
    If you would rather the live file not exist until Phase 9, it can be
    deleted; I kept it because spec section 3 asks for the directory.

## Exact plan for Phase 1

Do not start until you say so. Phase 1 is read-only. It does not submit,
amend, decrease or cancel orders, and it does not add a trading key.

1. Add `kalshi-sdk==17.1.0`. Import it only inside `entropytrade.exchange.kalshi`.
2. `KalshiGateway` implements `ExchangeGateway` with `TradingMode.READ_ONLY`.
   Construct `KalshiConfig.demo()` or `.production()` from config. Never
   `from_env()`. Refuse to start if `KALSHI_ALLOW_UNKNOWN_HOST` is set.
   Set `max_retries=0`. Wrap the HTTP transport so rate-limit headers and the
   raw error body are visible. Map SDK models to domain types at the boundary.
   Money stays `Decimal`.
3. Extend the protocol with a streaming surface that yields domain events
   (book snapshot, book delta, trade, lifecycle), not SDK messages.
4. Discovery: series, events, markets. Persist metadata. Store rules text and
   `rules_hash`. Record the settlement source and the date it applies. For
   KXHIGH*, NWS CLI before 2026-08-14 and The Weather Company on and after
   that date, taken from the contract text rather than hard-coded as a
   forever fact.
5. REST order books from `orderbook_fp` (`yes_dollars` / `no_dollars`) into
   the Phase 0 `OrderBook`.
6. WebSocket: connect with the read-scoped key, apply book deltas through the
   same book type, record the trade feed and lifecycle events. On reconnect,
   resubscribe and resync. Use the SDK's gap handling for the book channels.
   Add our own sequence checks for `trade` and lifecycle, which the SDK ignores.
   A gap is a health event and a reason to refetch, not a silent skip.
7. Limits: `GET /account/limits` and endpoint costs. Our budgeter owns pacing.
   A 429 today is `{"error":"too many requests"}` with no `Retry-After`.
8. Persistence: immutable raw payloads plus normalized rows for markets, rule
   versions, trades, book snapshots, book deltas and lifecycle events.
   Include `available_at` / receive time. Include which endpoint (live or
   `/historical/*`) a row came from, after reading `/historical/cutoff`.
   Store `exchange_index`.
9. Health: connected or not, last message time, last gap, lag.
10. Replay: a recording from this collector can be played back through the
    same book type without the network. The SDK's REST fixture transport is
    not the recording format (it ignores bodies and wraps).

Acceptance, from the spec: run for hours against demo or read-only production,
restart without corrupting or duplicating stored rows, reconnect after a
dropped socket, and detect a sequence gap.

Out of scope for Phase 1: paper fills, fees as a calculator, order submission,
PydanticAI, the dashboard, and any live credential beyond a read-scoped key
you supply at runtime. `.env.example` stays names only.
