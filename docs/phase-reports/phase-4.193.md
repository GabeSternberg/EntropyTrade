---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.193 checkpoint

Date: 2026-10-03. Phase 4.193 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.193.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public Open-Meteo forecast API once for ECMWF temperature at the
stored Philadelphia coordinates, latitude 39.87 and longitude -75.23. The
documented model id is `ecmwf_ifs`. The host is
`https://api.open-meteo.com/v1/forecast`. The hourly field is
`temperature_2m`. Use `temperature_unit=fahrenheit`, `timezone=UTC`, and
`forecast_days=1`. Do not send a second model. Do not repeat `models=hrrr`.
If the response is not HTTP 200, store the body and the status and do not
invent temperatures. Do not align a successful body to the CLI decision
clock. Do not add a threshold. Do not trade. Do not score a holdout. Do
not promote. No live order. The CLI coverage row for ECMWF stays "no stored
value".

## Result

The request returned HTTP 200. The model id is `ecmwf_ifs`. 24 hours of
`temperature_2m`, 0 nulls. The first hour is 2026-10-03T00:00 and its value
is 72.6°F. The last hour is 2026-10-03T23:00 and its value is 64.6°F. The
response timezone is GMT. The response coordinates are 39.89455 and
-75.18826 and were not snapped to the request or to the HRRR grid point.
The series was not aligned to the CLI decision clock. The CLI coverage row
for ECMWF still says no stored value. Nothing was traded. `2°F` and `0.40`
were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 315 passed.
