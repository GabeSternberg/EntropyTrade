---
cursor:
  subagentId: "bc-f01883ed-f91d-5370-84f2-d6aa0527e162"
---

# Phase 4.51 checkpoint

Date: 2026-10-02. Phase 4.51 is complete. It is off-plan work. No order was
sent. The production host was not called.

A copy of this file is in the repository at `docs/phase-reports/phase-4.51.md`.

## What was fetched

Unauthenticated GET to the Iowa Environmental Mesonet for NWS product
`CLIPHL`, the Philadelphia climate report named in `KXHIGHPHIL`.

| Call | Result |
| --- | --- |
| `cgi-bin/afos/retrieve.py?pil=CLIPHL&fmt=text&limit=400&sdate=2026-08-24&edate=2026-10-03` | HTTP 200. 79 products. Stored at `data/public/iem/cliphl-afos.txt`. |
| `api/1/nws/afos/list.json?pil=CLIPHL&sdate=...&edate=...` | HTTP 422. Body below. No rows were invented from it. |

```json
{"detail":[{"type":"extra_forbidden","loc":["query","sdate"],"msg":"Extra inputs are not permitted","input":"2026-08-24"},{"type":"extra_forbidden","loc":["query","edate"],"msg":"Extra inputs are not permitted","input":"2026-10-03"}]}
```

## What a label is

`available_at` is the UTC time in the WMO header `KPHI ddhhmm`. The parser
already refuses a high whose time falls on the observation day, so the
afternoon "valid today" products are not labels. 38 of those were skipped.
40 mornings remain, 23 Aug through 1 Oct 2026. No day had a later product
with a different high. The source on each row is `iem-nws-cli`, with the
retrieve URL as the endpoint.

These dates are on or after 2026-08-14. The contract text names The Weather
Company, not the NWS CLI. The CLI number is the closest public station report.
It is not recorded as the settlement value. Open-Meteo is not settlement either.

## Disagreements

Against the stored Open-Meteo archive, on all 40 days:

- Exact value differs on 40 days. The archive has tenths; the CLI high is an integer.
- Rounded to the nearest degree, 39 days still differ.
- Mean absolute difference is 2.19 °F.

Against Kalshi official `result` on markets that also have an archive high:

| Set | Markets | CLI disagrees | Open-Meteo disagrees |
| --- | --- | --- | --- |
| `B80.5` (80–81 °F) | 9 | 0 | 1 |
| All stored `KXHIGHPHIL` strikes on those days | 222 | 0 | 50 |

The one `B80.5` archive miss is 25 Aug 2026. The CLI high is 80, available
26 Aug 06:14 UTC, and the bracket resolves YES. The archive high is 79.8,
which does not. The official result is `yes`.

## Tests

`make check` on 2026-10-02: ruff clean, mypy strict clean, pytest 146 passed.

## Files

- `data/public/iem/`
- `backend/src/entropytrade/weather/cli_observations.py`
- `backend/tests/unit/test_cli_observations.py`
