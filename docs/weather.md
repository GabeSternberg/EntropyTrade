# Weather

Phase 4 scores daily-high brackets from recorded bodies. Nothing in
`entropytrade.weather` opens a socket.

## Labels and forecasts

`parse_cli_daily_high` reads the first `MAXIMUM` line of an NWS CLI product and the
`FOR <MONTH> <DAY> <YEAR>` date. Hourly temperatures in the same text are not the
label. `parse_weather_company_high` reads a recorded JSON object whose `high_f` is a
string. Both refuse an `available_at` on the observation day: the daily high is not
known until a later calendar day.

`parse_recorded_forecast` reads one forecast vintage. `run_time` cannot be after
`available_at`. A forecast may be available on the valid day; the label may not.

Philadelphia contracts (`KXHIGHPHIL`, station CLIPHL) still settle by the rule in
`parse_settlement`: NWS CLI before 2026-08-14, The Weather Company on and after, when
the contract text does not name a source.

## Baselines

Scored only with information available at the decision:

| Baseline | Probability |
| --- | --- |
| Market | Displayed book midpoint. Not a fill price. |
| Climatology | Fraction of already-available CLI highs that resolve YES on the strike. |
| Raw forecast | 1 if the forecast value itself would resolve YES, else 0. |
| Calibrated | Average of the raw indicator and the climatology hit rate. |
| Fitted / ML | Refused below 30 scored days. This sample does not qualify. |

`greater` is strict, `less` is strict, `between` is inclusive, via `Strike.resolves_yes`.
Persistence may repeat the previous CLI high only after that high's `available_at`.

## What the fixture says

The tests use a synthetic Philadelphia day, not a downloaded archive. A YES buy of one
contract at 0.40, with a zero fee coefficient, settles to cash 100.60 from a 100 start.
The same trade with coefficient 0.02 pays a 0.01 taker fee (cash 100.59). A two-hour
latency with only one book does not fill (cash stays 100). A forecast issued after the
CLI does not enter the error. None of this is a claim about live Philadelphia markets.

Live NWS, Weather Company, and Open-Meteo calls are unverified.
