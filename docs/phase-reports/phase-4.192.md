---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.192 checkpoint

Date: 2026-10-03. Phase 4.192 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.192.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public Open-Meteo forecast API once for HRRR temperature at the
stored Philadelphia coordinates, latitude 39.87 and longitude -75.23. The
documented model id is `ncep_hrrr_conus`, from the Open-Meteo open-data
model list. It is not the string `hrrr`, which already returned HTTP 400.
The host is `https://api.open-meteo.com/v1/forecast`. The hourly field is
`temperature_2m`. Use `temperature_unit=fahrenheit`, `timezone=UTC`, and
`forecast_days=1`. Do not send a second model. Do not repeat `models=hrrr`.
If the response is not HTTP 200, store the body and the status and do not
invent temperatures. Do not align a successful body to the CLI decision
clock. Do not add a threshold. Do not trade. Do not score a holdout. Do
not promote. No live order. The CLI coverage row for HRRR stays "no stored
value".

## Result

The request returned HTTP 200. The model id is `ncep_hrrr_conus`. 24 hours
of `temperature_2m`, 0 nulls. The first hour is 2026-10-03T00:00 and its
value is 73.2°F. The last hour is 2026-10-03T23:00 and its value is 63.4°F.
The response timezone is GMT. The response coordinates are 39.863625 and
-75.22328 and were not snapped to the request. The series was not aligned
to the CLI decision clock. The earlier HTTP 400 for `models=hrrr` stays
stored. The CLI coverage row for HRRR still says no stored value. Nothing
was traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 313 passed.
