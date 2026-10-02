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
`demo` or `live`. Phase 0 has no implementation that opens a socket. A fake in the tests
satisfies the protocol and demonstrates the refusal.

There is no streaming method yet. Phase 1 adds it on this protocol. The collector will use
the SDK's WebSocket client for books, with our own sequence checks on the trade and
lifecycle channels, because the SDK tracks sequence only for `orderbook_delta`,
`orderbook_snapshot` and `order_group_updates`.

## Rate limits

Kalshi meters reads and writes as separate token buckets, refilled continuously, with burst
capacity of about three seconds on the higher tiers. `GET /account/limits` and
`GET /account/endpoint_costs` are the source of the numbers, returned as `ApiLimits`.
The budgeter is Phase 1. Priority, when it exists, is cancel, then order state, then
execution, then market-data recovery, then research. A collector must not be able to spend
the tokens needed to cancel.

The SDK retries by default and hides rate-limit headers. Phase 1 will construct it with
`max_retries=0` and a wrapping transport so the budgeter sees the responses. 429s currently
carry no `Retry-After`.

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
