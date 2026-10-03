---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.178 checkpoint

Date: 2026-10-03. Phase 4.178 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.178.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public previous-runs API for Philadelphia wind speed at the stored
coordinates, latitude 39.87 and longitude -75.23. The hourly field is
`wind_speed_10m_previous_day1`. Do not send `run`. Do not send a start
date. Use `temperature_unit=fahrenheit`, `wind_speed_unit=mph`,
`timezone=UTC`, `past_days=40`, and `forecast_days=0`. Do not overwrite
`previous-runs.json`, `revision-vintages.json`, or the dew-point, humidity,
or cloud-cover archives.

If the response is HTTP 200 and the payload has the field, store the body
and a manifest. If the response is not HTTP 200, store the body and the
status, and do not invent wind speeds. Do not send a second unit. Do not
trade on the field. Do not add a threshold. Do not score a holdout. Do not
promote. No live order.

## Result

The request returned HTTP 200. The body is
`data/public/open-meteo/wind-previous-day1.json`. The manifest is
`wind-previous-day1.manifest.json`. The field
`wind_speed_10m_previous_day1` has 960 hours and 0 nulls. The first hour
is 2026-08-24T00:00 and the last hour is 2026-10-02T23:00. The request
asked for miles per hour. The response unit is `mp/h`. The response
timezone is GMT, and there is no issue time. The requested coordinates
were 39.87 and -75.23. The response coordinates are 39.863625 and
-75.22328. 2026-08-23 is not in the body and was not invented. The earlier
archives were not overwritten. The CLI coverage row for wind still says
no stored value. Nothing was traded. `2°F` and `0.40` were not changed.
Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 285 passed.
