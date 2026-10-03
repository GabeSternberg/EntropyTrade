# EntropyTrade

Private, single-user research, backtesting and (eventually) automated trading for Kalshi
prediction markets. Not a SaaS product. Phase 0 is complete: domain types, architecture
and an audit of the open-source projects the design builds on. Phase 1 is a read-only
Kalshi gateway and a SQLite recorder. Phase 2 is paper accounting and the risk gate.
Phase 3 replays recorded books without showing the strategy future rows. Phase 4 scores
daily-high baselines from recorded weather bodies. Phase 5 turns a prompt into
StrategySpecs and backtests the ones that pass the critic and the interpreter.
Phase 6 stores those specs and serves a read-only registry page.
Phase 7 flags executable-price violations and can paper them.
Phase 8 compares a paper or shadow price with the next recorded print.
Phase 9 classifies a submit without opening a socket. The Kalshi gateway
still refuses every submit. Phase 10 flags decay from those comparisons and
proposes a downward lifecycle move. None of this sends exchange orders.

The requirements are in [`docs/project-spec.md`](docs/project-spec.md). Where the project
actually is, and how to resume it, is [`STATUS.md`](STATUS.md).

## Requirements

Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run entropytrade
make check          # ruff, mypy, pytest
```

`entropytrade` prints the version and the default trading mode (`read_only`). A checkout
cannot submit orders.

## Layout

`backend/src/entropytrade/` is the Python package. `domain/` holds venue-neutral types
(exact decimals, UTC timestamps, strategy specs, the order state machine). `exchange/`
defines `ExchangeGateway`. The Kalshi SDK (`kalshi-sdk==17.1.0`) is imported only inside
`exchange/kalshi/`.

Kalshi's current API docs are checked out as an agent skill at
[`.agents/skills/kalshi-docs/`](.agents/skills/kalshi-docs/SKILL.md), pinned by
[`skills-lock.json`](skills-lock.json). Refresh with `npx skills add ammario/kalshi-docs --skill kalshi-docs -a cursor -y --copy`.
The command in the spec, `npx add-skill`, is the old name of that tool.

## Configuration

`.env.example` lists variable names and nothing else. Copy it to `.env` locally; `.env` is
gitignored. `configs/dev`, `configs/paper` and `configs/live` are mode files. Live mode also
requires `ENTROPYTRADE_LIVE_TRADING_ENABLED=true` in the execution process environment.

## Status

Phase 10 is complete as a fixture-tested gate. It does not submit. Phase 11
is deferred. Weather research scores stored daily-high tapes. The frozen
revision rules use 2°F and a 0.40 print. `forecast_revision_bracket` buys
the stored between-contract that contains a later maximum revised up by at
least 2°F. `forecast_revision_down` uses the same magnitude with the sign
flipped. Every stored city that already has both previous-day fields is scored
on that downward rule. Those decisions have prediction records.
Neither rule scores a holdout or sends an order. Philadelphia dew point,
relative humidity, cloud cover, wind speed, and precipitation from the
public previous-runs API are stored and are not trades. Observed
temperature for the same dates is stored from the public archive API and
is not a trade. The hour of day is the hour in those timestamps, and
the calendar month is the month in those timestamps. Previous-day
temperature errors compare the observed daily maximum with the stored
previous-day maximum and are not a trade. Their unrounded mean is stored
as a station bias and is not subtracted from a forecast. Hours until
resolution are the hours from 15:00 UTC on the valid day until the stored
CLI label time. A public NWS points response and the one forecast
it names are stored and are not aligned to that clock. The hourly
forecast named by that points body is stored the same way. A one-day
GFS ensemble from the public Open-Meteo ensemble API is stored and is
not a trade. The unrounded mean of those 31 series is stored and is not
a threshold. The range of those series, maximum minus minimum, is stored
the same way. A forecast-API request with `models=hrrr` returned HTTP 400
and is stored as an error. No temperature was invented from that body.
The documented model id `ncep_hrrr_conus` returned one day of temperature
and is stored the same way, not aligned to the CLI clock. The documented
model id `ecmwf_ifs` is stored the same way, on its own grid point. The
hour-by-hour difference of those two stored series is recorded and is not
a threshold. Stored Philadelphia candlesticks have bid and ask close
strings. A candle is not an order book. The same files store volume and
open interest as strings, and volume is not a size at the touch. The
ask close minus the bid close is stored as a spread and is not compared
to 0.40. A candlestick price close is counted only when the stored field
is a decimal string. A missing close is not filled in and is not called
a probability. Where both the close and the previous close are decimal
strings, the change is the close minus the previous and is not compared
to 0.40. Candlestick tickers have 65 distinct strike suffixes. `B80.5`
is absent from those tickers and was not invented. Stored CLI-window
order books do not have both a yes level and a no level, so no imbalance
was computed. One previous-runs day of `ncep_hrrr_conus`
`temperature_2m_previous_day1` is stored and is not a threshold. The same
request for `ecmwf_ifs` is stored on its own grid point. The hour-by-hour
difference of those two previous-day series is recorded and is not a
threshold. One previous-runs day of `gfs_seamless` is stored the same way
and was not snapped to the ensemble grid. On that previous day, GFS minus
HRRR is 0°F at every stored hour. That zero is not a threshold. The
hour-by-hour difference of the GFS ensemble control and the HRRR forecast
is recorded on the two stored grids and is not a threshold. The same
control series minus the stored ECMWF forecast is recorded on those two
grids and is not a threshold. On the previous day, GFS minus ECMWF is
recorded on the two stored grids and is not a threshold. The unrounded
ensemble mean minus the stored HRRR forecast is recorded on those two
grids and is not a threshold. The same unrounded mean minus the stored
ECMWF forecast is recorded on those two grids and is not a threshold. The
same unrounded mean minus the ensemble control is recorded on the stored
ensemble grid and is not a threshold. The control's rank inside the 31
series is 1 plus the number of series strictly colder than the control.
That rank is not divided and is not a probability. Stored candlestick
spreads have 20 distinct values. The count was not compared to 0.40.
Stored candlestick price closes have 98 distinct values. A close was not
called a probability and the count was not compared to 0.40. Consecutive
candlestick closes have 94 distinct changes. That count was not compared
to 0.40. Stored candlestick bid closes have 100 distinct values, including
0.0000. A candle is not an order book and the count was not compared to
0.40. Stored candlestick ask closes have 100 distinct values. 0.0000 is
absent from those asks and was not invented. The count was not compared
to 0.40. Stored candlestick volumes have 3023 distinct values. Volume is
not a size at the touch and the count was not compared to 0.40. Stored
candlestick open interest has 3846 distinct values. 0.00 is absent and
was not invented. Open interest is not a size at the touch. 1912 stored
bid closes are exactly 0.0000. That zero is not a fill and the count was
not compared to 0.40. 143 stored ask closes are exactly 1.0000. That one
is not a settlement and is not a probability. 1465 stored volumes are
exactly 0.00. That zero is not a missing volume and is not a size at the
touch. One stored open-interest value is exactly 1.00. That one is not a
size at the touch. The stored NWS hourly forecast minus the stored HRRR
forecast, at equal UTC instants, is recorded. The NWS polygon was not
snapped to the HRRR grid. That difference is not a threshold. The same
NWS series minus the stored ECMWF forecast is recorded the same way.
The NWS polygon was not snapped to the ECMWF grid. That difference is
not a threshold. The same NWS series minus the ensemble control is
recorded on the stored ensemble grid. Member series are not in that
difference. It is not a threshold. The same NWS series minus the
unrounded ensemble mean is recorded. The mean still uses all 31
temperature series. That difference was not rounded and is not a
threshold. The same NWS series minus ensemble member
`temperature_2m_member01` is recorded. The other members stay in the
stored mean. That difference is not a threshold. The stored NWS hourly
temperatures have 28 distinct values, from 46 through 73. That count
was not compared to 0.40 and is not a threshold. The stored NWS forecast
periods, not the hourly body, minus the stored HRRR forecast at equal
UTC instants are recorded. That difference is not a threshold. Those
same forecast periods have 12 distinct temperatures, from 45 to 73.
Missing integers were not invented. The count was not compared to 0.40
and is not a threshold. The stored NWS hourly precipitation
probabilities have 14 distinct values, from 0 to 66. A value was not
divided by 100 and was not called a market probability. The stored NWS
hourly relative-humidity values have 40 distinct values, from 46 to 100.
A value was not divided by 100 and the count was not compared to 0.40.
The stored NWS hourly dew-point values have 25 distinct values. The unit
was not converted and the count was not compared to 0.40. The stored NWS
hourly wind directions have 7 distinct values. A direction was not
converted into degrees. The stored NWS hourly wind-speed strings have 3
distinct values in alphabetical order: `0 mph`, `10 mph`, and `5 mph`.
Those strings were not parsed into numbers. The stored NWS hourly
short forecasts have 11 distinct strings. A forecast was not rewritten
into another word and the count was not compared to 0.40. The stored NWS
hourly periods have 81 daytime periods and 75 nighttime periods. Daytime
was not treated as a trading session and the counts were not compared to
0.40. The stored NWS hourly detailed forecasts have 0 distinct strings.
Every stored string was empty and was not filled in. A forecast was not
rewritten and the count was not compared to 0.40. The stored NWS hourly
temperature trends have 0 distinct strings. Every stored value was null
and was not filled in. A trend was not rewritten and the count was not
compared to 0.40 or to 2°F. The stored NWS hourly temperature units have
1 distinct string, `F`. The unit was not converted into another scale
and the count was not compared to 0.40 or to 2°F. The stored NWS hourly
period names have 0 distinct strings. Every stored string was empty and
was not filled in. A name was not rewritten and the count was not
compared to 0.40 or to 2°F. The stored NWS hourly icon strings have 13
distinct values. An icon was not fetched, a string was not rewritten,
and the count was not compared to 0.40 or to 2°F. The stored NWS hourly
period numbers are the integers 1 through 156. A missing number was not
invented and the count was not compared to 0.40 or to 2°F. The stored
NWS hourly end times have 156 distinct strings. A duration was not
computed and the count was not compared to 0.40 or to 2°F. The stored
NWS hourly start times have 156 distinct strings. A duration was not
computed and the count was not compared to 0.40 or to 2°F. The stored
NWS forecast period names, not the hourly body, have 14 distinct strings
in alphabetical order. A name was not rewritten and the count was not
compared to 0.40 or to 2°F. Those same forecast periods have 7 distinct
short forecasts. A forecast was not rewritten and the count was not
compared to 0.40 or to 2°F.
See
[`STATUS.md`](STATUS.md) before starting anything else.
The scanner is described in [`docs/scanner.md`](docs/scanner.md).
The reuse decisions are in [`docs/external-repositories.md`](docs/external-repositories.md).
