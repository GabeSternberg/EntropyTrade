# Capability inventory

Audited 2026-10-24 against `de13acb` and the R0 changes. **Implemented** means code exists;
**tested** means automated evidence; **externally verified** requires actual source/service
evidence; **operational** requires a running, recoverable workflow. None of the major
end-to-end services is verified operational. Tests and historical reports alone do not
establish that status. Paths below are relative to `backend/src/entropytrade/`.

| Subsystem / status | Implementation and technology | Coverage, timing and verification | Outstanding work |
| --- | --- | --- | --- |
| Domain / implemented, tested | `domain/`; Pydantic, Decimal, UTC | Synthetic/property tests cover exact grids, complement, payout, strict/inclusive strikes, order states, approval constraints, as-of revision filtering | These types cannot verify a provider's claimed availability time |
| Discovery / implemented, fake-HTTP tested | `exchange/kalshi/{gateway,mapping,config,transport}.py`; `kalshi-sdk==17.1.0` | REST series/event/market/book/trade/cutoff conversion; stored public GETs provide historical API examples | Market/trade lists read one page (limit 200); historical coverage and current API drift need real verification |
| Stream/book / implemented, simulated | `exchange/{feed,book,sequence,frames}.py`, `exchange/kalshi/{wire,stream,session}.py`; SDK sequence tracker | Snapshot/delta/trade/lifecycle parsing, gap detection, stale state and fake reconnect tests | `run_connections` consumes supplied iterators; no socket-opening service or multi-hour session evidence; per-market freshness risk |
| Recording / implemented, local tests | `storage/recorder.py`; SQLite WAL | Raw HTTP, rule/metadata versions, series fees, trades, frames and cutoff; reopen/dedup tested | Frame session collisions and unsequenced-frame loss; raw dedup loses repeated receipt context; no durable collector orchestration |
| Rules / implemented, recorded-data tests | `exchange/settlement.py`, `domain/market.py`; Kalshi rules and strikes | Historical KXHIGH examples name Weather Company; schedule fallback and strict strike handling tested | Fallback is not proof for arbitrary markets; persist complete versioned semantics and invalidation; Weather Company parser is a hand-shaped fixture schema |
| Accounting/paper / implemented, tested | `portfolio/{ledger,store}.py`, `execution/{paper,fees,series_fees}.py`; Decimal, SQLite | YES/NO netting, collateral, fills, settlement, IOC/FOK/post-only behavior and fee properties use fixtures | No real account reconciliation or generic multi-strategy allocation/correlation manager; resting fills/queue competition and shared book-depth consumption are not operationally modeled; fee coefficient is supplied |
| Risk / implemented, tested | `risk/engine.py`, `domain/{risk,lifecycle,modes}.py` | Caps, loss/drawdown, liquidity, stale/spread, optional edge/model/reconcile/order-rate checks; kill/HALT and human promotion tests | Caller supplies event exposure/order counts; replay passes event exposure zero. Correlated/series budgets and cancel-on-halt are missing |
| Replay / implemented, tested on fixtures and stored studies | `backtest/replay.py`; `DecisionView`, PaperBroker | As-of filtering and revised-data leakage tests, latency touch clamp, settlement, holdout refusal; study runs also exercise it | No general artifact/coherence writer or full experiment validation; fill/split chronology and capacity need repair before inference |
| Weather/data / implemented, stored-body verified | `weather/{recorded,cli_observations,settlement_score,public_dataset,revision_bracket,...}.py`; Kalshi/IEM/NWS/Open-Meteo | Mainly 2026-08-23–10-01 city windows; metadata manifests and local recomputation; NWS is a single later snapshot | Availability conventions are not verified publication vintages; settlement-source mismatch, narrow strike coverage, fragmented adapters; no generic ingestion command |
| Features / placeholder plus scattered helpers | `features/__init__.py`, `weather/`, `weather/provenance.py`; committed JSON manifests | Forecast/revision/model-gap/weather-variable summaries and hashes exist; many fields explicitly excluded from decision joins | No registered feature families, versioned transform pipeline or generic point-in-time dataset builder; unknown clocks must stay unknown |
| Models / baselines only | `ml/__init__.py`, `weather/{baseline,probability}.py` | Prior-label hit rate, binary forecast indicator, midpoint and arithmetic blend; MAE/Brier tests and stored samples | No fitted statistical/ML model, learned calibration, temporal fitting or model artifact registry. scikit-learn is merely an MLflow dependency |
| Agents / scripted scaffold, tested | `agents/{team,pipeline,fixture,deps,guard}.py`; PydanticAI TestModel | Four typed roles, fixture specs, critic/compiler rejection; no holdout window or order tools; provider requests blocked at import/run | No real provider configuration or research, evidence retrieval, distinct prompt-driven hypotheses; critic receives spec IDs rather than full specs |
| Strategy interpreter / narrow tested subset | `strategies/interpret.py`; typed StrategySpec | Informational, fixed contracts, immediate YES entries, probability predicates; text must say hold to settlement | Not a complete DSL: gross probability-minus-ask check ignores costs, some spec fields/exit predicates are not enforced; NO/other sizing/exits missing |
| Experiments/lineage / partial, local tested | `strategy_registry/{store,experiments}.py`, `domain/runs.py`; SQLite, MLflow | Immutable spec versions/lifecycle, verdicts and one backtest summary per spec; local MLflow parameter export tested | No general repeated-search accounting, model/feature/run lineage, uncertainty intervals, minimum independent events or protected final evaluator |
| Structural scan / prototype, fixture/stored tested | `strategies/scanner.py`, `exchange/related_strikes.py`, `weather/structure.py` | Price/fee/size checks for complement, threshold, exhaustive/duplicate relationships; stored-strike investigations | Verified relationship groups, continuous scanning and realistic multi-leg/capacity/leg-risk evaluation needed |
| Shadow/monitoring / prototype, simulated | `execution/shadow.py`, `monitoring/decay.py` | Intended vs paper prices and later prints, simple mean-difference degradation; downward lifecycle/size invariants tested | No continuous feed deployment, observed fills, model/calibration/feature drift or robust live-vs-backtest monitoring |
| UI/processes / placeholders plus local registry view | `strategy_registry/dashboard.py`, `cli.py`, `frontend/src/`, root Compose | HTML view and optional HALT POST tested; CLI prints version; Compose exits | No FastAPI research API or React workflow UI. HALT stops new intents, not resting orders |
| Execution / intentionally blocked | `execution/submit_gate.py`, `exchange/kalshi/gateway.py` | Mock submit outcome classifier; all live attempts refused, gateway refuses submits/cancels | No live transport; account methods raise. Keep disabled through research recovery and R8 review |

## Correctness risks that gate future claims

1. **Availability:** `weather/public_dataset.py` and revision adapters derive clocks from
   valid hours or fixed midnight conventions; some ingested timestamps are also assigned.
   `available_at <= decision_time` tests are necessary but cannot validate these assumptions.
   Stored NWS metadata strings are not a historical vintage archive.
2. **Execution fidelity:** early `public_dataset._books` maps candle volume to quantity.
   Later `exchange/cli_window.py` correctly leaves touch size absent. Do not route the
   early study into a book-fidelity experiment or report its results as executable returns.
3. **Recording:** frame primary key `(channel, sid, seq)` omits connection/session identity;
   `save_frame` drops `seq=None`. `save_raw` keys only by body hash. These are not sufficient
   for lossless restart-safe collection across sessions and repeated identical responses.
4. **Freshness:** `CollectorFeed.book` stamps any retrieved book with the last message
   time across the feed, so activity elsewhere can make an old book appear fresh.
5. **Replay:** `_book_at` chooses the first later book without an age/split bound. A fill
   can reach beyond the split. Future fills are booked inside an earlier decision loop;
   displayed capacity is reusable and `event_deployed=ZERO`. Touch clamping alone does
   not make the simulator conservative. Repair chronology/capacity before broad experiments.
6. **Interpretation/fees:** the compiler accepts some fields it never enforces, uses gross
   edge and chooses the maximum probability feature. Historical coefficient examples 0/0.02
   are scenarios, not verified fees; a later series snapshot does not prove the historical
   effective schedule. Reject unsupported semantics explicitly in R4.
7. **Statistics:** many correlated city/strike/rule attempts were made without a full search
   ledger. Binary rule-fire values in prediction files are not calibrated probabilities.
   Holdout rejection in one API is not a data-access security boundary for arbitrary code.

See [results](results.md) for measured evidence, [recovery audit](recovery-audit.md) for
fragmentation and acceptance review, and [roadmap](roadmap.md) for the repair sequence.
