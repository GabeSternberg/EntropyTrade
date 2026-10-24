# EntropyTrade — current status

Updated 2026-10-24. R0 is preserved at `c7ad278` on `recovery/r0`.
R1 was developed on `recovery/r1`, with local commits only. No merge or push authorized.

## Objective and checkpoint

**R1 — reliable read-only recording and a generic point-in-time dataset builder — is
complete for review, with authenticated WebSocket verification blocked by credentials.**
R2 has not started. The goal remains a trustworthy research-to-shadow workflow, not trade
recommendations. [Roadmap](docs/roadmap.md) is the active development plan.

## What now works

- `entropytrade collect`: continuous read-only SDK-backed application with paginated
  discovery, metadata/rule snapshots, raw WS receipts, normalized books/trades/lifecycle,
  session identities, sequence/conflict detection, snapshot recovery, per-book freshness,
  bounded retries, clean shutdown, writer lock, disk budget and persisted JSON health.
- Explicit SQLite v1→v2 migration retains legacy frames/provenance gaps. Raw deliveries
  and deduplicated facts are distinct; repeated observations and genuine rule revisions
  survive restarts. Transactions use WAL/FULL synchronous writes.
- `entropytrade dataset`: configurable locations/series/dates/UTC schedule/sources produce
  versioned Parquet rows, weather evidence, manifests, code/input/artifact hashes, coverage
  and missing-data reports. It reads frozen public sources and live-mode collector records.
- Strict features exclude unknown/assumed clocks and future revisions. Historic candles
  stay separate context; only fresh sized books with known contract rules can qualify as
  executable evidence. Finalized Kalshi outcomes are separate labels.
- R0's domain, paper, risk, replay, registry and scripted agent foundations remain.
  See [capabilities](docs/capabilities.md) for tested versus operational status.

## Verification and actual data

- Final `make check`: Ruff lint/format clean, strict mypy clean (434 files),
  **528 tests passed in 123.66s**. All 503 R0 tests remain; 25 new cases cover
  recorder/collector/dataset behavior, including Hypothesis properties and crash recovery.
- Independent output builds have identical Parquet hashes; repeated frozen sample builds
  reproduce manifest/version/row hash. Artifact checksums and changed-document links pass.

Public production REST acquisition on October 24 retrieved **36 actual contracts across
six Philadelphia/Chicago events**, September 1–3, plus **1,060 candles**, with no acquisition
failures. All 36 rows have finalized Kalshi labels. Repeated frozen-source builds reproduce
the dataset/version and Parquet artifacts. **Zero** rows have certified historical forecast
features, historic rule snapshots or executable historical books. All **1,920** imported
legacy forecast observations retain uncertain availability and stay outside strict features.

The CLI replay demonstration retained 7 receipts/frames, then 14/14 after restart, one
unique trade and zero unclosed sessions. These are **synthetic wire messages**. Fake HTTP/
socket tests additionally verify reconnects, scope guards, durability, gaps and invalidation.
No real WebSocket handshake or multi-hour exchange session was run: no dedicated read-only
key is configured. No orders were submitted, cancelled or enabled.

## Setup and unresolved work

Run `uv sync --locked`, then `make check`. [Data platform guide](docs/data-platform.md)
contains exact collector, replay, dataset and inspection commands. A separate key with only
`read` scope is required for live WS verification, using `ENTROPYTRADE_READ_KEY_ID` and
`ENTROPYTRADE_READ_KEY_PATH` (PEM mode 600). Scope verification refuses write-capable keys.
Generic trading-key environment variables are not fallbacks. Key inventories are not recorded.

Kalshi SDK remains 17.1.0. PyArrow 19 is now an explicit analytical dependency (already
present through MLflow); no distributed services or order transport were added. The pinned
SDK boundary handles an absent unused liquidity field and historical filter incompatibility.
Ruff now checks the Python `data/` package as well as the rest of the backend.

Remaining: authenticated sustained collector verification; certified forecast vintages and
more independent events; historical universe/rule evidence and execution depth; the R0
replay chronology/capacity/fee and StrategySpec limitations. Fitted models, real agents,
automated experiment validation, continuous shadow operation and the workflow UI remain
later capabilities. Raw data, R0 research artifacts and historical Git history are preserved.

## Exact next action

Review R1. Configure a dedicated read key and complete the guide's sustained collection/
restart check when available. There is **not enough certified weather history for a
forecast-revision modeling/edge claim**. Recommended R2: obtain verified forecast vintages
or begin receipt-backed forward weather capture, implement the feature registry and temporal
model/artifact pipeline, then compare climatology/market/raw-forecast and regularized calibrated
baselines only on eligible independent events. Report insufficient data where appropriate.
Do not begin R2 without approval.
