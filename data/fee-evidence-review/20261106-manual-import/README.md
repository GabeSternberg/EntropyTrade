# Operator manual import of the official fee schedule — 2026-11-06

Branch `claude/vibrant-bohr-1hw7xm`, stacked on PR #7. Addresses option 1 of issue #6.
**No authentic fee schedule has been imported or certified.** Every byte used here is a
CONTROLLED test PDF (`%PDF-1.4\ncontrolled cli test bytes\n`,
`sha256:ab2dc777cf4f46b0108ac1ca2218b06d170e098c7fcdeb42579667f152601254`).

## What was executed

| Check | Result |
|---|---|
| `test_fee_manual_import.py` (13 cases) | Pass |
| `test_fee_capture_due.py`, `test_fee_evidence.py` (unchanged) | Pass (44 fee cases in total) |
| Retained 2026-10-30 version `fresh-source-version.json` | Recomputes to its recorded `sha256:973a6db6…d322`; no `manual_import` key is serialized |
| CLI `--import-schedule` on a temporary workspace under `data/cache/` | Version stored with `manual_import` provenance, `status: 200`, `received_at` = import clock, refusal "Unreviewed operator manual import…"; workspace deleted afterwards |
| CLI without `--downloaded-at`/`--note` | Exit 2: `--import-schedule requires --downloaded-at and --note` |
| Real Chromium (pre-installed Playwright) against the actual server on `127.0.0.1:8791`, [`browser-check.cjs`](browser-check.cjs) | `#fee-evidence` shows `OPERATOR MANUAL IMPORT (no system-observed HTTP) · Imported … · Operator-attested download …`; "Original fee source 1" download hash equals the input hash; 0 page errors; [screenshot](manual-import.png) |
| Ruff lint/format, strict mypy (563 files), frontend unit tests (24) | Pass |
| Full pytest ([log](pytest-full.log)) | **1,354 passed in 692.40s**, zero failures/errors/skips |

The browser check is an ad-hoc single-page verification, not a run of the Playwright
acceptance suite (`frontend/browser/*.spec.cjs` needs `npm ci` in `frontend/browser`, which
was not performed). Listener restart and offline restore were not re-executed for imported
versions; they use the unchanged fee store and workspace snapshot paths.

## Not established

- No real official schedule bytes exist in any workspace. A human must download the PDF.
- Certification still requires a human `--review` attestation; nothing here certifies a fee.
