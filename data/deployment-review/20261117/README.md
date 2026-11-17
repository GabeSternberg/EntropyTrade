# Deployment software acceptance — November 17, 2026

The deployment software increment passes acceptance at application commit
`76add54535908bb996cb30183f6663f2883b45cf` in
[PR #34](https://github.com/GabeSternberg/EntropyTrade/pull/34).
[CI run 44173222729](https://github.com/GabeSternberg/EntropyTrade/actions/runs/44173222729)
passes **2,123 Python tests in 1,652.33 seconds**, Ruff/format, strict mypy (660 files)
and 125 frontend tests. The decoded complete job log is retained as
[compressed text](quality/ci-44173222729.log.gz), with
[run metadata](quality/github-ci-run.json) and [successful job steps](quality/github-ci-jobs.json).
Completion changes contain documentation and retained evidence only; application code,
CI-executed tests, native harnesses, deployment templates and dependency configuration
remain identical to the accepted commit.

The [operating guide](../../../docs/windows-research-server.md) gives exact physical
Windows/WSL, private access, startup, backup, offsite-copy and restore procedures.
**The actual Windows PC, Tailscale account, canonical collector, Mac/phone and offsite
storage have not been accessed or configured.** No live order or paid provider call was made.

## What is implemented

- Private mode requires one exact HTTPS origin and Tailscale owner login, then an owner
  session for API reads, downloads and mutations. Bootstrap is identity-checked and minimal;
  Host/Origin, CSRF and duplicate-header checks remain strict. Cookies are Secure, HttpOnly
  and SameSite=Strict; restart invalidates RAM sessions. Controlled tests exercise the real
  HTTP handler with emulated trusted proxy headers. Actual HTTPS/Tailscale identity and ACL
  behavior remain physical acceptance gates.
- Separate `EntropyTrade-research` checkout/workspace, private configuration and credentials,
  pinned commit/lock/Python/environment, research-only user units and a daily backup timer.
  The maintenance coordinator stops/restarts only the previously active research unit and
  retains staging/lease cleanup on interruption. Real static systemd unit verification and
  the actual cloud CLI's WSL refusal pass; no unit was installed or started in cloud.
- Complete offline research validation includes dormant/unpromoted fitted and portable
  models, manifests, raw responses, feature hashes, frozen plans/reports, SQL references,
  budgets and protected boundaries. Models and feature/label values remain opaque bytes;
  restore never trains, scores, migrates or resumes jobs. Atomic Linux/WSL no-replace
  publication rejects destinations created after the last existence check.
- Real GnuPG encryption uses a pinned, validated public recipient; the server needs no
  private key. Restore copies and verifies an independently trusted ciphertext hash before
  decryption and publication. Wrong keys, corruption, bounds, timeouts, busy leases, disk
  shortages and unsafe paths refuse. A time-shifted real GPG case preserves decryption of
  historical ciphertext after recipient expiry while new encryption still refuses.
- Read-only collector export holds one existing shared lock through verification/copy,
  preserves the complete hash-linked history and original embedded application locks, and
  restores only into a new marked inactive inspection directory outside `data/cache`.
  Controlled two-link byte/mode/time preservation and encrypted history round trips pass.
  No physical collector data or collector service/task was touched.

## Browser and recovery evidence

All **six final native Chromium cases** pass with no skips, flaky/unexpected cases, page
errors or console errors. The four lifecycle/layout cases take 82.299245 seconds; the two
owner/recovery cases take 332.463247 seconds. See [lifecycle results](browser/lifecycle-results.json),
[owner results](browser/owner-results.json), and their retained logs/receipts under `browser/`.
Each before/after source fingerprint matches. The lifecycle scope is 711 files, hash
`56038ccab84068955ac0e71378b67466140205142bd0072d54d0bb15d9970d90`;
the owner harness's narrower scope is 681 files, hash
`d66ce2ac5f8f7de0f3aabcf75653c62c951f50d306126b5e8a8bdbfadd21b485`.

Actual fitted synthetic research, exact lifecycle navigation, owner sign-in/out, review,
rollback/revocation, halt/release, restart invalidation and offline snapshot/restore are
exercised through real pages/services. The revoked, restarted and restored readiness JSON
exports are byte-identical:
`16d11e19205d0c52506bd3a57c6a1bbb0e01c5040c0e772d97a18f4c4f1cdd32`.
These are local HTTP browser tests. Private Secure-cookie attributes and proxy/session
boundaries have separate real HTTP tests; genuine private TLS and actual devices remain
unexecuted physical checks.

An additional [protected-key drill](quality/protected-key-drill.json) encrypts/restores
actual synthetic application artifacts using an ephemeral passphrase-protected GPG key.
It stops the generation agent, unlocks via controlled stdin, then verifies production
noninteractive cache reuse, all immutable hashes and the restored 1-job/2-dataset/3-feature/
1-experiment inventory. This is a local copied-ciphertext drill, without actual offsite
transfer, the user's key or an interactive pinentry test. The exact executed driver is
[retained](quality/protected-key-drill.py); to repeat from a prepared checkout, first create
`data/cache/deployment-checks`, then run it with `PYTHONPATH=backend/src:backend` and the
locked Python environment. It uses temporary controlled keys/data and cleans its GPG agent.

## Review and limitations

[Review findings](review.md) record corrected systemd quoting, interruption cleanup,
model-reference integrity, historical-key expiry and persisted research conventions.
The first complete CI run passed 2,119 tests and exposed two recovery cases: multi-source
requirement ID suffixes and a synthetic fixture's mixed manifest/link metadata. Both are
fixed, strict manifest checks remain enforced, two negative regressions were added, all
56 research/orchestration cases pass locally, and the final whole suite passes 2,123 tests.
Earlier failures and the cloud disk-exhaustion attempt remain under `failed-attempts/`.
The old native E harness's readiness route and renamed audit tab were updated to F; its
original timeout and interrupted stale-selector attempt are retained.

Positive fits/accounts/keys/history fixtures are explicitly synthetic. Metadata probes
labelled real are count/navigation tests, not authentic scientific evidence. Current
adverse-execution eligibility remains unchanged. Authentic point-in-time evidence,
certified fees and authenticated live-provider verification remain separate gates.
Owner review cannot authorize live submission.

Raw final traces/screenshots/downloads remain locally in
`data/cache/deployment-browser-final-3` and `data/cache/deployment-owner-browser-final-4`.
Earlier completed synthetic scratch workspaces and redundant successful traces were removed
to fit the cloud disk; cleanup receipts record their scope and hashes. Final receipts,
selected screenshots and identical downloads are retained here. No canonical or authentic
collector evidence was removed. [acceptance.json](acceptance.json) records exact claims and
external gates; `manifest.json` hashes the retained packet.
