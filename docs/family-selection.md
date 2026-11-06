# Market-family screening

`entropytrade family-screen` compares Kalshi series from retained public catalog receipts.
It supports the user's decision on the second major market family; it never chooses one.
Implementing a new family still requires written user approval (see
[project context](../PROJECT_CONTEXT.md)).

## What it reports

For each series, `backend/src/entropytrade/families/screening.py` reports:

- coverage: markets, events, close dates, and the first and last close dates;
- labels: finalized YES/NO contracts, plus the events and dates in which every contract is
  finalized;
- structure: market and strike types, and the median number of contracts per event;
- activity: the share of contracts with any traded volume, total lifetime volume and the
  median volume per event;
- rules: the number of distinct rule wordings, with dates and numbers masked, and the
  verbatim earliest- and latest-closing `rules_primary` text;
- series metadata, when a `/series/{ticker}` receipt is supplied: title, category, frequency,
  fee type and multiplier, named settlement sources and contract URL;
- `label_history_minimum`: whether finalized labels reach the existing binary-family
  fitting floor of 40 events on 20 dates with both outcomes. This floor matches
  `bitcoin_models`.

The report has no wall-clock fields, and every input carries its SHA-256. Re-running on the
same receipts gives byte-identical JSON.

## Running it

```bash
# Offline, over retained receipts (files holding {"markets": [...]}, a bare list or {"series": {...}})
uv run entropytrade family-screen --receipt a.json --receipt b.json --output screen.json

# Read-only catalog fetch into a NEW directory, then screen what was fetched
uv run entropytrade family-screen --fetch-series KXEXAMPLE --fetch-dir data/cache/catalog-YYYYMMDD
uv run entropytrade family-screen --fetched data/cache/catalog-YYYYMMDD --output screen.json
```

### Fetch limits

Fetching sends unauthenticated GET requests to `api.elections.kalshi.com` and nowhere
else. The only paths allowed are `/series/{TICKER}`, `/markets` and `/historical/markets`.

The transport is the existing `BoundedTransport`, so its limits still apply:

- at most 20 requests per run;
- at most 2 MB per response and 12 MB per run;
- no redirects and no authentication headers;
- the process environment, including any proxy, is ignored.

Each series may fetch 1–5 pages per endpoint.

Every response is kept under `raw/`, including failures, which are saved as `*.error.json`.
`manifest.json` records each response's URL, status, receive time, size and hash. Transport
errors are recorded in the manifest and stop that series; nothing is retried.
`--fetched` checks every file against its manifest hash and skips non-200 responses.

### Refusals

The screen refuses instead of guessing when:

- a receipt is not JSON, or has an unknown shape;
- a market has no ticker or event ticker;
- a numeric field is negative or invalid, or a timestamp is invalid;
- series metadata conflicts between receipts;
- a fetched file's hash does not match its manifest;
- the output path already exists.

## Handling repeated receipts of one ticker

Every supplied update clock is validated, including unique and superseded observations.
Dated revisions are resolved in clock order before observations without clocks are merged;
changing receipt-file order cannot erase an unclocked final result. Lifetime volume is
compared across both legacy integer and fixed-point catalog fields.

- **Different `updated_time` values:** the later receipt wins, and the ticker counts toward
  `revised_tickers`.
- **No ordering clock:** this happens when both receipts share an `updated_time`, for
  example live and historical endpoints or repeated polls, where open interest, quotes and
  cumulative volume still differ. The receipts are merged and counted in `merged_tickers`:
  - identity fields (event, close time, market and strike type, `rules_primary`) must
    agree;
  - two different final results are refused;
  - a final result is kept over an unresolved one;
  - lifetime volume, which never decreases, keeps its maximum.

## Limitations

The screen cannot answer several of the selection criteria:

- **Point-in-time history:** catalog fields describe markets as observed when each receipt
  was fetched. They show that labels exist, not that predictors were available at decision
  time.
- **Execution costs:** lifetime volume is not executable depth. The fee type comes from
  series metadata, not from certified effective fees.
- **Resolution semantics:** rule text is shown verbatim, and no settlement authority is
  inferred from it. Wording changes within one series, such as KXHIGHPHIL below, need to be
  reviewed by a person.
- **Modeling feasibility and realistic validation:** these still need the existing
  experiment, holdout and fee gates.

## Retained-receipt screen (2026-11-05)

The only results so far come from receipts already in the repository. See the
[exact command and report](../data/family-screening-review/20261105/README.md).

| Series | Markets | Events | Close dates | Labeled events/dates | YES/NO | Traded share | Volume | Rule wordings | Label minimum |
|---|---:|---:|---|---|---|---:|---:|---:|---|
| KXBTC | 478 | 5 | 2026-10-25…2026-10-30 (4) | 0/0 | 0/0 | 0.197 | 184867.09 | 3 | not met |
| KXHIGHPHIL | 4098 | 683 | 2024-11-21…2026-10-04 (683) | 681/681 | 681/3405 | 0.987 | 42112545.33 | 18 | met |
| KXMVECROSSCATEGORY | 0 | 0 | — | — | — | — | — | — | no market receipts |
| KXNHL | 0 | 0 | — | — | — | — | — | — | no market receipts |

What the table shows:

- **KXHIGHPHIL.** The retained catalog has enough finalized labels to *attempt* a fit, but
  the rule wording changed:
  - the earliest retained rule names the NWS Daily Climate Report;
  - the latest names The Weather Company (CLIPHL), which matches the series metadata.

  Older labels therefore do not share current settlement semantics. The existing weather
  label gates already treat NWS and Weather Company values as different sources.
- **KXBTC.** These captures hold only five events that were open when captured, with no
  finalized results. The separately reconciled Bitcoin history, with four finalized
  events, is documented in [bitcoin-history.md](bitcoin-history.md).
- **KXNHL and KXMVECROSSCATEGORY.** Only series metadata (fee types) is retained, so their
  markets cannot be screened without a catalog fetch.

## Decision procedure (needs user approval)

1. In an environment where `api.elections.kalshi.com` is reachable, fetch three to six
   candidate series from categories distinct from daily temperature highs. More KXHIGH
   cities would be the same family. Confirm each ticker from a catalog receipt; do not take
   one from memory.
2. Screen those receipts together with the retained weather and Bitcoin receipts.
3. For each candidate, review:
   - the verbatim rules and named settlement source;
   - whether a public, point-in-time predictor exists that is recorded independently of
     Kalshi;
   - label balance and frequency;
   - fee type;
   - traded share.
4. Record the user's written choice before any family-specific implementation begins.

Neither this screen nor its retained results establish predictive skill, effective fees,
realistic validation or profitability.
