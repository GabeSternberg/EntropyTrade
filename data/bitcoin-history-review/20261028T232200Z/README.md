# Bitcoin retained-history implementation review — October 28

**Intermediate implementation; V1 and empirical second-family acceptance remain incomplete.**
The starting checkout was clean on `supervisor/20261028-191140`, HEAD `9ba9b3d`.
All changes are uncommitted for supervisor review. No branch, index, commit, merge, push,
supervisor control file, credential, trading permission or risk cap was changed.

The [operating guide](../../../docs/bitcoin-history.md) describes the CLI, website mode,
fixed calendar policy, binary-target semantics and current limitations. Numeric fitting
tests use explicitly synthetic samples. Actual retained receipts establish only the
replay/insufficiency result below. No empirical model accuracy or return is claimed.

| Check | Executed result | Durable receipt |
| --- | --- | --- |
| Locked environment verification | `uv sync --locked --offline`: 121 resolved, 117 checked; existing environment, not a clean install | [log](locked-sync.log) |
| Ruff lint/format | Passed on current backend source | [log](ruff-reviewed.log), current source fingerprints in `source.json` |
| Strict mypy | Passed, 480 files | [log](static-types-final.log) |
| New Bitcoin tests | 17 passed in 4.60s | [log](bitcoin-tests-reviewed.log) |
| Frontend presentation checks | 12 passed, zero failures/skips; direct Node execution of `node:test` assertions | [log](frontend-direct.log) |
| Test collection | 751 collected | [log](collection-final.log) |
| Whole `make check` | Ruff/format/mypy passed; pytest stalled at the existing collector reconnect test and was interrupted | [log](make-check-final.log) |
| Collector diagnosis | 20-second stack dump; 45-second deadline plus five-second kill grace expired, exit 137 | [log](collector-diagnostic.log) |
| Independent grouped checks | 45-second dump stalled in existing R4 research/AnyIO workflow; interrupted | [log](independent-tests.log) |
| Additional bounded per-file checks | 207 files attempted, 198 completed successfully; 660 reported test passes, three listener failures, eight file timeouts; two previously stalled files not rerun | [receipt](per-file-checks.json), [runner](run_file_checks.py), [logs/JUnit](per-file/) |
| Browser installation | Playwright-managed Chromium installation command exited 0 | [log](chromium-install.log) |
| New browser acceptance | Failed before page interaction: Chromium `setsockopt: Operation not permitted (1)`, `SIGTRAP`; no retry, screenshots or page pass claimed | [log](browser.log), [JSON](browser/playwright-results.json), [JUnit](browser/playwright-results.xml), retained trace |

The three listener failures originate in `socket.socket(...)` with `PermissionError:
[Errno 1] Operation not permitted`. Eight additional files reached the per-file runner's
40-second deadline; their original assertions and 25-second faulthandler dumps are
retained. The two files already stalled in earlier attempts were not rerun. These
additional checks are **not a passing full-suite gate**. Root causes of the stalls remain
unresolved. After this sweep, final self-review added rejection of events spanning multiple
target dates; current static checks, all 17 Bitcoin tests and the real offline workflow
were rerun. The broader sweep predates that guard, with source fingerprints retained
separately in `source-at-sweep.json`. No test assertions, risk limits or warning policies were weakened. The
runner bounds external test processes and reports nonzero exits without substituting data.

An initial lint attempt found one long line, which was fixed before final checks.
`frontend-current.log` retains an unsupported Node flag attempt; `frontend-direct.log`
records the actual twelve passing in-process checks. The earlier completed `real-offline-history` replay remains a receipt of its own source
state. Old partial attempts are retained,
not silently replaced by passing receipts.

## Real retained-data replay

The executed command was:

```bash
.venv/bin/entropytrade bitcoin-history \
  --capture data/workbench-review/20261026T203717Z/browser-attempt-2/runs/public-bitcoin/public \
  --capture data/workbench-review/20261025T163400Z/public-bitcoin/public \
  --no-fetch --output data/bitcoin-history-review/20261028T232200Z/real-reviewed-history
```

It completed with two immutable copied source captures, **four recognized event samples
across three target dates**, zero finalized labels, zero probabilities, no forecast scores,
no trading scenarios and no P&L. Both typed candidates returned `INSUFFICIENT_DATA` with
the explicit 40-fit-event/20-date/receipt-time target gate. The history manifest freezes
anchor `2026-10-25`, fit cutoff `2026-12-24`, and protected holdout start `2027-01-23`.
No target dates have reached that protected boundary. Feature identities were independently
reloaded and checked against the current implementation and experiment artifacts.

`fetch_enabled=false`, zero new outcome reads and four deferred targets are explicit in
[the manifest inputs](real-reviewed-history/history/outcomes/receipts.json).
[Full stdout](real-reviewed-history.log), raw input copies and their manifests, research
proposals/audit, model refusal artifacts, experiment result/report, local registry and MLflow
artifacts remain in [the completed run](real-reviewed-history/). These are real historical
receipts from earlier captures, not fresh successful ingestion or fabricated history.

The earlier credential-free feasibility probe failed DNS resolution on three public GETs.
The fresh `real-history` attempt produced no HTTP receipts or completed snapshot/result
before interruption; its partial files and `real-history-run.log` remain separately retained.
The empty `real-history.log` came from an initial module invocation without an entrypoint;
it performed no workflow and is not acceptance evidence.

## Outstanding acceptance

The supervisor should independently review source and full test failures, then execute
`make check` and the new Playwright history procedure in a permitted environment. The
browser harness opens an actual localhost listener, submits through the form, inspects
all tabs/downloads, restarts the actual server and compares retained downloads. Its
empty-history workflow does not establish successful live acquisition. An actual populated
history workflow and successful official result reconciliation still need verification.

Real probability evaluation requires sufficient original point-in-time captures and official
targets received before the frozen fit cutoff, plus independent validation dates. The
current narrow strictly-above profile may also fail the both-outcomes requirement; no
rule, independence, clock or minimum-evidence gate may be relaxed to obtain a model.
Exceptional resolution paths, sized books and historical fee evidence remain unverified,
so execution stays closed. Continuous paper/shadow and the V1 release matrix remain
subsequent reviewed work. No V1 completion or next major milestone is authorized by this bundle.

`validation.json`, `source.json` and `SHA256SUMS` bind current source/check outcomes and
all retained files. `prior-checksums.log` and `prior-verification.json` retain the prior
workbench index check, including seven absent transient lock/WAL/SHM files that are not
tracked in this checkout. All readable indexed prior files matched their hashes. No
missing transient file was fabricated or recreated. No Git write was performed.
