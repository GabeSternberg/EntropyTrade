# Capability inventory

Updated 2026-10-25 for R3. **Implemented** means code exists; **tested** means automated
evidence; **externally verified** requires actual source/service evidence; **operational**
requires a running, recoverable workflow. Weather polling and public market acquisition
have short real-session evidence. Models have a complete synthetic proof, while empirical
fitting remains data-blocked. Authenticated Kalshi WS remains unverified without a read key.
Paths below are relative to `backend/src/entropytrade/`.

| Subsystem / status | Implementation and technology | Coverage, timing and verification | Outstanding work |
| --- | --- | --- | --- |
| Domain / implemented, tested | `domain/`; Pydantic, Decimal, UTC | Synthetic/property tests cover exact grids, complement, payout, strict/inclusive strikes, order states, approval constraints, as-of revision filtering | These types cannot verify a provider's claimed availability time |
| Discovery / real REST verified, tested | `exchange/kalshi/{gateway,mapping,recorded,transport}.py`; SDK 17.1.0 | Cursor pagination, actual event contracts, raw receipt capture; 36 real PHL/CHI contracts retrieved in R1 | Pinned SDK compatibility model accepts absent unused liquidity as None; its `_list` seam must be rechecked on SDK upgrade; retrospective universe completeness is unknown |
| Stream/book / runnable, simulated integration | `collector/service.py`, `exchange/kalshi/socket.py`, existing frame/feed/book boundary | SDK connection/auth + raw tap, selected book/trade subscriptions, global lifecycle, session recovery, gap/conflict checks and per-market freshness; fake socket/HTTP tested | No authenticated handshake or hours-long exchange session: dedicated read key missing. Unsequenced-channel completeness cannot be guaranteed |
| Recording / implemented, restart/crash tested | `storage/recorder.py`; SQLite WAL/FULL, explicit schema v2 | Raw receipt/body separation, semantic frame identities scoped by session, trade IDs, atomic integrity effects, metadata→HTTP provenance, health, legacy-preserving migration, v1/abrupt-exit tests | Disk budget stops rather than deleting/rotating data. Archive closed databases manually; legacy lost provenance is not reconstructable |
| Rules / implemented, recorded-data tests | `exchange/settlement.py`, `domain/market.py`; Kalshi rules and strikes | Historical KXHIGH examples name Weather Company; schedule fallback and strict strike handling tested | Fallback is not proof for arbitrary markets; persist complete versioned semantics and invalidation; Weather Company parser is a hand-shaped fixture schema |
| Accounting/paper / implemented, tested | `portfolio/{ledger,store}.py`, `execution/{paper,fees,series_fees}.py`; Decimal, SQLite | YES/NO netting, collateral, fills, settlement, IOC/FOK/post-only behavior and fee properties use fixtures | No real account reconciliation or generic multi-strategy allocation/correlation manager; resting fills/queue competition and shared book-depth consumption are not operationally modeled; fee coefficient is supplied |
| Risk / implemented, tested | `risk/engine.py`, `domain/{risk,lifecycle,modes}.py` | Caps, loss/drawdown, liquidity, stale/spread, optional edge/model/reconcile/order-rate checks; kill/HALT and human promotion tests | Caller supplies event exposure/order counts; replay passes event exposure zero. Correlated/series budgets and cancel-on-halt are missing |
| Replay / implemented, tested on fixtures and stored studies | `backtest/replay.py`; `DecisionView`, PaperBroker | As-of filtering and revised-data leakage tests, latency touch clamp, settlement, holdout refusal; study runs also exercise it | No general artifact/coherence writer or full experiment validation; fill/split chronology and capacity need repair before inference |
| Weather/data / generic builder, real REST verified | `data/{schema,sources,acquire,dataset,recording}.py`; PyArrow, existing SDK boundary | Configurable cities/dates/actual strikes, receipt versus uncertain clocks, immutable inputs and manifests; 36 real PHL/CHI contracts/six events and 1,060 candles | No certified September forecasts/historical rules/books; scalar settlement highs missing |
| Forecast archive / real capture/restart verified | `weather/{forecast,collection}.py`, `storage/forecast_archive.py`; HTTPX, R1 SQLite journal | Open-Meteo GFS seamless + NWS hourly, PHL/CHI: three real polls, 18 receipts/four vintages/648 hourly points; immutable raw/sighting provenance, first-seen clocks, failures/retries/limits; crash exit tested | Short capture, not a multi-day deployment; no archived changing model runs or source-matched scalar settlement feed. Product update/valid/receipt clocks never imply initialization |
| Features / implemented, causal/real-diagnostic tested | `features/{registry,pipeline}.py`; Parquet | Versions/units/dependencies, full-local-day maxima, distinct revisions, disagreement, causal prior-day bias, known deadline/calendar; DST, late revisions and corrected labels tested | Real sample has zero eligible forecast events; ensemble/observed-temperature canonical inputs supported but not currently captured |
| Models / fitted synthetic proof, real data-limited | `ml/{models,probability,evaluation,experiment,synthetic}.py`; scikit-learn, joblib | Empirical CDF, raw assumed-spread forecast, learned residual distribution, Ridge/boosting, monotone logistic/isotonic CDF calibration; date-blocked groups, event weighting, walk-forward, holdout off by default; distribution → strict/inclusive contracts | No empirical trained model, calibrated Kalshi comparison or validated edge; integer reported-Fahrenheit assumption, pooling/city dependence and minimum gates are not evidence of statistical power |
| Agents / provider-configurable, mock protocol verified; live blocked | `agents/{team,pipeline,provider,evidence,outputs,validation,guard}.py`; PydanticAI | Four typed roles and deterministic analyst; multiple hypotheses/full specs, bounded actual R1/R2 evidence projections, protected dates/outcomes, source/model/feature/universe gates; OpenAI wire mock and missing-key/failure tests | No dedicated research key: no actual external LLM run. Standalone worker required for process-wide framework guard; semantic critique is not proof. R4 experiments are not run |
| Strategy interpreter / narrow tested subset | `strategies/interpret.py`; typed StrategySpec | Informational, fixed contracts, immediate YES entries, probability predicates; text must say hold to settlement | Not a complete DSL: gross probability-minus-ask check ignores costs, some spec fields/exit predicates are not enforced; NO/other sizing/exits missing |
| Experiments/lineage / modeling workflow connected, strategy engine partial | `strategy_registry/{store,experiments}.py`, `ml/experiment.py`; existing SQLite + local MLflow | Modeling runs/model hashes/prediction IDs, feature/data/code/runtime lineage, train ranges, checksums, idempotent registration and repeatable fits tested; existing strategy lineage retained | R3 adds immutable research-run/tool/spec/gate lineage, idempotency and indexed normalized search counts; no broad experiment engine or statistical selection correction |
| Structural scan / prototype, fixture/stored tested | `strategies/scanner.py`, `exchange/related_strikes.py`, `weather/structure.py` | Price/fee/size checks for complement, threshold, exhaustive/duplicate relationships; stored-strike investigations | Verified relationship groups, continuous scanning and realistic multi-leg/capacity/leg-risk evaluation needed |
| Shadow/monitoring / prototype, simulated | `execution/shadow.py`, `monitoring/decay.py` | Intended vs paper prices and later prints, simple mean-difference degradation; downward lifecycle/size invariants tested | No continuous feed deployment, observed fills, model/calibration/feature drift or robust live-vs-backtest monitoring |
| UI/processes / data/weather/model CLI runnable, dashboard pending | `cli.py`, `collector/`, `weather/collection.py`, `strategy_registry/dashboard.py` | Collector, weather polling/export, acquisition/dataset, feature/model and explicitly synthetic demo commands; local registry view retained | Compose/frontend remain placeholders; no research API or React workflow UI |
| Execution / intentionally blocked | `execution/submit_gate.py`, `exchange/kalshi/gateway.py` | Mock submit outcome classifier; all live attempts refused, gateway refuses submits/cancels | No live transport; account methods raise. Keep disabled through research recovery and R8 review |

## Correctness risks that gate future claims

1. **Availability:** `weather/public_dataset.py` and revision adapters derive clocks from
   valid hours or fixed midnight conventions; some ingested timestamps are also assigned.
   `available_at <= decision_time` tests are necessary but cannot validate these assumptions.
   Stored NWS metadata strings are not a historical vintage archive.
2. **Execution fidelity:** early `public_dataset._books` maps candle volume to quantity.
   Later `exchange/cli_window.py` correctly leaves touch size absent. Do not route the
   early study into a book-fidelity experiment or report its results as executable returns.
3. **Recording (R1 repaired):** session-aware identities, unsequenced receipts, conflicting
   payloads, repeated HTTP receipts and metadata provenance are retained. Legacy gaps remain
   unknown. Network outage intervals and unsequenced completeness cannot be retroactively fixed.
4. **Freshness (R1 repaired):** books retain per-market update times, expire independently,
   and invalidate on integrity/lifecycle changes. Live behavior still needs authenticated verification.
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

See [agent operations](agent-research.md), [weather/model operations](weather-modeling.md), [data commands and limitations](data-platform.md), [results](results.md) for measured evidence, [recovery audit](recovery-audit.md) for
fragmentation and acceptance review, and [roadmap](roadmap.md) for the repair sequence.
