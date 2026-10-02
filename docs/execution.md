# Execution

The execution engine is Phase 2 for paper and demo reconciliation, and Phase 9 for live
orders. Phase 0 defines the only door it has.

## Input and output

Input is an `ApprovedOrderIntent`: an `OrderIntent` plus a `RiskDecision` that approved a
positive quantity no larger than the request, decided at or after the intent. Output is an
`Order` and, later, `Fill`s.

`OrderRequest.from_approved` builds the wire request. `client_order_id` is a UUID minted
before the call and is the idempotency key. Resubmitting the same id must not create a
second order.

`PaperBroker.submit` accepts only an `ApprovedOrderIntent`. It walks the current
`OrderBook`, charges `trade_fee` on taker slices, and records the fill on a `Ledger`.
Good-till-canceled remainder rests as collateral. Fill-or-kill and immediate-or-cancel
cancel what they cannot take. The broker does not call `KalshiGateway.submit_order`.
A later book does not fill an order that is already resting; that matching loop is still
open. `run_shadow` fills the ledger only in `PAPER`. `SHADOW` records the price it
would have paid and compares it with the next recorded print. A missing print is a
gap. `LIVE` and `DEMO` raise before the strategy runs, even when the live flag is set.
`attempt_submit` calls an injected transport only in `DEMO`. Every other mode,
including `LIVE` with the flag set, raises first. The Kalshi gateway's own
`submit_order` still raises for every mode and is not wired to that transport. Reconciliation compares snapshots and adopts an `unknown` order only along a legal
transition, keyed by `client_order_id`.

## State machine

```text
created -> risk_approved -> submitting -> acknowledged -> resting -> partially_filled -> filled
                |               |              |            |              |
                v               v              v            v              v
            cancelled       rejected       cancel_pending / cancelled / unknown
```

`unknown` is the crash state: timeout, connection loss, or a response we could not parse
after the exchange may have accepted the order. The only exits are reconciliation against
the exchange (open orders, fills, the order looked up by `client_order_id`). Local state
is never assumed correct after a restart.

Terminal states have no outgoing transitions. Filled quantity never exceeds the request
and never decreases.

## Gateway

`ExchangeGateway` is the protocol in `entropytrade.exchange.gateway`. Reads cover exchange
status, API token-bucket limits, series, events, markets, books, trades, portfolio, open
orders, fills and settlements. `submit_order` and `cancel_order` call
`require_order_submission`, which raises `OrderSubmissionForbiddenError` unless the mode is
`demo` or `live`. `KalshiGateway` implements the reads and calls
`require_order_submission` on submit and cancel, which raises while the mode is
`read_only`. Portfolio, order, fill, and settlement reads raise `GatewayError`; they are
Phase 2. No method on this class sends an order.

Streaming is `LiveIngest` plus domain frames (`orderbook_snapshot`, `orderbook_delta`,
`trade`, `market_lifecycle_v2`), not a method on the protocol. Book gaps use the SDK
`SequenceTracker`. Trade and lifecycle gaps use `SequenceWatch`, because the SDK ignores
those channels. A gap is a health event. After a disconnect, deltas are refused until a
snapshot. `run_connections` is the resubscribe loop; it consumes frame iterators and does
not open a socket by itself.

## Rate limits

Kalshi meters reads and writes as separate token buckets, refilled continuously, with burst
capacity of about three seconds on the higher tiers. `GET /account/limits` and
`GET /account/endpoint_costs` are the source of the numbers, returned as `ApiLimits` and
`EndpointCostSchedule`. `ReadBudget` prices each read from that schedule (default cost
when a route is unlisted) and refuses the call before it is sent when the bucket cannot
pay. Priority, when orders exist, is cancel, then order state, then execution, then
market-data recovery, then research. A collector must not be able to spend the tokens
needed to cancel. That split is not enforced yet: Phase 1 has no trading key and no
cancel path.

`KalshiGateway` sets `max_retries=0` and wraps the HTTP transport. A 429 is one attempt.
The body `{"error": "too many requests"}` is kept, and `retry_after` stays unset when
Kalshi omits `Retry-After`.

## Sharding

Order entry can target an exchange shard (`exchange_index`). Collateral is per shard.
Phase 1 records the field. Phase 9 has to fund the shard a market lives on before sending
an order there. Weather markets are not in the shard table published as of 2026-09-03
(combos, crypto, commodities, and some sports), so they stay on shard 0 until Kalshi says
otherwise. The domain stores `exchange_index` on events and markets rather than guessing
from the ticker.

## Reconciliation

Before any write, and after every reconnect, gap, or `unknown` order: balance, positions,
resting orders, recent fills, settlements. Compare to the journal. Halt on unexplained
drift. Paginate; the API defaults to 100 rows. This is the weather bot's posture, not its
code: that bot never compared local state and never halted.
