# External repositories

Audit date: 2026-10-02. Each repository was cloned and read at the commit below.
Nothing from these trees was vendored as runtime implementation. **R0 clarification
(2026-10-24):** this is a historical source audit, not a fresh upstream assessment.
The current lock installs `kalshi-sdk` 17.1.0, `pydantic-ai-slim` 2.53.0,
Pydantic 2.13.5 and MLflow 2.22.5. The CC0 Kalshi documentation reference is
retained under `.agents/skills/kalshi-docs/`. No runtime dependency changed in R0.
The SDK boundary and typed agent choice remain applicable; the agents are still
scripted and bulk analytical/model libraries are not an implemented pipeline.
Recheck upstream APIs, maturity, licensing and compatibility before R1/R2/R3
implementation; the dated findings below are not current service verification.

Full notes from the inspection live with the phase report. This file is the
decision record: what the spec claimed, what the code actually does, and how
EntropyTrade will reuse it.

| Project | Commit | Date | License |
| --- | --- | --- | --- |
| TexasCoding/kalshi-python-sdk (PyPI `kalshi-sdk` 17.1.0) | `6bbc01270d11` | 2026-09-30 | MIT © 2026 Texas Coding |
| ammario/kalshi-docs | `4582a4209c74` | 2026-10-01 | CC0 1.0 |
| karshincheo/kalshi-trading | `0f1f3d195244` | 2026-06-10 | MIT © 2026 Kar Shin Cheo |
| mifisher/kalshi-weather-bot | `45e69671040f` | 2026-07-28 | MIT © 2026 Michael Fisher |
| Quentin-Piot/prediction-market-backtester | `c77dff74680b` | 2026-03-07 | MIT © 2026 Quentin Piot |
| Jon-Becker/prediction-market-analysis (vendored inside the backtester) | claimed `f47ceb2ba906`, not re-verified offline | — | MIT © 2026 Jonathan Becker |
| Viprasol-Tech/kalshi-trading-bot | `c18882736e78` | 2026-06-06 | MIT © 2025 Viprasol Tech Private Limited |
| pmxt-dev/pmxt (v2.54.0) | `4a367d812541` | 2026-07-18 | MIT, two holders: © 2026 pmxt.dev (root) and © 2026 qoery.com (`core/`) |
| pydantic/pydantic-ai (`pydantic-ai-slim` 2.53.0) | `6bc07cf18b06` | 2026-10-01 | MIT © Pydantic Services Inc. 2024–present |

## Where the spec was wrong or only partly true

The spec's section 2 treats several of these projects as implementations we
can adopt. After reading the current code, most of those claims are partial
or false. The architecture docs already follow the corrections below.

**Kalshi Python SDK.** REST, async, WebSocket, V2 orders, Decimal wire types
and the MIT license are real. Sequence-gap handling is only on
`orderbook_delta`, `orderbook_snapshot` and `order_group_updates`. Fills and
user orders have no sequence number and drop the oldest frame by default.
Record/replay is REST-only, ignores request bodies and wraps fixtures. FIX
exists and is immature (no outbound store, mock-only tests). The README claim
that POST/DELETE never retry is false: they retry `ConnectError` and
`PoolTimeout`. The default environment is production. `KALSHI_ALLOW_UNKNOWN_HOST`
can redirect a signed request. A 201 whose body fails pydantic validation
raises after the order is already live, and Kalshi's error `code` is discarded.
WebSocket connections require an API key even for public data, so "only
execution holds credentials" has to become "the trading key lives only in
execution; the collector has its own read-scoped key."

**karshincheo/kalshi-trading.** The named modules exist. They are not a
foundation. The "forecast" feature is an Open-Meteo archive observation, so
forecast equals actual on the sample. Labels use `actual >= strike` for every
contract, which is wrong for brackets and for strict-less strikes. The
generated-code sandbox is not a boundary: it is an AST allowlist plus a
subprocess, and generated code can import, read holdout files, and write into
the project tree. The evaluator values open positions at zero, overwrites lots,
fills at mid and undercharges fees by roughly an order of magnitude. The paper
broker charges zero fees and does not settle. The walk-forward backtester
filters on a `_timestamp` field the snapshots do not have, so it sees no data.
The live client targets `trading-api.kalshi.com`, which returns 401, and parses
removed integer cent fields as `None`. Kelly's core fraction `(p-m)/(1-m)` is
correct; `kelly_full.expected_value` is not. The unauthenticated order route
bypasses risk. There is no kill switch.

**mifisher/kalshi-weather-bot.** The posture (demo-first, fail-closed rules,
signed exposure, reconcile-before-write, one rejection reason) is the part
worth keeping. The implementation is already stale against Kalshi. KXHIGH*
contracts, including Philadelphia, settle "according to The Weather Company"
(`https://weather.com/kalshi`) for target dates on or after 2026-08-14, not the
NWS Daily Climate Report the spec and this bot assume. The bot's rules regex
now rejects every live market, and it has no Philadelphia station (CLIPHL).
`strike_type: less` with cap 82 means "less than 82", not "82 or below"; the
bot's `LessThanOrEqual` is off by one. Long NO is marked as a liability, which
understates equity by about one dollar per contract. Reconciliation does not
paginate, does not diff the journal and does not halt. GTC orders are never
cancelled, including across a halt. The fee formula matches the general taker
schedule but hard-codes 0.07 and ignores maker fees; KXHIGH's `fee_multiplier`
is 1, so makers pay nothing. "Climatology" is the training base rate, about
0.25 by construction. The README's "skill but −3 to −4¢ after fees" is prose
without committed artifacts; a rerun was noisy and near zero. The order-book
parser still reads `orderbook.yes`/`no`; the live payload is
`orderbook_fp.yes_dollars`/`no_dollars`. Historical markets older than the
cutoff (around 2026-08-02 for `market_settled_ts`) are only on `/historical/*`.

**prediction-market-backtester.** Run directories, `results.json`, a coherence
check that recomputes metrics from the CSVs, a golden equity hash, a batch
checkpoint and a quality-gate shape are worth reimplementing. The engine is
not. Cash-at-risk is inverted (it caps upside; the tests assert the wrong
number). Limit price is ignored. There is no settlement and no buying-power
check. Same-bar fills are the default. Batch run directories collide. The
quality gate runs after nulls have already been dropped. Money is float. The
Kalshi loader requires `yes_price` and `count`, which Kalshi removed on
2026-03-12. The vendored indexer has no `/historical/*` and dedupes by ticker.

**Viprasol-Tech/kalshi-trading-bot.** RSA-PSS signing is correct, mypy strict
passes, and the strategy ABC plus a single submit choke point are the right
shape. The REST client is not functional: the base URL already ends in
`/trade-api/v2` and the client prepends it again, so every call 404s (checked
live). Models are integer cents; live `*_dollars` and `*_fp` parse to `None`
and the book parses to `{}`. `KALSHI_DRY_RUN` is never read; only `--live`
matters. The risk check ignores side, so a NO buy is treated as more YES, and
a market order has zero notional. The backtester fills at the order's own
limit. `secrets/` never contained a key. Nothing here is a dependency.

**pmxt.** The unified Series → Event → Market → Outcome idea, a venue field,
`source_metadata`, build-then-submit, a capability map and a `MatchRelation`
(identity, complement, subset, and so on) with a confidence are worth copying
as ideas. The package is not. The Python SDK spawns a Node sidecar and sends
the Kalshi private key in every HTTP body. Money is float. `buildOrder`
ignores `outcomeId`, so buy is always YES and sell is always NO. Prices are
rounded to integer cents. Position fields the schema does not have become
`NaN`. Balance uses `portfolio_value` as if it were cash plus positions.
Five- and fifteen-minute candles silently come back as one-minute candles.
`feature-status.csv` marks Kalshi `tested_partial`; the compliance matrix is a
static method scan. Cross-venue matching is a closed hosted service. The repo
root contains a committed hosted API key. Two copyright holders. Inactive
since 2026-07-18, with a Rust rewrite planned for 2027 or later.

**PydanticAI.** The spec's choice holds. Use `pydantic-ai-slim[anthropic,openai]>=2.53,<3`,
not the meta-package (about 99 packages, including the Logfire SDK, versus
about 28). Telemetry is off unless enabled, and once enabled `include_content`
defaults to true, so prompts would be exported; set it false. V2 has been
stable since 2026-06-23 and the project's own policy allows a V3 any time
after about 2026-09-23, which is why the pin is `<3`. It is not a dependency
until Phase 5. Application flow stays ordinary Python; `pydantic_graph` is a
transitive dependency of the agent loop and is not how this app is structured.
`httpx2` is Pydantic's httpx fork and will sit beside the `httpx` that
`kalshi-sdk` uses.

**Kalshi itself, checked against public GETs on 2026-10-02 (no credentials).**
Legacy integer cent fields are gone. Prices are `*_dollars` strings (4 decimal
places; the tick comes from `price_ranges`). Counts are `*_fp` strings.
`strike_type: greater` with floor 89 means the value is greater than 89.
`strike_type: less` with cap 82 means the value is less than 82. `between` is
inclusive on both ends. Series `KXHIGHPHIL` settles on The Weather Company.
`fee_type` is `quadratic` with `fee_multiplier` 1. Hosts that answer: 
`api.elections.kalshi.com` (SDK production default), `demo-api.kalshi.co`, and
`external-api.kalshi.com` (not in the SDK's known-host list unless unknown
hosts are allowed). `trading-api.kalshi.com` returns 401. Rate limits are
separate read and write token buckets; a 429 body is `{"error":"too many
requests"}` and currently has no `Retry-After`. Exchange sharding and per-shard
collateral are real and absent from the spec; weather was not in the published
shard table as of the 2026-09-03 doc, so record `exchange_index` and assume
shard 0 until told otherwise.

## Reuse matrix

`dependency` means a pinned package behind our types. `reimplement` means we
write it ourselves, using the other project as a design or a test vector.
`reference` means we read it and do not copy it. `reject` means do not depend
on it, do not vendor it, and do not treat it as a design.

| component | project | reuse method | license | reason | modifications |
| --- | --- | --- | --- | --- | --- |
| REST client, resources, response models (`AsyncKalshiClient`) | kalshi-sdk 17.1.0 | dependency (Phase 1) | MIT © Texas Coding | 116/117 OpenAPI 3.32.0 operations, Decimal wire types, mypy strict, large unit suite | Exact pin. `KalshiConfig.demo()` / `.production()` only. Never `from_env()`. Refuse `KALSHI_ALLOW_UNKNOWN_HOST`. `max_retries=0`. Wrapping transport for rate-limit headers and error `code`. Convert to domain types inside `exchange/kalshi/` |
| V2 order writes (`OrdersResource.*_v2`, required `client_order_id`) | kalshi-sdk | dependency, execution process only | MIT © Texas Coding | Current order API | Any outcome that is not a definite 4xx is unknown and is reconciled by `client_order_id`. Not called in Phase 0 or 1 |
| RSA-PSS signer (`kalshi.auth.KalshiAuth`) | kalshi-sdk | dependency | MIT © Texas Coding | Correct Kalshi signing | Read-scoped key in the collector. Trading key only in execution |
| WebSocket client and sequence tracker | kalshi-sdk | dependency (Phase 1) | MIT © Texas Coding | Reconnect, resubscribe, book gap to snapshot | Our own sequence checks for trade and lifecycle. `overflow=ERROR` if user streams are ever subscribed. Raw-frame tap for the recorder |
| Local order book (`OrderbookManager`) | kalshi-sdk | reimplement | MIT © Texas Coding | Live and replay must share one book on our types. SDK book is basic and tied to SDK models | Done in Phase 0 as `OrderBook`: YES-price scale, NO bids converted by complement, crossed-book check. Deltas land in Phase 1 |
| Decimal field types | kalshi-sdk | reimplement | MIT © Texas Coding | SDK accepts floats via `Decimal(str(x))` | Done. Floats and bools rejected. Price 4 dp, quantity 2 dp, money 6 dp |
| REST record/replay transports | kalshi-sdk | dependency, tests only, later | MIT © Texas Coding | Convenient REST fixtures | Not for order tests (bodies ignored, fixtures wrap). Our own recording format for market data |
| Retry classification and spec-drift tests | kalshi-sdk | reference | MIT © Texas Coding | Sound rules; their drift job is the right idea | Reimplement in our budgeter. Nightly diff scoped to fields we read |
| FIX engine, perps/Klear, DataFrame helpers | kalshi-sdk | reject (FIX is reference only) | MIT © Texas Coding | FIX is immature. Perps are out of scope. DataFrames belong to our storage layer | — |
| API reference (Markdown + AsyncAPI + OpenAPI narrative) | ammario/kalshi-docs | reference copy, CC0 | CC0 1.0 | Current docs, installed as `.agents/skills/kalshi-docs` at `4582a4209c74` | `npx skills add` (the spec's `npx add-skill` is the old name). `skills-lock.json` records a content hash, not the git SHA; the SHA is recorded here |
| Binary Kelly `(p-m)/(1-m)` | karshincheo/kalshi-trading | reimplement, later | MIT © Kar Shin Cheo | Core formula is right and tested there | Decimal, executable price, versioned fee, risk caps. Do not copy `expected_value` |
| Scenario log-wealth sizing | karshincheo/kalshi-trading | reimplement the idea, later | MIT © Kar Shin Cheo | Right shape for a bracket event | One scenario per mutually exclusive outcome. Their code assumes independence |
| Research-loop shape, `program.md`, chronological split, circuit-breaker rule list, `IBroker`, ticker heuristics, Open-Meteo cache shape, normal-CDF baseline | karshincheo/kalshi-trading | reference | MIT © Kar Shin Cheo | Useful skeletons around a broken evaluation | StrategySpec instead of generated Python. Embargo. No archive-as-forecast |
| Generated-code sandbox, evaluator, paper broker, walk-forward engine, trading engine, Kalshi client, temperature pipeline | karshincheo/kalshi-trading | reject | MIT © Kar Shin Cheo | Escapable sandbox, label leakage, wrong fees and fills, dead or stale exchange code | — |
| Fail-closed rules allowlist, signed economic-intent risk, reconcile-before-write, calibration gate with one rejection reason, NBS `txn` (not the max of hourly temps) | mifisher/kalshi-weather-bot | reimplement, later | MIT © Michael Fisher | The posture is right and the formulas are small | Settlement source by date. Strict-less strikes. Paginated reconcile that halts. Maker-aware versioned fees. Philadelphia / CLIPHL |
| NWS CLI resolver | mifisher/kalshi-weather-bot | reference | MIT © Michael Fisher | Useful for labels before 2026-08-14 and as a cross-check | Not the settlement source after that date |
| Portfolio marks, hard-coded 0.07 fee as production code, "climatology" base rate, the bot as a package | mifisher/kalshi-weather-bot | reject | MIT © Michael Fisher | Sign bug, no fee versioning, misnamed baseline, unpublished app pinned to a dead LLM path | Fee numbers may be reused as test vectors |
| Run schema, directory writer, coherence validator, golden equity hash, batch checkpoint, quality gate | prediction-market-backtester | reimplement | MIT © Quentin Piot | Best ideas in that repo, and they are small | Decimal, content hashes, atomic writes, settlement and collateral invariants |
| Loaders, bar builder, simulator, PnL ledger, calibration metric shape | prediction-market-backtester | reference | MIT © Quentin Piot | Concepts only | Full rewrite. Their Kalshi loader is on removed integer fields |
| Sharpe-on-bars, package dependency, scanner, category heuristic | prediction-market-backtester | reject | MIT © Quentin Piot | Wrong clock, float money, Kalshi complement skipped | — |
| Vendored indexer retry/backoff | Jon-Becker/prediction-market-analysis | reimplement, later | MIT © Jonathan Becker | Sensible tenacity policy | Honor `Retry-After` when Kalshi sends one. Per-bucket limits |
| Vendored Kalshi and Polymarket indexers | Jon-Becker/prediction-market-analysis | reject | MIT © Jonathan Becker | Stale against `/historical/*` and fixed-point fields | Our own recorder |
| Strategy ABC returning intents, single submit choke point, `RiskDecision` shape, Kelly formula, VWAP test cases, pydantic-settings shape, Dockerfile/CI/pre-commit layout, signature test idiom | Viprasol-Tech/kalshi-trading-bot | reference (reimplement the type shapes ourselves) | MIT © 2025 Viprasol Tech Private Limited | The shapes match the spec. The code does not work against Kalshi | Already reflected: `OrderIntent`, `RiskDecision`, `TradingMode` default `read_only`, gateway guard |
| REST client, models, WebSocket, backtester, example strategies, Rich-only logging | Viprasol-Tech/kalshi-trading-bot | reject | MIT © 2025 Viprasol Tech Private Limited | Doubled URL (live 404), stale cents schema, fills at the limit price | Keep only the YES/NO reciprocal book idea, already in `OrderBook` |
| Unified hierarchy, venue field, `source_metadata`, build-then-submit, capability map, `MatchRelation` | pmxt | reimplement the idea | MIT (idea only; two holders) | Cheap later if a second venue appears | Partially in the domain now: `Venue`, `OutcomeSide`, `OrderIntent` separate from `OrderRequest` |
| pmxt package, Kalshi adapter, hosted matching | pmxt | reject for V1 | MIT © pmxt.dev and © qoery.com; matching is a proprietary service | Sidecar credentials, float money, wrong Kalshi trading code | Revisit only for read-only cross-venue data, in a later phase, never with our key |
| `pydantic-ai-slim[anthropic,openai]>=2.53,<3` | pydantic-ai | dependency in Phase 5 | MIT © Pydantic Services Inc. | Typed outputs, tools, offline `TestModel` / `FunctionModel` | Import only inside `agents/`. No order tool. `ALLOW_MODEL_REQUESTS=False` in tests. `include_content=False` if tracing is ever on |
| `pydantic_evals` | pydantic-ai | optional dev dependency, Phase 5 | MIT © Pydantic Services Inc. | Offline prompt evals | Local only |
| `pydantic_graph`, MCP, durable-exec integrations | pydantic-ai | reference or reject | MIT | Graph is transitive. MCP and Temporal are unused infrastructure | App flow stays plain Python |
| Full `pydantic-ai` meta-package and the Logfire extra | pydantic-ai | reject | MIT; Logfire SaaS is separate | Pulls a telemetry SDK and a web stack we do not want by default | — |

## Decisions that follow

1. Phase 1 depends on `kalshi-sdk==17.1.0` and nothing else from this list.
2. No third-party source is copied into `vendor/`. If that ever changes, the
   copy lands there with its `LICENSE`, the upstream commit, and a notice in
   `THIRD_PARTY_NOTICES.md`.
3. Strategy code is a `StrategySpec` of predicates, not generated Python. The
   karshincheo sandbox is not a substitute.
4. Weather rules are versioned by the settlement source in the contract text.
   Do not assume NWS CLI for KXHIGH* after 2026-08-14.
5. One order book and one money type serve live, paper and backtest. Floats
   are rejected at the boundary.
