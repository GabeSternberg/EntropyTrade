# R0 audit appendix

Audit date: 2026-10-24. Read alongside [capabilities](capabilities.md) and [results](results.md).
This appendix is an investigation aid, not the active roadmap. Baseline `de13acb` is
unchanged upstream main at the time of cloning; R0 uses branch `recovery/r0`.

## Acceptance review against historical claims

| Historical claim | Current source/test evidence | Recovery conclusion |
| --- | --- | --- |
| Phase 1 recorder complete | SDK REST boundary and fake frames/reconnect; CLI only prints; session accepts iterators | Useful primitives; hours-long authenticated recorder acceptance not met |
| Phase 2 account/risk complete | Ledger, broker, risk and supplied-snapshot reconciliation tests; gateway account reads raise | Local foundation; exchange reconciliation/crash recovery not demonstrated |
| Phase 3 backtester complete | As-of selection and replay; provenance types; no general atomic run/coherence writer | Partial; chronology, fill split bounds, shared depth and event exposure gate inference |
| Phase 4 models complete | Binary indicator, prior hit rate, arithmetic blend; ml package docstring only | Original fitted-model/baseline comparison acceptance not met |
| Phase 5 agent research complete | TestModel outputs scripted; model parameter typed TestModel; provider calls blocked | Orchestration scaffold, no provider-backed research |
| Phase 6 dashboard/lineage complete | SQLite specs and summaries, local MLflow parameter export, HTML/HALT handler | Useful local components; no workflow dashboard or full model/dataset/run lineage |
| Phases 7–8 scan/shadow complete | Fixture/stored-book scans and comparisons against later prints | Prototypes; continuous real-market validation not demonstrated |
| Phases 9–10 execution/decay complete | Mock demo outcome gate; live refused; mean print-vs-fill difference and downward states | Safety prototypes; neither live execution nor full drift monitoring |

## Verification method and limits

Read the original spec, architecture, old status and reuse audit before targeted specialist
docs. Reviewed the major subsystem source and tests, recent Git history and source manifests.
Selected reports support specific data/strategy/clock questions; the hundreds of reports
were not read in sequence. Reran stored Philadelphia scores, scan summary, prediction
counts and manifest validation. No fresh external market/weather/provider session was run.
No credentials were configured by the managed environment. Original tests use fake HTTP,
synthetic streams and committed public bodies; no separately configured live integration
suite or multi-hour service evidence was found. Reuse choices were checked against the
current lock/import boundaries; upstream repositories/licenses were not re-audited in R0.
No significant new dependency or functionality is introduced here.

## Fragmentation decisions

- **Meaningful reusable functionality:** retain domain/SDK/book/ledger/risk/replay/registry
  seams and source parsers that preserve real semantics and provenance. Fix documented
  correctness risks with their consuming capabilities rather than a broad rewrite.
- **Duplicate parsing:** ten forecast/hourly generatedAt/updateTime/validTimes/generator/
  units modules repeated JSON/property validation. R0 replaces that duplication with
  `weather/nws_metadata.py`. Public dataclasses/loaders and exact legacy note text remain.
  Ten source-spelling assertions were replaced by six grouped behavioral cases exercising
  both source documents, all five fields, missing/malformed inputs, source isolation,
  manifest/source rejection and a socket tripwire. Existing recorded-result tests remain.
- **Narrow helpers:** NWS per-field summaries, exchange bid/ask/volume/candle summaries
  and city study wrappers belong in coherent source/feature families when R1/R2 supplies
  consumers. Do not extend the legacy per-field pattern or route it into new runtime code.
- **Obsolete exploration candidate:** early candle-sized `public_dataset.py` is superseded
  for execution-fidelity claims, but has study consumers and reproducibility value. Retain
  it, label limitations, and exclude it from the future certified dataset/backtest route.
- **No blanket deletions:** no obscure helper was proven safely disposable solely from
  lack of a production caller. All source bodies, reports, manifests and experiment artifacts
  remain; historical status/README snapshots have adjusted relative links.

## Verification and preservation results

Baseline `de13acb` was exported to a separate pristine directory and checked with the
same locked virtual environment: Ruff lint/format clean, strict mypy clean (420 source
files), **507 pytest tests passed in 173.87s**. The initial restricted-sandbox async
gateway test stalled; it passed with network permission, which also permits the local
HTTP registry integration tests. No test was skipped or changed to conceal that issue.

Recovery `make check`: Ruff lint/format clean (421 files), strict mypy clean
(422 source files), **503 tests passed in 172.11s**. The count is 507 minus ten
source-spelling tests plus six grouped behavior/failure cases. All other existing tests,
including property, accounting, risk, lifecycle, leakage, public-study and note-compatibility
checks, passed without skips. The successful run used network permission for async and
loopback integration support; no live exchange/provider verification is implied.

A byte comparison against the pristine baseline confirmed **1,097** existing files in
`data/`, `research/`, `docs/research/` and `docs/phase-reports/` unchanged. Original
`project-spec.md`, dependency declarations/lock and third-party notices are unchanged.
All relative links in the 11 new/updated entry, audit and archive documents resolved.
The version CLI still reports default `read_only`. No production submission was added.

## Weather/exchange module reference inventory

Generated using Python AST `Import`/`ImportFrom` edges across `backend/src` and
`backend/tests`, after the R0 parser consolidation. Category is a family-level review,
not a deletion instruction. `S/T` counts distinct direct source/test importers; S does
not imply operational runtime use (a note renderer is source too). Tests may inspect file
paths dynamically; zero T is not proof of absent testing. Legacy report references are
preserved in the indexed report tree. Every listed module is retained.

| Module (under entropytrade/) | Classification | S/T | Direct source callers |
| --- | --- | --- | --- |
| `exchange/ask_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/bid_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/book.py` | reusable | 1/0 | `exchange/feed` |
| `exchange/book_imbalance.py` | narrow stored-data summary | 0/1 | — |
| `exchange/budget.py` | reusable | 1/0 | `exchange/kalshi/gateway` |
| `exchange/candle_activity.py` | narrow stored-data summary | 0/1 | — |
| `exchange/candle_change.py` | narrow stored-data summary | 0/1 | — |
| `exchange/candle_price.py` | narrow stored-data summary | 2/1 | `exchange/change_values`, `exchange/close_values` |
| `exchange/candle_quotes.py` | narrow stored-data summary | 0/1 | — |
| `exchange/candle_spread.py` | narrow stored-data summary | 5/1 | `exchange/ask_values`, `exchange/bid_values`, `exchange/spread_values`, `exchange/unit_asks`, `exchange/zero_bids` |
| `exchange/change_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/cli_window.py` | reusable | 1/1 | `weather/tape_score` |
| `exchange/close_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/feed.py` | reusable | 1/2 | `exchange/kalshi/stream` |
| `exchange/frames.py` | reusable | 6/3 | `exchange/feed`, `exchange/kalshi/session`, `exchange/kalshi/stream`, `exchange/kalshi/wire`, `storage/recorder`, `strategies/scanner` |
| `exchange/gateway.py` | reusable | 5/3 | `exchange/kalshi/config`, `exchange/kalshi/gateway`, `exchange/kalshi/mapping`, `exchange/kalshi/wire`, `execution/submit_gate` |
| `exchange/historical_trades.py` | reusable | 8/2 | `weather/austin_rules`, `weather/before_close`, `weather/before_occurrence`, `weather/chicago_rules`, `weather/dallas_rules`, `weather/kxhigh_scan`, `weather/newyork_rules`, `weather/oklahomacity_rules` |
| `exchange/interest_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/public_tape.py` | reusable | 3/2 | `exchange/cli_window`, `weather/settlement_score`, `weather/structure` |
| `exchange/related_strikes.py` | reusable | 0/1 | — |
| `exchange/sequence.py` | reusable | 2/1 | `exchange/feed`, `exchange/kalshi/stream` |
| `exchange/settlement.py` | reusable | 10/3 | `exchange/kalshi/mapping`, `weather/chicago_rules`, `weather/cli_observations`, `weather/cli_print_guess`, `weather/informational_rules`, `weather/provenance`, `weather/revision_bracket`, `weather/revision_rule`, `weather/settlement_score`, `weather/trade_score` |
| `exchange/spread_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/trade_prints.py` | reusable | 13/7 | `weather/austin_rules`, `weather/chicago_rules`, `weather/cli_print_guess`, `weather/dallas_rules`, `weather/informational_rules`, `weather/kxhigh_scan`, `weather/newyork_rules`, `weather/oklahomacity_rules`, `weather/provenance`, `weather/revision_bracket`, `weather/revision_rule`, `weather/trade_score`, `weather/walk_forward` |
| `exchange/unit_asks.py` | narrow stored-data summary | 0/1 | — |
| `exchange/unit_interest.py` | narrow stored-data summary | 0/1 | — |
| `exchange/volume_values.py` | narrow stored-data summary | 0/1 | — |
| `exchange/zero_bids.py` | narrow stored-data summary | 0/1 | — |
| `exchange/zero_volumes.py` | narrow stored-data summary | 0/1 | — |
| `weather/amsterdam_listing.py` | narrow city-study wrapper | 0/1 | — |
| `weather/austin_rules.py` | narrow city-study wrapper | 1/2 | `weather/revision_bracket` |
| `weather/baseline.py` | reusable | 5/1 | `agents/fixture`, `weather/chicago_rules`, `weather/public_dataset`, `weather/settlement_score`, `weather/walk_forward` |
| `weather/before_close.py` | narrow source/feature helper | 0/1 | — |
| `weather/before_occurrence.py` | narrow source/feature helper | 0/1 | — |
| `weather/chicago_rules.py` | narrow city-study wrapper | 3/16 | `weather/feature_coverage`, `weather/revision_bracket`, `weather/revision_rule` |
| `weather/cli_observations.py` | reusable | 15/10 | `weather/austin_rules`, `weather/chicago_rules`, `weather/cli_print_guess`, `weather/dallas_rules`, `weather/hours_until_resolution`, `weather/informational_rules`, `weather/kxhigh_scan`, `weather/newyork_rules`, `weather/oklahomacity_rules`, `weather/provenance`, `weather/revision_bracket`, `weather/revision_rule`, `weather/settlement_score`, `weather/trade_score`, `weather/walk_forward` |
| `weather/cli_print_guess.py` | narrow source/feature helper | 2/4 | `weather/chicago_rules`, `weather/walk_forward` |
| `weather/cloud_cover.py` | narrow source/feature helper | 0/1 | — |
| `weather/dallas_rules.py` | narrow city-study wrapper | 1/1 | `weather/revision_bracket` |
| `weather/dew_point.py` | narrow source/feature helper | 0/1 | — |
| `weather/ecmwf_ifs.py` | reusable | 4/1 | `weather/ensemble_ecmwf_gap`, `weather/mean_ecmwf_gap`, `weather/model_gap`, `weather/nws_ecmwf_gap` |
| `weather/ecmwf_ifs_previous.py` | reusable | 2/1 | `weather/gfs_ecmwf_gap`, `weather/previous_model_gap` |
| `weather/ensemble_ecmwf_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/ensemble_hrrr_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/ensemble_rank.py` | narrow source/feature helper | 0/1 | — |
| `weather/expiration_check.py` | narrow source/feature helper | 1/1 | `weather/chicago_rules` |
| `weather/feature_coverage.py` | narrow source/feature helper | 0/2 | — |
| `weather/forecast_dispersion.py` | narrow source/feature helper | 0/1 | — |
| `weather/forecast_mean.py` | narrow source/feature helper | 4/1 | `weather/mean_control_gap`, `weather/mean_ecmwf_gap`, `weather/mean_hrrr_gap`, `weather/nws_mean_gap` |
| `weather/gfs_ecmwf_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/gfs_ensemble.py` | reusable | 11/1 | `weather/ensemble_ecmwf_gap`, `weather/ensemble_hrrr_gap`, `weather/ensemble_rank`, `weather/forecast_dispersion`, `weather/forecast_mean`, `weather/mean_control_gap`, `weather/mean_ecmwf_gap`, `weather/mean_hrrr_gap`, `weather/nws_control_gap`, `weather/nws_mean_gap`, `weather/nws_member_gap` |
| `weather/gfs_hrrr_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/gfs_seamless_previous.py` | reusable | 2/1 | `weather/gfs_ecmwf_gap`, `weather/gfs_hrrr_gap` |
| `weather/hour_of_day.py` | narrow source/feature helper | 0/1 | — |
| `weather/hours_until_resolution.py` | narrow source/feature helper | 0/1 | — |
| `weather/houston_listing.py` | narrow city-study wrapper | 0/1 | — |
| `weather/hrrr_archive.py` | reusable | 0/1 | — |
| `weather/humidity.py` | narrow source/feature helper | 0/1 | — |
| `weather/informational_rules.py` | narrow city-study wrapper | 9/130 | `weather/austin_rules`, `weather/chicago_rules`, `weather/dallas_rules`, `weather/kxhigh_scan`, `weather/newyork_rules`, `weather/oklahomacity_rules`, `weather/revision_bracket`, `weather/revision_rule`, `weather/walk_forward` |
| `weather/kxhigh_scan.py` | reusable | 1/1 | `weather/revision_bracket` |
| `weather/last_print.py` | narrow source/feature helper | 3/7 | `weather/before_close`, `weather/before_occurrence`, `weather/cli_print_guess` |
| `weather/live_trades_short.py` | narrow source/feature helper | 0/1 | — |
| `weather/mean_control_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/mean_ecmwf_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/mean_hrrr_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/mexicocity_listing.py` | narrow city-study wrapper | 0/1 | — |
| `weather/model_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/ncep_hrrr.py` | reusable | 5/1 | `weather/ensemble_hrrr_gap`, `weather/mean_hrrr_gap`, `weather/model_gap`, `weather/nws_forecast_hrrr_gap`, `weather/nws_hrrr_gap` |
| `weather/ncep_hrrr_previous.py` | reusable | 2/1 | `weather/gfs_hrrr_gap`, `weather/previous_model_gap` |
| `weather/newyork_rules.py` | narrow city-study wrapper | 1/5 | `weather/revision_bracket` |
| `weather/nws_control_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_daytime.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_detailed_forecast.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_dew_point.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_ecmwf_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_end_time.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast.py` | reusable | 47/2 | `weather/nws_control_gap`, `weather/nws_daytime`, `weather/nws_detailed_forecast`, `weather/nws_dew_point`, `weather/nws_ecmwf_gap`, `weather/nws_end_time`, `weather/nws_forecast_context`, `weather/nws_forecast_coordinate_count`, `weather/nws_forecast_daytime`, `weather/nws_forecast_detailed`, `weather/nws_forecast_elevation`, `weather/nws_forecast_end_time`, `weather/nws_forecast_geometry_type`, `weather/nws_forecast_hrrr_gap`, `weather/nws_forecast_icon`, `weather/nws_forecast_name`, `weather/nws_forecast_number`, `weather/nws_forecast_precipitation`, `weather/nws_forecast_short`, `weather/nws_forecast_start_time`, `weather/nws_forecast_temperature_trend`, `weather/nws_forecast_temperature_unit`, `weather/nws_forecast_temperatures`, `weather/nws_forecast_type`, `weather/nws_forecast_wind_direction`, `weather/nws_forecast_wind_speed`, `weather/nws_hourly_context`, `weather/nws_hourly_coordinate_count`, `weather/nws_hourly_elevation`, `weather/nws_hourly_geometry_type`, `weather/nws_hourly_type`, `weather/nws_hrrr_gap`, `weather/nws_icon`, `weather/nws_mean_gap`, `weather/nws_member_gap`, `weather/nws_metadata`, `weather/nws_period_name`, `weather/nws_period_number`, `weather/nws_precipitation_probability`, `weather/nws_relative_humidity`, `weather/nws_short_forecast`, `weather/nws_start_time`, `weather/nws_temperature_trend`, `weather/nws_temperature_unit`, `weather/nws_temperature_values`, `weather/nws_wind_direction`, `weather/nws_wind_speed` |
| `weather/nws_forecast_context.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_coordinate_count.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_daytime.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_detailed.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_elevation.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_end_time.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_generated_at.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_forecast_generator.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_forecast_geometry_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_hrrr_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_icon.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_name.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_number.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_precipitation.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_short.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_start_time.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_temperature_trend.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_temperature_unit.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_temperatures.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_units.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_forecast_update_time.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_forecast_valid_times.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_forecast_wind_direction.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_forecast_wind_speed.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_hourly_context.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_hourly_coordinate_count.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_hourly_elevation.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_hourly_generated_at.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_hourly_generator.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_hourly_geometry_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_hourly_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_hourly_units.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_hourly_update_time.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_hourly_valid_times.py` | compatibility wrapper; duplicate parser consolidated | 0/1 | — |
| `weather/nws_hrrr_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_icon.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_mean_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_member_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_metadata.py` | reusable | 10/1 | `weather/nws_forecast_generated_at`, `weather/nws_forecast_generator`, `weather/nws_forecast_units`, `weather/nws_forecast_update_time`, `weather/nws_forecast_valid_times`, `weather/nws_hourly_generated_at`, `weather/nws_hourly_generator`, `weather/nws_hourly_units`, `weather/nws_hourly_update_time`, `weather/nws_hourly_valid_times` |
| `weather/nws_period_name.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_period_number.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_astronomical.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_context.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_coordinate_count.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_geometry_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_id.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_property_id.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_property_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_twilight_begin.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_points_type.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_precipitation_probability.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_relative_humidity.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_short_forecast.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_start_time.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_temperature_trend.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_temperature_unit.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_temperature_values.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_wind_direction.py` | narrow source/feature helper | 0/1 | — |
| `weather/nws_wind_speed.py` | narrow source/feature helper | 0/1 | — |
| `weather/observed_temperature.py` | narrow source/feature helper | 3/1 | `weather/hour_of_day`, `weather/previous_day_error`, `weather/seasonality` |
| `weather/oklahomacity_rules.py` | narrow city-study wrapper | 1/1 | `weather/revision_bracket` |
| `weather/precipitation.py` | narrow source/feature helper | 0/1 | — |
| `weather/previous_day_error.py` | narrow source/feature helper | 1/1 | `weather/station_bias` |
| `weather/previous_model_gap.py` | narrow source/feature helper | 0/1 | — |
| `weather/probability.py` | reusable | 3/1 | `weather/provenance`, `weather/public_dataset`, `weather/settlement_score` |
| `weather/provenance.py` | reusable | 1/6 | `weather/feature_coverage` |
| `weather/public_dataset.py` | legacy exploration; unsafe book sizing | 0/1 | — |
| `weather/recorded.py` | reusable | 7/1 | `weather/austin_rules`, `weather/chicago_rules`, `weather/cli_observations`, `weather/dallas_rules`, `weather/kxhigh_scan`, `weather/newyork_rules`, `weather/oklahomacity_rules` |
| `weather/revision_bracket.py` | reusable | 2/3 | `weather/kxhigh_scan`, `weather/revision_records` |
| `weather/revision_records.py` | reusable | 1/2 | `weather/kxhigh_scan` |
| `weather/revision_rule.py` | reusable | 4/120 | `weather/hours_until_resolution`, `weather/kxhigh_scan`, `weather/revision_bracket`, `weather/revision_records` |
| `weather/seasonality.py` | narrow source/feature helper | 0/1 | — |
| `weather/settlement_score.py` | reusable | 5/16 | `weather/informational_rules`, `weather/provenance`, `weather/tape_score`, `weather/trade_score`, `weather/walk_forward` |
| `weather/settlement_value.py` | narrow source/feature helper | 1/1 | `weather/chicago_rules` |
| `weather/short_refresh.py` | narrow source/feature helper | 0/1 | — |
| `weather/station_bias.py` | narrow source/feature helper | 0/1 | — |
| `weather/structure.py` | reusable | 0/1 | — |
| `weather/tape_score.py` | narrow source/feature helper | 0/1 | — |
| `weather/trade_score.py` | narrow source/feature helper | 0/1 | — |
| `weather/volume_check.py` | narrow source/feature helper | 0/1 | — |
| `weather/walk_forward.py` | reusable | 4/5 | `weather/chicago_rules`, `weather/kxhigh_scan`, `weather/revision_bracket`, `weather/revision_rule` |
| `weather/wind.py` | narrow source/feature helper | 0/1 | — |
