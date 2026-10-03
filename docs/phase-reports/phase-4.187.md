---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.187 checkpoint

Date: 2026-10-03. Phase 4.187 is off-plan work. No order was sent. Nothing
was promoted. `2°F` and `0.40` were not changed.

A copy of this file is in the repository at `docs/phase-reports/phase-4.187.md`.

## Rule

This archive rule was written before the request was sent.

Read `properties.forecastHourly` from the stored Philadelphia NWS points
body. If that value is not a string that starts with
`https://api.weather.gov/`, do not request anything and do not invent
hourly values. If it does, request that one URL with
`User-Agent: EntropyTrade research archive` and
`Accept: application/geo+json`. Do not send a key. Do not request any
other URL. If the response is not HTTP 200, store the body and the status
and do not invent hourly values. Do not align the body to the CLI decision
clock. Do not add a threshold. Do not trade. Do not score a holdout. Do
not promote. No live order.

## Result

`properties.forecastHourly` in the stored points body is
`https://api.weather.gov/gridpoints/PHI/48,75/forecast/hourly`. That
request returned HTTP 200. The body has 156 periods and 0 null
temperatures. The first period starts at 2026-10-03T03:00:00-04:00. No
other URL was requested. The body was not aligned to the CLI decision
clock. The CLI coverage row for NWS forecast still says no stored value.
Nothing was traded. `2°F` and `0.40` were not changed. Nothing was
promoted.

## Tests

`make check` on 2026-10-03: ruff clean, mypy strict clean, pytest 303 passed.
