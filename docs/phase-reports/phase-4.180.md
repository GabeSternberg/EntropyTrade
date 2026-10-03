---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.180 checkpoint

Date: 2026-10-03. Phase 4.180 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.180.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public Open-Meteo archive API for Philadelphia observed temperature
at the stored coordinates, latitude 39.87 and longitude -75.23. The hourly
field is `temperature_2m`. The window is `start_date=2026-08-24` and
`end_date=2026-10-02`, which is the span already stored by the previous-day
series. Do not add 2026-08-23. Do not send `run`. Use
`temperature_unit=fahrenheit` and `timezone=UTC`. Do not overwrite
`previous-runs.json`, `revision-vintages.json`, or the dew-point, humidity,
cloud-cover, wind, or precipitation archives.

If the response is HTTP 200 and the payload has the field, store the body
and a manifest. If the response is not HTTP 200, store the body and the
status, and do not invent temperatures. Do not trade on the field. Do not
add a threshold. Do not score a holdout. Do not promote. No live order.

## Result

The request returned HTTP 200. The body is
`data/public/open-meteo/observed-temperature.json`. The manifest is
`observed-temperature.manifest.json`. The field `temperature_2m` has 960
hours and 0 nulls. The first hour is 2026-08-24T00:00 and the last hour
is 2026-10-02T23:00. The unit is °F. The response timezone is GMT, and
there is no issue time. The requested coordinates were 39.87 and -75.23.
The response coordinates are 39.89455 and -75.18826, which are not the
previous-runs grid point. They were stored as returned. 2026-08-23 was
not requested and is not in the body. The earlier archives were not
overwritten. One error string in the precipitation reader said
`precipitationow`; it now says `window`. The precipitation series was
not rewritten. The CLI coverage row for recent observed temperature
still says no stored value. Nothing was traded. `2°F` and `0.40` were
not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 289 passed.
