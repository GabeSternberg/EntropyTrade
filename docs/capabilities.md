# Capability inventory

Updated 2026-10-25 for R4. **Implemented** means code exists; **tested** means automated
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
| Accounting/paper / implemented, tested | `portfolio/{ledger,store}.py`, `execution/{paper,fees,series_fees}.py`; Decimal, SQLite | YES/NO netting, collateral, fills, fees, settlement and IOC/FOK behavior; R4 replay consumes depth and records partial/cancelled orders | No real account reconciliation, resting queue/competition model or multi-strategy allocation manager; real fee evidence remains required |
| Risk / implemented, tested | `risk/engine.py`, `domain/{risk,lifecycle,modes}.py` | Caps/loss/drawdown, stale/spread/edge, kill/HALT and human promotion; replay passes pending+filled event exposure; genuine reduce-only exits cannot flip | Correlated/series budgets and live cancel-on-halt remain missing; paper equity uses cost basis |
| Replay / chronological, fixture/integration tested | `backtest/replay.py`; existing Ledger/PaperBroker/RiskEngine | Decision → latency → execution; no future/cross-split/stale fills; shared snapshot capacity, reservations, YES/NO, expiry/close, settlement and three scenarios | Snapshot reset assumptions and queue/competition unknown; no real historical L2 evaluation; at-cost drawdown is not market-marked |
| Weather/data / generic builder, real REST verified | `data/{schema,sources,acquire,dataset,recording}.py`; PyArrow, existing SDK boundary | Configurable cities/dates/actual strikes, receipt versus uncertain clocks, immutable inputs and manifests; 36 real PHL/CHI contracts/six events and 1,060 candles | No certified September forecasts/historical rules/books; scalar settlement highs missing |
| Forecast archive / real capture/restart verified | `weather/{forecast,collection}.py`, `storage/forecast_archive.py`; HTTPX, R1 SQLite journal | Open-Meteo GFS seamless + NWS hourly, PHL/CHI: three real polls, 18 receipts/four vintages/648 hourly points; immutable raw/sighting provenance, first-seen clocks, failures/retries/limits; crash exit tested | Short capture, not a multi-day deployment; no archived changing model runs or source-matched scalar settlement feed. Product update/valid/receipt clocks never imply initialization |
| Features / implemented, causal/real-diagnostic tested | `features/{registry,pipeline}.py`; Parquet | Versions/units/dependencies, full-local-day maxima, distinct revisions, disagreement, causal prior-day bias, known deadline/calendar; DST, late revisions and corrected labels tested | Real sample has zero eligible forecast events; ensemble/observed-temperature canonical inputs supported but not currently captured |
| Models / fitted synthetic proof, real data-limited | `ml/{models,probability,evaluation,experiment,synthetic}.py`; scikit-learn, joblib | Empirical CDF, raw assumed-spread forecast, learned residual distribution, Ridge/boosting, monotone logistic/isotonic CDF calibration; date-blocked groups, event weighting, walk-forward, holdout off by default; distribution → strict/inclusive contracts | No empirical trained model, calibrated Kalshi comparison or validated edge; integer reported-Fahrenheit assumption, pooling/city dependence and minimum gates are not evidence of statistical power |
| Agents / configurable, mock protocol verified; live blocked | `agents/{team,pipeline,provider,evidence,outputs,validation,guard}.py`; PydanticAI | Typed hypotheses/specs, full criticism, bounded protected evidence, immutable audits; integrated R4 experiments and generic evidence projection | No research key or external LLM run; one isolated provider worker; semantic critique is not proof |
| Strategy interpreter / useful bounded DSL, tested | `strategies/interpret.py`, `domain/strategy.py` | Ticker/event/series/time/date, YES/NO, versioned inputs, feature/probability predicates, net edge/fees, entry price/spread/size, fixed contracts/dollars, position caps, settlement/predicate exits | Kelly, hedging, resting/post-only and duration exits explicitly unsupported; real execution still needs venue tick validation |
| Experiments/lineage / connected, synthetic end-to-end verified | `experiments/{data,engine,workflow,synthetic}.py`, existing Registry + local MLflow, Parquet | Prompt → candidates → R2 predictions → replay → metrics/ranking, config/code/data/model/spec hashes; protected event/date splits, walk-forward, bootstrap, trials and exact replay; non-weather fixture uses same engine | Real candidates insufficient; no multiple-testing correction or automatic final evaluator; no synthetic P&L ranking/promotion |
| Structural scan / prototype, fixture/stored tested | `strategies/scanner.py`, `exchange/related_strikes.py`, `weather/structure.py` | Price/fee/size checks for complement, threshold, exhaustive/duplicate relationships; stored-strike investigations | Verified relationship groups, continuous scanning and realistic multi-leg/capacity/leg-risk evaluation needed |
| Shadow/monitoring / prototype, simulated | `execution/shadow.py`, `monitoring/decay.py` | Intended vs paper prices and later prints, simple mean-difference degradation; downward lifecycle/size invariants tested | No continuous feed deployment, observed fills, model/calibration/feature drift or robust live-vs-backtest monitoring |
| UI/processes / integrated backend CLI; website next | `cli.py`, `experiments/workflow.py`, collectors and local registry view | `research-and-test` completes real-data insufficiency and full synthetic paths alongside existing data/weather/model/research commands | Minimal localhost research website is next after approval; no production dashboard or continuous shadow |
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
5. **Replay (R4 repaired):** chronology, split/close/expiry/age bounds, shared snapshot
   capacity, pending reservations and event exposure are tested. Snapshot replenishment,
   competition/queues and cost-basis drawdown remain explicit simulation limitations.
6. **Interpretation/fees (R4 repaired):** supported semantics and version/source references
   are enforced; unsupported fields fail explicitly. Net edge includes fee/uncertainty
   reserves. Real experiments require available/effective fee evidence; example coefficients
   are not proof of a historical schedule. Venue tick validation is future execution work.
7. **Statistics:** many correlated city/strike/rule attempts were made without a full search
   ledger. Binary rule-fire values in prediction files are not calibrated probabilities.
   Holdout rejection in one API is not a data-access security boundary for arbitrary code.

See [integrated experiment operations](experiments.md), [agent operations](agent-research.md), [weather/model operations](weather-modeling.md), [data commands and limitations](data-platform.md), [results](results.md) for measured evidence, [recovery audit](recovery-audit.md) for
fragmentation and acceptance review, and [roadmap](roadmap.md) for the repair sequence.
