---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.191 checkpoint

Date: 2026-10-03. Phase 4.191 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.191.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public Open-Meteo forecast API for HRRR temperature at the stored
Philadelphia coordinates, latitude 39.87 and longitude -75.23. The host is
`https://api.open-meteo.com/v1/forecast`. The model parameter is `hrrr`.
The hourly field is `temperature_2m`. Use `temperature_unit=fahrenheit`,
`timezone=UTC`, and `forecast_days=1`. Do not send a second model. If the
response is not HTTP 200, store the body and the status and do not invent
temperatures. Do not align the body to the CLI decision clock. Do not add
a threshold. Do not trade. Do not score a holdout. Do not promote. No live
order. The CLI coverage row for HRRR stays "no stored value".

## Result

The request returned HTTP 400. The body is
`{"reason":"Invalid value: Cannot initialize MultiDomains from invalid String value hrrr","error":true}`.
There is no hourly series. No temperature was invented. A second model was
not sent. The string `hrrr` is not retried. The CLI coverage row for HRRR
still says no stored value. Nothing was traded. `2°F` and `0.40` were not
changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 311 passed.
