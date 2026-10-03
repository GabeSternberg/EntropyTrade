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
