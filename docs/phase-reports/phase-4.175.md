---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.175 checkpoint

Date: 2026-10-03. Phase 4.175 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.175.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public previous-runs API for Philadelphia dew point at the stored
coordinates, latitude 39.87 and longitude -75.23. The hourly field is
`dew_point_2m_previous_day1`. Do not send `run`. Do not send a start date.
Use `temperature_unit=fahrenheit`, `timezone=UTC`, `past_days=40`, and
`forecast_days=0`. Do not overwrite `previous-runs.json` or
`revision-vintages.json`.

If the response is HTTP 200 and the payload has the field, store the body
and a manifest. If the response is not HTTP 200, store the body and the
status, and do not invent dew points. Do not trade on the field. Do not
add a threshold. Do not score a holdout. Do not promote. No live order.

## Result

The request returned HTTP 200. The body is
`data/public/open-meteo/dew-point-previous-day1.json`. The manifest is
`dew-point-previous-day1.manifest.json`. The field
`dew_point_2m_previous_day1` has 960 hours and 0 nulls. The first hour is
2026-08-24T00:00 and the last hour is 2026-10-02T23:00. The unit is °F.
The response timezone is GMT, and there is no issue time. The requested
coordinates were 39.87 and -75.23. The response coordinates are
39.863625 and -75.22328. 2026-08-23 is not in the body and was not
invented. `previous-runs.json` and `revision-vintages.json` were not
overwritten. The CLI coverage row for dew point still says no stored
value. Nothing was traded. `2°F` and `0.40` were not changed. Nothing
was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 279 passed.
