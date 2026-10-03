# Feature manifest coverage

This note records the stored CLI rescore feature manifest. It does not fit a model. Nothing was promoted.

The manifest has 39 rows. Every row is station CLIPHL. The decision clock
is 15:00:00Z. The named columns are forecast_high,
point_in_time_climatology, and prints_at_decision.

The row keys are climatology, decision_time, forecast_available_at,
forecast_high_f, market_listed, market_ticker, prints_at_decision,
raw_probability, sized_book, station, and valid_on. sized_book is false
on all 39 rows.

The previous-runs file's hourly fields are time and
temperature_2m_previous_day1. Bid is empty on 39 prediction records. Ask
is empty on 39 prediction records.

Spec section 27 names the features below. None of those names is a
manifest column or a previous-runs hourly field.

| Spec feature | Stored value |
| --- | --- |
| NWS forecast | no stored value |
| GFS ensemble | no stored value |
| HRRR where available | no stored value |
| ECMWF where available | no stored value |
| forecast mean | no stored value |
| forecast dispersion | no stored value |
| forecast changes/revisions | no stored value |
| hours until resolution | no stored value |
| hour of day | no stored value |
| recent observed temperature | no stored value |
| dew point | no stored value |
| humidity | no stored value |
| cloud cover | no stored value |
| wind | no stored value |
| precipitation | no stored value |
| seasonality | no stored value |
| historical station/model bias | no stored value |
| previous day's errors | no stored value |
| Kalshi bid | no stored value |
| Kalshi ask | no stored value |
| spread | no stored value |
| market probability | no stored value |
| market price change | no stored value |
| trade volume | no stored value |
| open interest | no stored value |
| order-book imbalance | no stored value |
| related temperature strikes | no stored value |

The revision-bracket manifest stores these features: later_max, earlier_max, revision. They are not CLI rescore columns. They are not a new threshold. The holdout is not scored. Nothing was promoted.

The Philadelphia dew-point archive stores 960 hours of dew_point_2m_previous_day1. 0 of those hours are null. The first hour is 2026-08-24T00:00. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia humidity archive stores 960 hours of relative_humidity_2m_previous_day1. 0 of those hours are null. The first hour is 2026-08-24T00:00. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia cloud-cover archive stores 960 hours of cloud_cover_previous_day1. 0 of those hours are null. The first hour is 2026-08-24T00:00. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia wind archive stores 960 hours of wind_speed_10m_previous_day1. 0 of those hours are null. The first hour is 2026-08-24T00:00. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia precipitation archive stores 960 hours of precipitation_previous_day1. 0 of those hours are null. The first hour is 2026-08-24T00:00. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia observed-temperature archive stores 960 hours of temperature_2m. 0 of those hours are null. The first hour is 2026-08-24T00:00. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia hour-of-day record has 960 hours taken from the observed-temperature timestamps. The hour is the hour in the timestamp. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia seasonality record has 960 months taken from the observed-temperature timestamps. The month is the month in the timestamp. Months are not bucketed into named seasons. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia previous-day error record has 39 eligible days and 2 skipped days. The error is the observed daily maximum minus the previous-day daily maximum. The grid points were not snapped together. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia station-bias record is the mean of 39 eligible previous-day errors. The mean is 0.6333333333333333333333333333 °F. It is not subtracted from a forecast. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia hours-until-resolution record has 40 labels and 0 negative spans. The decision time is 15:00 UTC on the valid day. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia NWS archive stores the points response and one forecast. The forecast has 14 periods. The first period starts at 2026-10-02T19:00:00-04:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia NWS hourly archive stores 156 periods. 0 temperatures are null. The first period starts at 2026-10-03T03:00:00-04:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia GFS ensemble archive stores 24 hours and 31 temperature series. 0 values are null. The first hour is 2026-10-03T00:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia forecast-mean record has 24 unrounded hourly means. Each mean uses all 31 temperature series. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia forecast-dispersion record has 24 hourly ranges. Each range is the maximum minus the minimum of all 31 series. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia HRRR request returned HTTP 400. No temperature series was invented. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia HRRR archive stores 24 hours of temperature_2m from ncep_hrrr_conus. 0 of those hours are null. The first hour is 2026-10-03T00:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia ECMWF archive stores 24 hours of temperature_2m from ecmwf_ifs. 0 of those hours are null. The first hour is 2026-10-03T00:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia ECMWF-minus-HRRR record has 24 eligible hours and 0 skipped hours. The difference is the ECMWF temperature minus the HRRR temperature. The grid points were not snapped together. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia candlestick files have 230 files and 5529 candlesticks. 5529 bids and 5529 asks are strings, including 0.0000. 0 fields were missing and were not filled in. A candle is not an order book. It was not aligned to 15:00 UTC. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia candlestick files have 230 files and 5529 candlesticks. 5529 volumes and 5529 open-interest values are strings, including 0.00. 0 fields were missing and were not filled in. Volume is not a size at the touch. It was not aligned to 15:00 UTC. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia candlestick spreads cover 5529 candlesticks. 0 spreads are zero and 0 are negative. 0 closes were not decimals and were not filled in. A zero spread is kept. The spread was not compared to 0.40. A candle is not an order book. It was not aligned to 15:00 UTC. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia candlestick price closes cover 4064 candlesticks. 1465 closes were missing and were not filled in. A close was not divided. A close was not compared to 0.40. It was not called a probability. It was not aligned to 15:00 UTC. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia candlestick price changes cover 4064 candlesticks. 1237 changes are zero and 1433 are negative. 1465 fields were missing and were not filled in. A change was not compared to 0.40. It was not aligned to 15:00 UTC. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia candlestick tickers have 65 distinct strikes across 230 files. 0 files had no ticker and were not filled in. B80.5 is absent. No neighbor bracket was invented. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The stored Philadelphia CLI-window order books have 240 books. 0 have both a yes level and a no level, so no imbalance was computed. 240 books had an empty side or no stored body and were not filled in. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia HRRR previous-day archive stores 24 hours of temperature_2m_previous_day1 from ncep_hrrr_conus. 0 of those hours are null. The first hour is 2026-10-02T00:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia ECMWF previous-day archive stores 24 hours of temperature_2m_previous_day1 from ecmwf_ifs. 0 of those hours are null. The first hour is 2026-10-02T00:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia ECMWF-minus-HRRR previous-day record has 24 eligible hours and 0 skipped hours. The difference is the ECMWF temperature minus the HRRR temperature. The grid points were not snapped together. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.

The Philadelphia GFS previous-day archive stores 24 hours of temperature_2m_previous_day1 from gfs_seamless. 0 of those hours are null. The first hour is 2026-10-02T00:00. It was not aligned to the CLI decision clock. It is not a CLI rescore column. It is not a threshold. Nothing was traded. Nothing was promoted.
