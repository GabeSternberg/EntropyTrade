# Family-screening evidence — 2026-11-06 (GitHub-hosted runner)

Branch `claude/vibrant-bohr-etkgi2`, stacked on PR #4 (`claude/vibrant-bohr-0m71vf`).
**V1 remains incomplete.** This evidence supports the user's second-family decision. It does
not make that decision, and no family-specific code was written.

Cloud sessions cannot reach `api.elections.kalshi.com` (issue #3), so both runs used the new
`family-catalog` workflow on GitHub-hosted runners. Every request was an unauthenticated GET
through the existing `BoundedTransport`. The full retained receipts are in each run's
`family-catalog` artifact (90-day retention). Cloud sessions cannot download artifact blobs,
so this directory keeps the complete job logs, which include every listing row, screen row
and file SHA-256.

## Files

| File | Contents |
|---|---|
| `discovery-job-127651155134.log.gz` | Full job log of discovery run [42144061322](https://github.com/GabeSternberg/EntropyTrade/actions/runs/42144061322): the complete 3,646-row series listing and file hashes. |
| `discovery-counts.txt`, `discovery-hashes.txt` | Counts and SHA-256 of every retained discovery file (manifest, 9 receipts, listing). |
| `screen-job-127652531926.log.gz` | Full job log of fetch-and-screen run [42144482210](https://github.com/GabeSternberg/EntropyTrade/actions/runs/42144482210). |
| `screen-table.md` | The Transportation listing from that run, then the screen table. |
| `screen-calls-and-rules.txt` | Per-series call statuses/bytes, and verbatim earliest/latest rule text and settlement sources. |
| `screen-hashes.txt` | SHA-256 of every retained fetch/screen file. |

## Run 1: series discovery (`push`, default 12 categories)

- 12 requests. 9 were usable. **Entertainment, Politics and Sports** exceeded the 2 MB
  per-response budget and are recorded as unusable. They were not retried, and the budget
  was not raised.
- 3,646 series were listed. Counts by the series' own `category` field: Financials 1,130,
  Economics 866, Climate and Weather 501, Science and Technology 389, Crypto 294, Companies
  192, World 137, Health 94, Transportation 34, others ≤ 5.
- Counts by frequency: one_off 1,180, custom 969, annual 482, monthly 419, daily 318,
  weekly 162, hourly 72, fifteen_min 28, quarterly 16.

## Run 2: fetch and screen six candidates (`workflow_dispatch`)

The six candidates were chosen from the run-1 listing, not from memory. They are daily
series from non-temperature categories whose settlement source is a public publisher
independent of Kalshi: `KXTSA KXAAAGASD KXTNOTED KXTXERCOTPEAKD KXSOFRD KXEURUSDD`. Choosing
which tickers to *screen* is a research step only. It is not a family selection.

There was one bounded fetch per series, with at most 3 pages of 200 markets per endpoint.
All 27 catalog responses (plus one Transportation listing) returned HTTP 200. The first dispatch ([42144192720](https://github.com/GabeSternberg/EntropyTrade/actions/runs/42144192720))
fetched successfully, but its combined screen refused a non-catalog fee file because my
workflow glob was too broad. That failure is retained and the glob is fixed.

| Series | Markets | Events | Close dates | Labeled events/dates | YES/NO | Traded share | Rule wordings | Label minimum |
|---|---:|---:|---|---|---|---:|---:|---|
| KXAAAGASD (AAA US gas price) | 1200 | 71 | 2026-08-01…2026-11-06 | 70/70 | 535/648 | 0.982 | 2 | met |
| KXSOFRD (NY Fed SOFR) | 380 | 66 | 2026-08-06…2026-11-09 | 64/64 | 56/308 | 0.753 | 4 | met |
| KXTNOTED (Treasury 10Y par yield) | 600 | 40 | 2026-04-16…2026-07-01 | 40/40 | 40/560 | 0.445 | 6 | met |
| KXTXERCOTPEAKD (ERCOT daily peak load) | 701 | 40 | 2026-08-29…2026-11-07 | 38/38 | 302/361 | 0.796 | 3 | not met (38 < 40) |
| KXTSA | 0 | — | — | — | — | — | — | no markets |
| TSA (legacy, returned by the KXTSA historical query) | 81 | 79 | 2021-07-21…2021-10-26 | 79/79 | 32/49 | 0.988 | 9 | met |
| KXEURUSDD | 0 | — | — | — | — | — | — | no markets |
| KXHIGHPHIL (retained receipts, reference) | 4098 | 683 | 2024-11-21…2026-10-04 | 681/681 | 681/3405 | 0.987 | 18 | met |

## How to read this

- **Coverage is truncated.** The 3-page cap stopped KXAAAGASD on both endpoints at full
  pages, and other series may also have more history than shown. Counts are lower bounds for
  the fetched window, not complete histories.
- **KXTNOTED** returned no live markets, and its fetched history ends on 2026-07-01. It may
  no longer be listed. A newer ticker would need to be confirmed from a listing.
- **KXTSA** has series metadata but no markets on either endpoint. The `TSA` rows are 2021
  legacy markets. They do not share the current series' metadata and would not supply
  current-semantics labels.
- **Settlement sources (verbatim from the series metadata).** These are all public
  publishers independent of Kalshi:
  - AAA gasprices.aaa.com
  - NY Fed reference rates
  - Treasury daily par yield curve
  - ERCOT NP6-346-CD
- Whether a **point-in-time predictor** can be recorded for any of them, and what its
  publication clock is, has not been established. The same applies to effective fees (all are
  `quadratic`, which is uncertified) and executable depth. The screen does not measure these,
  and the existing experiment, holdout and fee gates still apply.
- "Label minimum met" means only that enough finalized labels exist to *attempt* a fit
  (40 events on 20 dates, both outcomes). It is not predictive skill, and it is not
  profitability.

## Decision still needed (user)

Per [family selection](../../../docs/family-selection.md), the user should review these rows
and record a written choice before any family-specific implementation begins. The agent
will not select a family.
