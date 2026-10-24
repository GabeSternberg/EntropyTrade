# EntropyTrade — current status

Updated 2026-10-24. Audited baseline: `de13acb` (2026-10-03), a clean clone of `main`.
The original 507-test baseline was reproduced from a pristine exported tree.

## Objective and active milestone

Recover the existing project, then build a trustworthy research-to-shadow workflow.
**R0 recovery is complete and awaiting review. R1 is not started.**
[Roadmap](docs/roadmap.md) is the active development plan. Do not resume Phase 4.290.

## What exists

- Venue-neutral Decimal/UTC domain models, strike semantics, point-in-time selection,
  typed StrategySpecs and approval/lifecycle constraints.
- Read-only Kalshi SDK adapter, frame parsing, sequence/book state, rate-budget
  primitives, SQLite recording/replay. HTTP and reconnect tests use fakes.
- Ledger, fees, paper broker, deterministic risk/kill switches, reconciliation helpers,
  temporal replay and split primitives. Real-account reconciliation is unwired.
- Scripted research pipeline, restricted YES strategy interpreter, SQLite registry,
  local MLflow export, HTML registry/HALT endpoint, structural and shadow prototypes.
- Committed public market/weather bodies and reproducible descriptive studies.
  [Results](docs/results.md) separates measured findings from execution assumptions.

These are implemented/tested foundations, not an operational platform. See
[capabilities](docs/capabilities.md) for subsystem evidence and risks.

## What is missing

- Generic listed-contract dataset builder with verified vintages and fidelity labels.
- Real long-running read-only collector, session-safe recording and sustained feed evidence.
- Consolidated feature pipeline, fitted/calibrated models and temporal model evaluation.
- Configurable provider-backed research and general automated experiment/validation engine.
- Continuous paper/shadow operation and private workflow dashboard.
- Live submission is deliberately unwired and remains forbidden for R0–R7.

## R0 changes and preservation

Short entry docs replace the micro-phase notebook; thematic findings and a legacy index
preserve the research trail. Original reports, raw data, manifests, research notes and
Git history remain intact. Ten NWS metadata loaders share parsing/validation; public
results and historical notes remain compatible. Other fragmentation is classified in
[the audit appendix](docs/recovery-audit.md), not indiscriminately deleted.

## Checks and external dependencies

- Pristine `de13acb` baseline: Ruff lint/format clean, strict mypy clean, **507 tests passed**.
- Recovery `make check`: Ruff lint/format clean (421 files), strict mypy clean
  (422 source files), **503 tests passed in 172.11s**. Ten source-text assertions
  were replaced by six grouped behavior/failure cases; golden results and core
  accounting, risk, leakage and lifecycle invariants still pass. No skips.
- The sandbox needed network permission for async/local HTTP integration tests;
  restricted runs stalled. The successful suite uses fake exchange HTTP and loopback.
- CLI smoke check remains `read_only`; relative links and preservation checks passed.

Locked packages remain unchanged: Kalshi SDK 17.1.0, PydanticAI slim 2.53.0,
MLflow 2.22.5. No copied third-party implementation or new runtime dependency in R0.
No Kalshi or LLM credentials were configured in the managed environment. No exchange
orders, provider LLM calls, or fresh weather requests were made. Stored HTTP bodies are
historical external evidence, not fresh service verification. Read-only Kalshi credentials
are needed to verify a WebSocket session; trading credentials belong only in a future
isolated executor. Weather Company access/schema and true forecast publication clocks
still need verification. The stored fee coefficient is not externally established.

## Exact next action

Review the R0 commit and [R1 acceptance criteria](docs/roadmap.md#r1--generic-marketdata-platform-and-continuous-recording).
After approval, begin with recorder session identities, lossless unsequenced-frame storage,
per-market freshness, paginated discovery and a runnable read-only service. Pair that with
a generic dataset command using actual listed contracts. Do not begin R1 before review.
