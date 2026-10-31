# Forward weather settlement labels

The private website can acquire scalar daily highs for a selected immutable retained
weather dataset. Start the usual workbench, freeze retained weather receipts, select the
dataset, and click **Acquire settlement labels**. **Refresh label acquisition** shows
progress, original source clocks, verified values and specific refusals. Download the
label evidence, then freeze another dataset to include compatible verified observations.
The original dataset stays immutable. Research uses the selected new dataset through the
existing model/backtest gates; labels alone do not establish sufficient history or returns.

```bash
.venv/bin/entropytrade-web --workspace data/cache/workbench
```

The adapter reads only the public [Weather Company daily climate endpoint](https://weather.com/kalshi/api/climate/primary?date=2026-10-29),
identified in the official [settlement portal](https://weather.com/kalshi)'s public client.
The initial verified mappings are CLIPHL → PHL/KPHL/America/New_York and
CLIMDW → MDW/KMDW/America/Chicago. Other stations or authorities produce explicit refusals.
NWS CLI, hourly maxima and official binary outcomes cannot substitute for Weather Company
scalar highs. No credentials, exchange submissions or arbitrary URLs are accepted.

A report must have the requested date, unique matching station and timezone, matching
report station/date, `status=official` or `revised`, `isOfficial=true`, and an integer
`maxTemp`. The portal identifies daily values as Fahrenheit. The captured contract must
explicitly name the same authority, station, date and maximum-temperature Fahrenheit rule.
Changed rules, unsupported semantics, preliminary/missing reports, HTTP failures, oversized
responses and incompatible clocks remain inspectable refusals. Acquired highs do not
manufacture a finalized Kalshi binary outcome or certify the absence of material errors.

Availability starts at the collector receipt after the full local day ends. HTTP Date and
Last-Modified remain receipt metadata; neither backdates availability. ISO provider
`issueTime` and `revisedAt`, when supplied with timezones, are retained separately and
validated against receipt and completed-day clocks. Missing provider clocks remain null;
`revised` without a timestamp never invents a revision-publication time. Every version keeps
its exact source bytes, status, digest, rule hashes, source dataset and parser identifier.
Corrections receive distinct revision identities. Repeated unchanged observations retain
the earliest authentic receipt; model fitting selects the latest revision actually known
at its cutoff. Original forecasts, decisions and frozen temporal boundaries stay unchanged.

The operator initiates each acquisition explicitly. Requests accept a UUID idempotency key
and an existing dataset ID only. Reusing the key returns the same request without network
work; another collection needs a fresh key. Jobs are limited to eight dates, eight queued or
running requests, 2 MB per response, 15-second HTTP timeouts and a 120-second overall
acquisition deadline. The client disables ambient proxies, credentials, redirects and cookie
forwarding. Shutdown cancels the active task. Receipts saved before interruption survive;
startup marks queued/running work interrupted and never silently retries it. A terminal
batch may contain both usable receipts and explicit missing-receipt refusals.

Label batches and request state live under `runs/weather-labels/`. Immutable research
snapshots copy compatible batches and exact raw JSON bodies. Loading a snapshot reparses
those bytes and verifies the original contract bindings, audit, observations and checksums
offline. Protected events from earlier snapshots and model/source protections remain
excluded; protected labels cannot enter fitting or evaluation. Acquisition also observes the
workspace's previously frozen protections when selecting targets. New dataset freezes
reapply protections even to an earlier acquisition. Browser inspection is for the local
operator; bounded research tools continue withholding label values and protected rows.

The existing workspace snapshot/restore includes and validates the label store. Restoring
never fetches sources. Up to 128 label batches enter one dataset; larger collections require
an operator-reviewed partition. This first adapter supports two existing weather stations,
not a new market family. The portal schema can change and fail closed. More independent
source-matched dates, temporal validation, certified fees, external-provider verification and
independent V1 review are still required.

Executed evidence and repeatable commands are in the
[October 31 bundle](../data/weather-label-review/20261031/README.md). The Playwright procedure
`frontend/browser/weather-labels.spec.cjs` uses managed Chromium, actual localhost listeners,
new public acquisition, downloads and restart. Controlled source/revision/error cases are
separate software tests and are never represented as new authentic observations.
