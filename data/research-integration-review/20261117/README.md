# End-to-end research readiness acceptance

**No authentic candidate currently qualifies for paper trading.** The supported lifecycle
works with controlled evidence; fresh authentic public data reaches materialization and
truthful modeling refusals. Windows, canonical collector and private research storage were
not accessed. See the [concise readiness report](../../../docs/research-integration-readiness.md)
and [separate safety review](review.md).

## Accepted source and checks

Code `25cdeb1be70d045b5506495cfc21d5c74c1d16c7`; PR [#35](https://github.com/GabeSternberg/EntropyTrade/pull/35).
Subsequent report/evidence edits do not change executable/test sources. The readiness
procedure verified the same 682 source files before/after, hash `066f4b344fa868eff595a3cb28fc33d38dbb9d9af2df97553737b26faab62f87`
([manifest](source-fingerprint.json)).

| Check | Executed result | Evidence |
| --- | --- | --- |
| Complete offline backend | 2,128 passed; zero failures/errors/skips | [CI run](https://github.com/GabeSternberg/EntropyTrade/actions/runs/44250125423), [receipt](quality-acceptance.json), `pytest-results.xml.gz`, `full-ci.log.gz` |
| Frontend DOM | 128 passed | CI above; `frontend-ready-final.log.gz` |
| Ruff / format / strict mypy | Passed; 661 Python source files | CI above |
| Complete default browser inventory | 36 distinct procedures across 20 files verified | [receipt](browser-acceptance.json), per-spec compressed reports |
| Live public browser procedures | Shadow, authentic labels and four workbench workflows passed on final code | [CI run](https://github.com/GabeSternberg/EntropyTrade/actions/runs/44250121144), `public-browser-accepted/` |

The cloud sweep's two public-source failures remain failures: its outbound requests returned
`ConnectError`/`GatewayError`. Exactly those procedures were also executed with all assertions
on the network-capable runner; its shadow procedure additionally verifies actual ingestion.
This is verification across two cloud environments, not a claim that blocked-network tests
passed locally. Every default registered name is accounted for; no skipped tests, expected
failures or retries are counted as passes. The optional retained-Bitcoin case requires an
explicit external input path and was not registered in this default 36-case inventory.

| Spec | Procedures | Development cloud | Public runner |
| --- | ---: | --- | --- |
| `provider` | 1 | 1 passed | — |
| `cis1990` | 3 | 3 passed | — |
| `research` | 4 | 4 passed | — |
| `research-paper` | 2 | 2 passed | — |
| `readiness` | 2 | 2 passed | — |
| `lifecycle` | 3 | 3 passed | — |
| `redesign` | 1 | 1 passed | — |
| `bitcoin-history` | 2 | 2 passed | — |
| `weather-history` | 1 | 1 passed | — |
| `forward-validation` | 2 | 2 passed | — |
| `label-partitions` | 1 | 1 passed | — |
| `shadow-history` | 3 | 3 passed | — |
| `fees` | 2 | 2 passed | — |
| `paper` | 2 | 2 passed | — |
| `alerts` | 1 | 1 passed | — |
| `prospective` | 2 | 2 passed | — |
| `recovery` | 1 | 1 passed | — |
| `shadow` | 1 | 1 passed | passed on public runner |
| `weather-labels` | 1 | 0 passed | passed on public runner |
| `workbench` | 1 | 0 passed | passed on public runner |

## Controlled versus authentic evidence

`controlled-summary.json` records the objective-driven test: real typed PydanticAI FunctionModel
output, approval (zero HTTP before consent), one shared synthetic acquisition, actual feature
materialization/fitting/replay, automatic reevaluation after evidence arrival and restart,
independent validation with holdout closed, a positive synthetic paper decision, one forward
prediction/execution, pending monitoring, and byte-identical snapshot/restore. Production
paper policy rejects every controlled proposal. Statistical/fee/execution/permission gates
are unchanged. `controlled-lifecycle-summary.json.gz` retains its full reports.

`CONTROLLED-synthetic-lifecycle-workspace.zip` is a separate successful repeat of the same
integration test, retaining 1,051 frozen paths including dataset/model artifacts, source
receipts and the simulated paper ledger. Its UUIDs differ from the first summary run.
[Archive receipt](controlled-workspace-archive.json); no genuine performance is represented.

`authentic-public-30day.zip` retains the original anonymous acquisition run and raw bytes:
862 PFM forecasts, 30 final CLI reports, 180 Kalshi contracts and 30 Weather Company labels
from 39 requests. Four datasets/four features persisted. [Summary](authentic-public-summary.json)
and [local verification](authentic-local-verification.json) show process reconstruction plus
snapshot/restore preserving 78 immutable files and five persisted refusals. Zero labels were
available before fitting cutoff; historical books/rules and certified fees were absent.
No authentic model, historical return or qualified paper candidate was invented.

No provider credential or local model endpoint was available. GitHub secret metadata was
inaccessible (403); no secret values were retrieved. Controlled agent/provider HTTP tests
cover behavior; an authenticated external AI inference remains unverified.

## Corrections and review limits

Fixed existing-execution-dataset reuse, scheduled rechecks (including old evaluated
checkpoints), exhausted-budget status, shutdown cancellation/lease retention, honest
materializer capabilities, initial/deferred workbench registration and initialization
interaction barriers. Test-only manifest and paper-monitor clock corrections preserve strict
recovery comparisons. No collector configuration, scientific minimum, risk policy or live
submission path changed.

Earlier attempts are not acceptance: source edits invalidated readiness fingerprints;
controlled monitoring mixed real/test clocks; early history/provider interactions exposed
initialization races; an interrupted trace exhausted disk. Failed/interrupted logs and
cleanup receipts identify these outcomes. Old extracted artifact duplicates were removed
only with their complete original ZIPs/hashes retained. Known obsolete synthetic traces were
removed with per-file hashes; no genuine/canonical source was deleted. Full current traces
remain local and public-run artifacts are retained by GitHub for 30 days. Committed compressed
reports/downloads, manifests and authentic/control archives persist independently.

Fee certification, timely historical or prospective evidence, exact unsupported feature
adapters, authenticated AI and physical Windows/TLS/reboot/offsite acceptance remain as
specified in the readiness report. Prospective 20-event/10-date qualification is a later
readiness gate, not a prerequisite to start an otherwise eligible paper deployment.

## Reproduction

Use Python 3.13.14, locked `uv.lock`, pinned Playwright 1.56.1/Chromium 1194, and fresh
workspace/evidence paths per spec. Run Ruff lint/format, strict mypy, all
`node --test frontend/tests/*.test.cjs`, and the complete `pytest` suite. The dedicated test is
`backend/tests/integration/test_research_lifecycle.py`. Browser commands and failure-retaining
procedures are in [the browser guide](../../../frontend/browser/README.md); use a filename
pattern ending in `/NAME\.spec\.cjs$` to avoid substring duplicates. Source acquisition
requires real public egress. The manual CI inputs `public_probe=true` and `public_browser=true`
run bounded anonymous checks without any repository secrets or order endpoints.
