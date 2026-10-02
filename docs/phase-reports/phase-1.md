---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 1 checkpoint

Date: 2026-10-02. Phase 1 is complete. Phase 2 has not been started.

This is the spec §40 step-4 report: what was built, the architecture that
matters, files, tests, reused code, weaknesses, decisions, and the exact plan
for Phase 2.

A copy of this file is in the repository at `docs/phase-reports/phase-1.md`.

## What was built

A read-only Kalshi adapter and a restart-safe recorder. `kalshi-sdk==17.1.0`
is a locked dependency. It is imported only inside `entropytrade.exchange.kalshi`.
`KalshiGateway` implements `ExchangeGateway` with `TradingMode.READ_ONLY` as a
constant. It constructs `KalshiConfig.demo()` or `.production()`, never
`from_env()`. It refuses to start if `KALSHI_ALLOW_UNKNOWN_HOST` is set. SDK
retries are off (`max_retries=0`). An observing HTTP transport keeps the status,
body, and headers of the last response, including a 429 of
`{"error": "too many requests"}` with no `Retry-After`.

SDK models are mapped to domain types at the boundary. Prices and quantities
stay `Decimal`. REST books come from `orderbook_fp` (`yes_dollars` /
`no_dollars`) into the Phase 0 `OrderBook`. A NO bid at 0.56 is a YES ask at
0.44. `greater` with floor 89 is still strict: 89 does not resolve YES.

Discovery covers series, events, and markets, including `GET /historical/*`
after `GET /historical/cutoff`. Each row records which origin it came from and
`exchange_index`. Rules text is stored with `rules_hash`. The settlement source
is parsed from the contract text. For KXHIGH*, when the text does not name a
source, the date in the ticker selects NWS Daily Climate Report before
2026-08-14 and The Weather Company on and after. That date is stored as
`settlement_target_date`. KXHIGH makers are not charged: `maker_pays` is true
only when the series `fee_type` string contains `maker`. The quadratic
multiplier is stored. Nothing hard-codes 0.07.

Streaming yields domain frames: book snapshot, book delta, trade, lifecycle.
Book gaps use the SDK `SequenceTracker`. Trade and lifecycle gaps use
`SequenceWatch`, because the SDK does not track those channels. A gap is a
health event and wipes the book. A duplicate sequence is not applied twice.
After a disconnect, deltas are refused until a snapshot, and that refusal does
not move the sequence watermark. `run_connections` treats each async iterator
as one socket lifetime and opens the next after `ConnectionError`.
`frame_from_wire` turns a Kalshi WebSocket JSON envelope into a domain frame.

`GET /account/limits` installs a `ReadBudget`. `GET /account/endpoint_costs`
replaces the flat default (10) with the schedule Kalshi returns. A read that
does not fit is refused before the coroutine is awaited, and the coroutine is
closed so it does not leak. Health reports connected or not, last message
time, last gap, stale tickers, missing sequence numbers, and lag.

`Recorder` is SQLite in WAL mode. `INSERT OR IGNORE` on natural keys makes a
restart a no-op for the same raw body, rule text, trade id, and
`(channel, sid, seq)` frame. Recorded frames replay through `parse_frame` and
the same `LocalBook` with no network.

`submit_order` and `cancel_order` call `require_order_submission` and raise
`OrderSubmissionForbiddenError`. Portfolio, order, fill, and settlement reads
raise `GatewayError` and do not touch the network. There is no trading key.
`.env.example` is still names only. `configs/live` is still unloaded.

## Acceptance

| Criterion | Result |
| --- | --- |
| Decimal / fixed-point money | Met. Mapping and book tests reject the float path already locked in Phase 0, and gateway fixtures assert `Decimal` prices and sizes. |
| Restart without duplicating rows | Met. Reopening the SQLite file and writing the same identities again leaves the counts unchanged. A later `captured_at` on the same rule text does not create a new rule version. |
| Detect a sequence gap | Met. A forward jump on the trade channel is a gap and the print is kept. A book gap from the SDK tracker wipes the book. A duplicate book sequence does not apply twice. |
| Reconnect after a dropped socket | Met in process. `run_connections` sees `ConnectionError`, marks the feed disconnected, and the next iterator's delta is stale until its snapshot. A live Kalshi socket was not opened. |
| Recorded data can be replayed | Met. `parse_frame` rebuilds a stored frame and `CollectorFeed` applies it. |
| Run for hours on demo or read-only production | Not met. No read-scoped key is available in this environment. The HTTP tests use `httpx.MockTransport` through the real SDK parsers. |

## Relevant architecture

```text
Kalshi REST / WS JSON
        |
        v
exchange/kalshi  (SDK import boundary)
  KalshiGateway, wire.frame_from_wire, BookSequenceWatch
        |
        v
domain frames + LocalBook + SequenceWatch + ReadBudget
        |
        v
Recorder (SQLite)  -->  parse_frame  -->  the same LocalBook
```

The SDK book manager is not used. Live ingest and replay share `LocalBook`.
The SDK sequence tracker is used for book channels only, and only on the live
path (`LiveIngest`). Replay uses `SequenceWatch` for every channel, including
books, so a recording does not need the SDK.

## Files

- `backend/src/entropytrade/domain/historical.py` — `ApiOrigin`, `HistoricalCutoff`
- `backend/src/entropytrade/domain/limits.py` — `EndpointCost`, `EndpointCostSchedule`
- `backend/src/entropytrade/domain/market.py` — `Series.exchange_index`, settlement basis and target date on `MarketRules`
- `backend/src/entropytrade/exchange/book.py` — `LocalBook`
- `backend/src/entropytrade/exchange/frames.py` — domain frames and `parse_frame`
- `backend/src/entropytrade/exchange/sequence.py` — `SequenceWatch`
- `backend/src/entropytrade/exchange/feed.py` — `CollectorFeed`, health, stale books
- `backend/src/entropytrade/exchange/budget.py` — `ReadBudget`
- `backend/src/entropytrade/exchange/settlement.py` — contract-text settlement parser
- `backend/src/entropytrade/exchange/kalshi/` — config, transport, mapping, gateway, stream, wire, session
- `backend/src/entropytrade/storage/recorder.py`
- `backend/tests/exchange/`

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 71 passed
(the Phase 0 suite plus the Phase 1 tests). The new tests cover:

- strike semantics, Weather Company text, historical origin, cutoff, decimals
- unknown-host refusal, local budget, endpoint-cost override, one-shot 429
- trade gap kept, reconnect stale-until-snapshot, SDK book gap and duplicate
- recorder restart idempotence and replay
- wire snapshot envelope and a dropped-socket resubscribe

No test contains a Kalshi key or a trading key. The RSA PEM in the HTTP tests
is generated in process and discarded.

## Reused code

`kalshi-sdk==17.1.0` (MIT, Texas Coding, commit `6bbc01270d11` as audited in
Phase 0): REST client, response models, and `SequenceTracker` for book
channels. Not reused: `from_env()`, SDK retries, `OrderbookManager`, the SDK
REST fixture transport (it ignores bodies). No trading bot and no
`prediction-market-backtester` code was vendored.

## Weaknesses

- The hours-long demo run and a real WebSocket handshake are unverified. No
  read-scoped key was present. `run_connections` and `frame_from_wire` are the
  code a live session would call; nothing in this checkout calls
  `KalshiWebSocket.connect`.
- `ReadBudget` does not yet reserve tokens for a future cancel path. There is
  no trading key, so the split cannot be exercised.
- Market list pagination stops at one page of 200. A full catalog crawl is not
  implemented.
- `configs/*.yaml` are still not parsed. No PyYAML dependency was added.
- Docker was not built. This environment has no `docker` binary.
- The SDK sequence tracker advances its watermark when it reports a gap. Our
  `SequenceWatch` does not, and waits for a snapshot. Live book ingest uses
  the SDK rule. Replay uses ours. They are intentionally different.

## Decisions

- Streaming is not a method on `ExchangeGateway`. A REST call and a socket
  have different lifetimes. The protocol gained no new methods in Phase 1.
  This differs from the wording in the Phase 0 plan ("extend the protocol").
  The surface is `MarketFrame`, `CollectorFeed`, and `LiveIngest`.
- Phase 1 does not add a trading key, and the collector cannot construct one.
- `KALSHI_ALLOW_UNKNOWN_HOST` is refused by our code before `KalshiConfig` is
  built. The SDK allows that variable; it does not fail known hosts when the
  variable is set.
- A non-4xx or a validation failure on an order response is still specified as
  unknown, reconciled by `client_order_id`. No submit code exists.
- `configs/live` stays unloaded. Default mode remains `read_only`.

## Exact plan for Phase 2

Phase 2 is accounting, a paper broker, and the risk engine. It does not submit
production orders and does not add a trading key to research code.

1. Account, positions, orders, fills, settlements, realized and unrealized
   P&L, and capital-at-risk, all on the Phase 0 domain types. Money stays
   `Decimal`. Fills stay monotone and cannot exceed the requested quantity.
2. `PaperBroker` fills against the Phase 1 `OrderBook`. It does not call
   `submit_order`. Partial fills only when the book has the size. No live
   order, including demo, unless a later step is explicitly a demo
   reconciliation client and live mode stays off.
3. Deterministic risk engine: bankroll cap, per-trade cap, per-event cap,
   total deployed cap, loss limit, drawdown limit, stale-data guard, minimum
   liquidity, maximum spread, kill switch. `RiskDecision` stays fail-closed.
   A strategy spec cannot set `risk_overrides_allowed` to anything but
   `"none"`. Tests must show a strategy cannot bypass the engine by calling
   the broker directly with an unapproved intent.
4. State reconciliation: local orders and fills versus a fixture that stands
   in for demo exchange state. Crash and restart must not double-count a fill.
   Unknown order outcomes, if any code path creates them, are reconciled by
   `client_order_id`. Do not add a submit implementation. If demo REST for
   portfolio is required, gate it the same way as Phase 1 reads and test it
   with fixtures when no key is present. Document that live demo
   reconciliation was not run.
5. Property tests for accounting invariants (cash, positions, fees, settlement).
   Do not hard-code 0.07. Fee identity stays `FeeModelRef` until a calculator
   exists; if Phase 2 needs a number, compute it from the series fee type and
   multiplier already stored, with KXHIGH makers at zero.
6. `make check` green before the phase is marked complete. Write
   `docs/phase-reports/phase-2.md` and the store copy. Update `STATUS.md`.
   Commit and push `cursor/phase-0-skeleton-e162` only.
