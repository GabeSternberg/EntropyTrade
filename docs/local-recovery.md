# Local operation and workspace recovery

October 29 provider continuation: the [current locked-install browser evidence](../data/provider-review/20261029/README.md)
executes this recovery procedure through Playwright-managed Chromium and the real localhost
workers. It also verifies provider result/failure snapshots and cancellation/restart without
automatic billable retries. The earlier environment-denial record below remains historical;
use the current bundle and [V1 matrix](v1_acceptance.md) for latest acceptance status.

Workspace snapshot/restore is an **offline local maintenance operation**. Stop the web
server with Ctrl-C and wait for its workers to exit. Never copy a running workspace by
hand. Server startup, snapshot and workers share an exclusive lease; workers retain the
lease after a parent crash until they exit. A busy lease refuses maintenance/startup.
No submission permission, risk setting or model promotion is added by recovery.

From the repository root, after `uv sync --locked`:

```bash
# Use a new archive name and keep the returned SHA-256 with your private backup.
.venv/bin/python -m entropytrade.api.recovery snapshot \
  --workspace data/cache/workbench --archive data/recovery/workbench-001.zip

# The destination must not exist, including as an empty directory or symlink.
.venv/bin/python -m entropytrade.api.recovery restore \
  --archive data/recovery/workbench-001.zip --workspace data/cache/workbench-restored
.venv/bin/python -m entropytrade.api.server --workspace data/cache/workbench-restored
```

Paths stay within this repository; workspaces stay under `data/cache/`. Existing archives
and destinations are refused. The archive includes consistent SQLite backups of jobs and
the shared lineage registry, every `runs/` and `shadow/` file and empty data directories.
It excludes transient SQLite sidecars, `.writer.lock` and the Matplotlib runtime cache.
Unexpected root entries, links and special files are refused, rather than silently lost.
Opaque model/MLflow artifacts are copied as bytes; restore does not deserialize executable
models. Research configurations and bundled recorded datasets come from the installed
project, not the workspace archive. Keep the project version with the backup.

The manifest records SHA-256, sizes, directories, database counts, format version and
`uv.lock`/`pyproject.toml` hashes. Current limits are 100,000 files/directories, 256 MiB per
file and 2 GiB total files. Restore stages verification before publishing a destination:
ZIP members, paths/types, checksums, database integrity/schema/references, research registry
lineage, strategy/model binding identities, contiguous cycle sequences, result digests
and referenced artifacts must agree. Missing evidence and incompatible locks fail closed.
Checksums detect corruption; they do not authenticate an archive supplied by another party.
Snapshots contain private prompts and evidence. Archive files are created with mode 0600.

Original receipt/source clocks, holdout boundaries, model parameters/calibration clocks,
completed cycle bytes and unresolved reservations remain intact. Normal startup interrupts
unfinished research/cycles, preserves paused monitors and schedules active shadow monitors
using their existing schedule and fresh receipt directories. It does not manufacture missed
polls or rewrite old source availability. A recovered monitor can still be model/fee blocked.
SQLite backup/open may change database file layout/journal mode; logical rows and original
evidence bytes are the preservation contract. Embedded absolute lineage paths remain the
original recorded values; this is not a migration of an external MLflow installation.

Legacy monitors already migrated by the tracking store may have a SQL NULL model binding.
Recovery preserves that NULL exactly, even if a model reference/export exists; it never
creates a binding or enables scoring. Normal startup recovery and resume retain the
`No frozen model binding` refusal. Non-null malformed values (including JSON `null`),
bad binding hashes and inconsistent bound/blocked models remain rejected. The
[controlled correction regressions](../data/local-operation-review/20261029-legacy-null-binding/README.md)
verify original logical rows, evidence bytes and clocks, startup interruption/fresh-cycle
recovery, resumed scoring refusal and JSON decision replay. These checks do not pass the
outstanding browser or full-suite acceptance steps below.

The [executed proof in the locked installation](../data/local-operation-review/fresh-authentic-current-source/verification.json)
restores one real research run, one paused monitor and two authentic completed cycles.
The installed CLI round trip and both 24-decision cycle replays pass. The original artifact hashes, database rows,
paused export and original clocks match. It creates no new source receipts or empirical
model evidence. To reproduce on another stopped, paused workspace:

```bash
.venv/bin/python tools/verify_recovery.py \
  --workspace "$PWD/data/cache/workbench" \
  --restored "$PWD/data/cache/recovery-proof" \
  --output "$PWD/data/local-operation-review/recovery-proof"
```

The offline verifier first requires an existing source database under `data/cache/`,
then snapshots and validates it under the exclusive lease before constructing application
stores. It holds that same lease through source inspection and source/restored comparison;
there is no nested lease acquisition. A separate destination lease covers restored-store
initialization, logical-row comparison, startup recovery and replay. Busy, missing,
out-of-cache and incompatible-schema sources cannot be initialized or migrated by this
verification tool. A read-only SQLite WAL backup can create transient WAL/SHM sidecars for
an existing valid source; those are runtime files, not a schema migration or new database.

For the browser-independent recovery gate in an already installed checkout:

```bash
python3 tools/recovery_gate.py \
  --output "$PWD/data/local-operation-review/NEW-ISOLATED-REVIEW"
```

This runs Ruff/format, strict mypy, frontend assertions and 13 focused pytest files in
separate processes with explicit deadlines, retaining source fingerprints, logs and JUnit.
It includes both existing listener files and `test_recovery_listener.py`: an actual
localhost server and unmodified research/shadow subprocesses complete recorded research,
download results, stop an active cycle, snapshot/restore, compare paused downloads, collect
a fresh cycle, cancel research and restart. Public polls retain actual receipts or honest
failures; they never substitute controlled inputs. Three existing asynchronous R4 workflow
cases are explicitly deselected in this focused gate. It does not launch a browser,
retry the known full-suite stall, or establish a new clean install or V1 release pass.

## Locked installation and real browser acceptance

The one-command acceptance driver exports explicit product/test/data roots into a new
installation, omitting Git/supervisor controls, credentials, existing environments and old
workspaces. It records source hashes, lock checks, package inventory, gates and exit codes.
It runs `uv sync --locked`, Ruff lint/format, strict mypy, frontend checks, pinned `npm ci`,
the supported Chromium installer, selected-browser discovery, an OS socket preflight,
actual Playwright interactions and the full pytest suite. Default browser coverage includes
research/recovery, controlled provider integration, authentic weather history, **both paper
procedures and operator alerts**. Discovery has separate reports and never counts as page
interaction. Browser execution stops after the first failure; denied socket capabilities
stop before browser launch or pytest, retaining an explicit blocked receipt and unexecuted
checks. A successful socket preflight alone cannot certify Chromium or any workflow.
Use Python 3.12+, uv, Node/npm and a machine permitting localhost sockets and Chromium:

```bash
python3 tools/local_acceptance.py --output "$PWD/data/local-operation-review/NEW-NAME"
```

For an offline machine with already provisioned package artifacts, optional
`--uv-cache-seed /path/to/uv-cache`, `--npm-cache-seed /path/to/npm-cache` and
`--chromium-seed "$PWD/frontend/browser/.browsers"` copy only the package artifact caches
and the Playwright-managed browser distribution. They do not reuse a virtual environment,
personal Chrome, provider/exchange configuration or credentials. The recorded provisioning
mode distinguishes an offline cached install from an uncached download. `--prepare-only`
provisions/checks and discovers selected browser tests without probing sockets, launching
Chromium or running the full suite. It explicitly reports these checks as unverified and
keeps `acceptance_complete=false`. Use it after a recorded environment denial; preparation
is not operating acceptance. `--check-environment` separately reports the exact localhost
and asyncio socketpair capability failures without browser launch or permission changes.

`frontend/browser/recovery.spec.cjs` submits a synthetic weather idea and a recorded real
idea through the form, inspects all result tabs and downloads, starts/pauses shadow, stops
an active monitor, snapshots/restores, inspects restored history/paused bytes, observes a
fresh active cycle, cancels research and restarts again. It compares frozen bindings,
download hashes and receipt clocks. No response interception, clock injection or replacement
worker is used. A very fast real request may complete during shutdown; either that exact
result or its actual interrupted state must survive. Controlled tests separately prove
in-flight recovery and nonempty reservation/risk behavior without claiming real probabilities.

**Earlier environment result (superseded by the current bundle):** the locked offline install and non-browser checks pass;
Chromium launch fails at `third_party/crashpad/crashpad/util/linux/socket.cc:45` with
`setsockopt: Operation not permitted (1)` and SIGTRAP, before any page interaction. The
failed [Playwright report](../data/local-operation-review/20261029-recovery-final/browser/playwright-results.json)
and trace are retained; no new screenshot or browser pass is claimed. The full suite
stalls in the existing collector reconnect test; its 45-second diagnostic stack and
120-second external deadline are retained in the [test log](../data/local-operation-review/20261029-recovery-final/pytest.log).
The stack alone does not prove the cause of that stall. The earlier unbounded attempt was
interrupted and is also incomplete. No denied browser launch was retried or bypassed.

The current bundle executes the browser steps; independent supervisor review must still
inspect its screenshots, downloads, listener/worker logs and final complete-suite report,
then cross-check [V1 acceptance](v1_acceptance.md). Its external-provider check remains
blocked without separately authorized research credentials. No real-data empirical release
gate is satisfied by the controlled or synthetic software procedures.
