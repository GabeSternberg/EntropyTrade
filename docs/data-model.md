# Data model

Domain types live in `entropytrade.domain`. They are frozen pydantic models, reject unknown
fields, and refuse to exist in an invalid state. This page is the map; the invariants are
enforced in the types and tested.

## Money and time

| Quantity | Representation | Grid |
| --- | --- | --- |
| Price (dollars per contract) | `Decimal` | 4 dp, in `[0, 1]`. Order prices are strictly inside `(0, 1)` and must also sit on the market's `TickSchedule`. |
| Contract count | `Decimal` | 2 dp, non-negative. Fractional contracts exist on some markets; whole contracts are `"10.00"`. |
| Money (fees, cash, P&L) | `Decimal` | 6 dp, signed. `price × quantity` lands exactly on this grid. |
| Probability | `Decimal` | `[0, 1]`, no grid. Model output, not an exchange value. |

Floats and bools are rejected. Naive datetimes are rejected; aware datetimes are converted
to UTC. Nothing in the domain compares a timestamp that lacks a timezone.

Prices on orders and fills are YES-denominated, which is Kalshi's current convention: an
order at price `p` with outcome NO costs `1 - p` per contract. Buying YES and selling NO
are the same exposure, so the domain stores the outcome side plus `reduce_only` rather than
the legacy action/side pair.

## Identity

Client-generated UUIDs identify intents, orders (`client_order_id`), risk decisions and
runs. They are the idempotency key when a submit times out.

`content_hash` is `sha256:` over canonical JSON: sorted keys, scale-independent decimals,
UTC timestamps. `StrategySpec.spec_hash()` and `MarketRules.rules_hash` are content hashes.
The rules hash ignores `captured_at`, so recapturing the same text is the same version and
any text change is a new version.

## Markets and rules

`Series` carries `fee_type` and `fee_multiplier`. `Event` carries `mutually_exclusive`.
`Market` carries lifecycle status, strike, rules, tick schedule, and result once the status
is `determined` or later. A `finalized` market must have a result. A result on an `active`
market is rejected.

`Strike.resolves_yes` implements Kalshi's operators. For integer temperatures, `greater`
with floor 89 is "above 89", `less` with cap 82 is "below 82", and `between` is inclusive
on both ends. `functional`, `custom` and `structured` strikes are not evaluable from
floor/cap and must not be guessed.

`Contract` is `(venue, market ticker, outcome side)`.

## Books and trades

`OrderBook` is stored on one YES-price scale: bids are YES bids, asks are YES asks.
`OrderBook.from_yes_and_no_bids` converts Kalshi's native NO bids. Levels are strictly
ordered. A crossed or locked book is flagged `is_crossed` and is not a price a strategy
may take. `midpoint` is explicitly not an executable price; `best_price_to_buy` is.

`TradePrint` records the YES price, the taker's outcome side, the exchange time and the
time we received it.

## Orders

`OrderIntent` is what a strategy wants. `RiskDecision` approves a quantity no larger than
the intent, at a time no earlier than the decision. `ApprovedOrderIntent` is the only
object execution accepts. `OrderRequest` is what would be sent, keyed by `client_order_id`.

`Order` moves through `OrderState`. Terminal states (`filled`, `cancelled`, `rejected`)
have no exits. `unknown` (submit timeout, or a response we could not parse) returns only
by reconciliation. Filled quantity is monotone and cannot exceed the request. A `filled`
order is completely filled; a `partially_filled` order is strictly in between.

## Positions and settlement

A `Position` is netted per market: non-negative quantity of one side, cost basis at most
$1 per contract. `PortfolioSnapshot` rejects two open positions in the same market.

`settlement_payout` pays `value` per YES contract and `1 - value` per NO contract, so the
two sides of one quantity sum to that quantity in dollars. A `Settlement` record is
rejected when its revenue does not match that payout. YES results pay $1, NO results pay $0,
scalar results pay the published value.

## Point in time

`PointInTimeRecord` requires `published_at <= available_at <= ingested_at` when a publish
time is known. `Forecast` additionally requires `run_time <= available_at` and a validity
window. Newer forecast runs are new records, never overwrites.

`select_as_of(records, decision_time, key)` returns the latest record per key with
`available_at <= decision_time`. Adding records that became available later does not change
the result. This is the primitive Phase 3's replay engine must use; joins on date alone
are not allowed.

## Strategy, research, runs

`StrategySpec` is the agent's output. See [`strategy-spec.md`](strategy-spec.md).
`StrategyVersion` records lineage: version 1 has no parent, later versions must name one,
and a version cannot be its own parent.

`AgentResearchRun` is running, completed, failed, or cancelled. A completed run must carry
a `ResearchReport` for that run. A running run cannot.

`BacktestRun` is provenance only (hashes, fee model, fill scenario, fidelity, seed,
splits). It does not contain a P&L. Train, validation and holdout, when present, are
inside the run window, chronological, and non-overlapping. A holdout requires a train split.

`Deployment` in `live` mode cannot be approved or active without a human `approved_by`.
Paper deployments can be proposed with no approver. `CapitalEnvelope` is a bound the risk
engine enforces; a spec cannot raise it (`risk_overrides_allowed` is the literal `"none"`).

## Recorder

`entropytrade.storage.recorder.Recorder` is one SQLite file in WAL mode. Rows are inserted
with `INSERT OR IGNORE` on natural keys, so reopening the file after a restart does not
duplicate a trade, a rule version, a raw body, or a `(channel, sid, seq)` frame. Tables:

- `raw_payloads` — sha256 of the body, origin (`live` or `historical`), path, status, receive time
- `rule_versions` — `(market_ticker, rules_hash)`, origin, `exchange_index`, captured time
- `market_metadata` — version hash of the market with `captured_at` removed, origin, `exchange_index`
- `series_fees` — fee type, multiplier, whether the fee type charges makers, `exchange_index`
- `events` — version hash and `exchange_index`
- `trades` — `trade_id`, origin, receive time
- `frames` — book snapshots, book deltas, and lifecycle events
- `cutoff` — the single `GET /historical/cutoff` observation

`MarketRules.settlement_basis` and `settlement_target_date` record which source applies and
on which contract date. The hash of the rule text does not include `captured_at`, so a
second read of the same text is the same version.

## What is deliberately not here yet

No Parquet layout and no feature store. DuckDB/Parquet for analytical data is still the
planned store for the backtester (Phase 3). Account, order, and fill tables are Phase 2.
Raw data is append-only; `data/raw/` is gitignored.
