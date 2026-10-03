---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.188 checkpoint

Date: 2026-10-03. Phase 4.188 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.188.md`.

## Rule

This archive rule was written before the request was sent.

Ask the public Open-Meteo ensemble API for a GFS temperature ensemble at
the stored Philadelphia coordinates, latitude 39.87 and longitude -75.23.
The model parameter is `gfs_seamless`. The hourly field is
`temperature_2m`. Use `temperature_unit=fahrenheit`, `timezone=UTC`, and
`forecast_days=1`. Do not send a second model. Do not send `past_days`.
If the response is not HTTP 200, store the body and the status and do not
invent ensemble members. Do not align the body to the CLI decision clock.
Do not add a threshold. Do not trade. Do not score a holdout. Do not
promote. No live order.

## Result

The request returned HTTP 200. The body is
`data/public/open-meteo/gfs-ensemble.json`. The model in the request was
`gfs_seamless`. The body has 24 hours, from 2026-10-03T00:00 through
2026-10-03T23:00, and 31 temperature series. None of the values are null.
The requested coordinates were 39.87 and -75.23. The response coordinates
are 39.75 and -75.25. They were not snapped together. No second model was
requested. The body was not aligned to the CLI decision clock. The CLI
coverage row for GFS ensemble still says no stored value. Nothing was
traded. `2°F` and `0.40` were not changed. Nothing was promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 305 passed.
