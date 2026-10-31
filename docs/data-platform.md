# Read-only collection and point-in-time datasets

R1 adds runnable local data commands. No command submits, cancels or modifies exchange
orders. Public REST acquisition is verified on actual Philadelphia/Chicago contracts.
Authenticated WebSocket operation remains unverified here because no read key is configured.

## Continuous collector

Create a separate Kalshi API key with **only `read` scope**, in the intended environment.
Do not reuse an execution key. The collector verifies the selected key's scopes through
the SDK and refuses write-capable or unverifiable keys. Key inventory is not recorded.
Store the PEM outside the repository, with mode 600. The process reads only the dedicated
variables below; it does not use `KALSHI_KEY_ID` or `KALSHI_PRIVATE_KEY_PATH` as fallbacks.

```bash
uv sync --locked
export ENTROPYTRADE_READ_KEY_ID='<read-only key id>'
export ENTROPYTRADE_READ_KEY_PATH='/private/path/kalshi-read.pem'
chmod 600 "$ENTROPYTRADE_READ_KEY_PATH"
uv run entropytrade collect --config configs/data/collector.json \
  --db data/raw/kalshi/weather.sqlite --environment production
```

Use `--environment demo` with a demo read key. Ctrl-C/SIGTERM stops cleanly; `--seconds 120`
provides a bounded session. Restart the same command and database. A database is bound to production, demo or replay;
environments cannot be mixed, and only production-bound live sessions are certified inputs. An advisory lock refuses
a second collector writer. No secret is put into a configuration file or an artifact.

Configure series/events, maximum markets, metadata refresh, per-book age, health interval,
retry budget and disk budget in `configs/data/collector.json`. REST discovery paginates.
The SDK handles transport, authentication and wire validation; our existing book/sequence
boundary consumes raw frames before SDK dispatch could discard duplicate/gapped messages.
Book/trade subscriptions select tickers. Lifecycle is global (the reference says ticker
filters are unsupported); raw lifecycle receipts preserve channel continuity, while only
monitored books are held in memory. Metadata/lifecycle changes invalidate affected books
and force rediscovery/resubscription. Periodic refresh also discovers newly active markets.

```bash
uv run entropytrade health --db data/raw/kalshi/weather.sqlite
```

JSON health distinguishes connection, per-market stale state, sequence gaps/unsequenced
messages and report age. A quiet book is not refreshed by another market's trade. A gap,
malformed message, lifecycle change or expired book closes the session and requires fresh
snapshots. Missing initial snapshots also fail closed. Backoff is bounded, with a finite
consecutive-failure budget. A historical gap remains audit evidence after recovery; a
fresh book does not repair lost history. Unsequenced messages are retained, but their
completeness cannot be proven from sequence numbers. No backfill is silently declared complete.

SQLite WAL uses FULL synchronous commits. Each message commits raw receipt, normalized
fact and integrity effects atomically. Session UUID + receipt ordinal identifies deliveries;
normalized frame identity also includes semantic content so conflicting sequence payloads
remain inspectable. Trades retain exchange trade IDs. Receipt time is captured before
JSON decoding; exchange event time and ingestion time stay separate. Market observations
link to retained HTTP receipts, and repeated metadata observations do not invent rule versions.

Schema v2 migrates v1 frames into an arrival-ordered table and preserves `legacy_frames_v1`.
Legacy session/ingestion provenance is explicitly unknown, and legacy rows are not certified
as newly collected data. Interrupted sessions remain unclosed; stale health exposes a
crash. A dataset reader uses a consistent read-only SQLite snapshot and invalidates books
at disconnect boundaries. Open sessions are certified only through committed receipts.

Memory is bounded by the configured market universe and socket lifetime; there is no
unbounded application message queue. The disk cap includes DB/WAL/SHM and stops collection
without deleting evidence (one in-flight message/checkpoint can exceed the threshold).
Archive a **closed**, checkpointed database and start a new file to continue. There is no
automatic destructive retention policy. SDK/SQLite or filesystem failures must be investigated
before restarting; collection does not infer missing data across downtime.

## Verification without credentials

The committed wire fixture is synthetic and is explicitly marked `replay` in sessions;
dataset readers exclude replay sessions from certified market data.

```bash
uv run entropytrade collect --config configs/data/collector.json \
  --db /tmp/weather-replay.sqlite --replay-wire backend/tests/fixtures/collector-wire.jsonl
# Run the same command again, then inspect persistence:
uv run entropytrade health --db /tmp/weather-replay.sqlite
```

The R1 CLI demonstration retained 7 receipts/7 normalized frames on the first run and
14/14 after restart, with zero unclosed sessions. Repeated normalized trade IDs remain
idempotent; separate observations/sessions remain auditable. Tests additionally exercise
a dropped connection, fresh subscriptions, sequence collisions/gaps, stale books,
lifecycle invalidation, malformed/conflicting input, v1 migration and abrupt process exit.
These establish simulated behavior, not a real exchange handshake or hours-long uptime.

Minimal remaining external verification: configure a read-only key, run for hours on an
active series, interrupt/restart the same DB, inspect health/session/effect history and
build a dataset using `--recorder`. No production trading key or order permission is needed.

## Generic daily-high dataset

The sample configuration covers Philadelphia and Chicago, September 1–3, 2026, at 15:00 UTC.
Cities/stations/timezones, series, dates, UTC decision times, source selection and maximum
book age are data configuration. No exact strike is requested. Acquisition queries daily
series event IDs and consumes their actual listed contracts, including all returned buckets.
Missing events remain coverage gaps. This daily event-ID convention is a family adapter,
not an assertion that arbitrary Kalshi event tickers follow the same convention.

Rebuild the committed real-data demonstration without network or credentials:

```bash
uv run entropytrade dataset --config configs/data/weather.json \
  --source data/public --source data/r1-source --output data/normalized/weather
```

Or acquire another immutable public source snapshot and build it in one command:

```bash
uv run entropytrade dataset --config configs/data/weather.json --source data/public \
  --fetch data/raw/weather-source-new --output data/normalized/weather
```

The fetch directory must not exist. Failures/raw responses remain evidence; an unsuccessful
or interrupted acquisition is never overwritten. REST requests use the SDK boundary,
conservative anonymous pacing and bounded pagination. Live/historical endpoints are both
queried; mutually exclusive event/series filters are handled correctly. SDK 17.1.0 requires
an unused liquidity field absent from observed responses; the boundary preserves its
absence as None. Its pinned `_list` pagination seam uses this narrow compatible model.
Recheck that adapter before SDK upgrades. No liquidity, price, strike or label is invented.

Output is an immutable `<output>/<dataset-version>/` directory containing:

- `rows.parquet`: contract/decision rows, strikes/rules, strict features, state, targets,
  provenance and quality flags. Money/numeric JSON uses exact decimal strings.
- `observations.parquet`: normalized source evidence, including uncertain weather values,
  their units/valid times, clocks and raw references; uncertainty is not a strict feature.
- `manifest.json`, `coverage.json`, `checksums.json`: input/code hashes, coverage by city,
  missing data and artifact integrity. `build.json` records build time/source roots outside
  the deterministic manifest. Identical frozen inputs/code/config reproduce the version,
  row hash and Parquet artifacts; refreshing sources intentionally changes the version.

Add `--recorder path.sqlite` to include live-mode metadata/books from a v2 recording.
The source snapshot digest includes committed receipts, metadata, integrity effects and
session boundaries. Demo, replay and unlabeled environments are excluded from certified
production market data. Replays and legacy frames with unknown provenance are excluded.

`entropytrade inspect <version-directory> --day 2026-09-01` shows contracts, existence
proof, rule availability, strict features, execution fidelity and eventual outcomes.
For larger queries use PyArrow Parquet filters (or your own DuckDB installation):

```python
import pyarrow.parquet as pq

rows = pq.read_table(
    "<version-directory>/rows.parquet", filters=[("target_date", "=", "2026-09-01")]
)
print(
    rows.select(
        [
            "market_ticker",
            "decision_time",
            "features_json",
            "historical_context_json",
            "outcome",
            "quality_json",
        ]
    ).to_pylist()
)
```

## Strict information boundaries

A normalized weather source can supply `observations.jsonl` following `data/schema.py`:
source/entity/variable/valid date/value/unit, actual issue/publication/availability/receipt/
ingestion/revision times where known, timing basis, evidence and raw-file reference/hash.
`provider_publication` requires publication evidence; `received` cannot precede receipt.
Unknown/assumed clocks never enter `features_json`. Legacy hourly valid times remain UTC;
R2 must aggregate them using each contract location’s local-day definition, not a UTC daily max. Observation/settlement-role values
never become forecast features. Revisions available after the decision cannot alter it.

Actual receipt-backed market captures are distinguished from legacy manifest fetch
conventions. Exchange creation times provide retrospective contract-existence evidence;
late snapshots cannot prove historic rule versions or a complete historical universe.
Rules retain their actual source text/basis. Eventual labels come only from finalized
Kalshi YES/NO contract results, not a substituted weather observation. A missing or
nonfinal result stays unresolved; the Weather Company and CLI are not interchangeable.

`market_state_json` contains receipt-backed state. `historical_context_json` contains
uncertified historical candles/prints. `execution_fidelity` reports what evidence exists;
`executable` additionally requires fresh uncrossed sized books, known rules/semantics and
an open contract. It describes evidence eligibility, not a guaranteed fill. Missing depth
is never replaced by volume. See [results](results.md) for the real sample's limitations.
