# Phase 4 exploration — consolidated recovery summary

R0 synthesis, 2026-10-24, baseline `de13acb`. This replaces hundreds of micro-phase entries
as the starting point for development. It does not certify their “complete” labels.
[Original reports](README.md) and all data/artifacts remain in place. Detailed, qualified
measurements are in [results](../results.md); implementation status is in
[capabilities](../capabilities.md).

## Data collected

The work progressed from synthetic Philadelphia labels/forecasts/books to stored public
Kalshi demo/production responses, IEM CLI products, Open-Meteo previous-run/archive/model
fields, NWS station/points/forecast/hourly snapshots and fee metadata. The main historical
window is August 23–October 1, 2026. Later city pulls and the 41-ticker scan greatly expanded
observations, but often requested the same B80.5 contract regardless of the listed buckets.
Not-found tickers were preserved; they are not a comprehensive inventory of those markets.

817 committed `data/public/` files (~88 MB) include raw bodies, failed response evidence,
SQLite study data and feature/prediction manifests. These remain valuable recovery inputs,
not a complete normalized research platform. Some manifests retain summaries without every
raw body. Do not rewrite those gaps as complete provenance.

## Provider compatibility and semantics

The code adapted to fixed-point Kalshi `*_dollars` / `*_fp` fields, historical/live endpoint
cutoffs, strict greater/less and inclusive between strikes, and explicit settlement-source
handling. Saved studied KXHIGH rules name The Weather Company. CLI/IEM is a cross-check
label for those dates, not authoritative settlement. The provider-specific Weather Company
JSON adapter is only verified on fixtures.

Open-Meteo daily previous-run requests and explicit `run` choices encountered errors.
Hourly previous_day1/previous_day2 fields were retained as an alternate experiment input.
Their historical availability clocks are conventions (`clock: rule`), not recorded
publication evidence. HRRR/model variants/ensembles and other variables were explored
selectively. Some were usable source values, some missing, and many never became aligned
features. Exact provider/model/version coverage needs source-level inventory in R1.

NWS points resolution produced one forecast snapshot with 14 periods and one hourly
snapshot with 156 periods. Many final reports counted strings, geometry and metadata in
those bodies. That preserved observations, but did not reconstruct historical vintages,
fit a model or create a point-in-time feature family.

## Historical execution coverage

A broad Philadelphia CLI-window request covered 240 settled contracts/66 suffixes and
230 stored candle files. Every current settled book was empty; one representative empty
body is retained and 239 manifest paths are null. Twelve real contemporary sized books
exist in the score's input, but are later than the historical labels. There are no eligible
sized books in the aligned study.

Print-based research explicitly separates optimistic assumed fills from base/conservative
no-fill cases. Later candle adapters preserve the absence of touch size. However, the
older `weather/public_dataset.py` maps candle volume into book size. That path remains
legacy lower-fidelity exploration and cannot substantiate executable performance.

## Features and strategies tested

Useful reusable primitives include parsing CLI MAXIMUM labels, forecast/label separation,
prior-label climatology, strict strike resolution, revision/containing-bracket selection,
as-of revision filtering, prediction/manifests and deterministic split refusal. Families
of exploratory functions cover forecast errors, model/ensemble gaps, observations, weather
variables, time, quote/candle/print summaries and related contracts. They are not a unified
feature registry or trained probability model pipeline.

Initial informational rules tested whether forecasts were inside/above/below the fixed
bracket or differed from its midpoint. Later rules used upward/downward revisions of at
least 2°F and selected containing stored brackets, with a 0.40 print threshold. Those
thresholds remained fixed within the recorded investigations. Repeating across cities
still creates selection pressure; it does not establish independent validation.

The 40-day Philadelphia CLI study recomputes MAE 2.9925°F, 39 probability rows, raw
Brier 0.05128205 and blend Brier 0.05280102. Its forecast never predicted YES inside
80–81. There are no eligible sized books or fills. The arithmetic blend is not learned
calibration. No fitted model exists despite a nominal minimum-history gate opening.

The initial gap rule's optimistic print-only walk-forward ended at 99.91 train and 99.99
validation from separate 100 starts. The 20/10/10 split skipped holdout. Later revision
artifacts regenerate 551 train/validation records and 91 fires, most without a containing
stored market, and all without executable bid/ask/net-edge evidence. Binary fire values
are not calibrated probability estimates. No strategy was promoted or validated profitable.

## Bugs, invariants and unresolved risks

Preserve Decimal/fixed-point accounting, UTC checks, payout/complement bounds, strict
strikes, revision-aware as-of filtering, human capital approvals, deterministic risk gates,
unknown-order classification, kill/HALT behavior and no-submit defaults. The meaningful
property/failure tests remain useful even though many field-specific tests add little.

The recovery source review also identified sessionless frame dedup, dropped unsequenced
frames, feed-wide timestamps used for book freshness, one-page discovery, replay fills
outside split/horizon and chronological/capacity limitations, caller-supplied event exposure,
gross-edge strategy interpretation and incomplete fee verification. These prevent strong
operational/backtest claims. [Capabilities](../capabilities.md) records the exact locations.

## Architectural lessons and next work

Keep the tested domain/SDK/ledger/risk/replay/registry seams. Consolidate source parsing
and validation by provider/family; cities and strikes belong in configuration. R0 shares
the ten duplicated NWS forecast/hourly metadata parsers while preserving public types,
notes and historical artifacts. Broader feature/exchange cleanup waits for a real consumer.

Experiments belong in run records, not development phases. A missing quote or negative
finding is an experiment result, not a reason for another software module/report. Prioritize
continuous read-only data capture and a generic reproducible dataset, then fitted models,
provider-backed research and a deterministic experiment engine. See the active
[R1–R8 roadmap](../roadmap.md). R0 stops for review; no next micro-phase is scheduled.
