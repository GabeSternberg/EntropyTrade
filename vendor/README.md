# vendor/

This directory is empty on purpose.

Prefer a pinned package dependency (`uv.lock`) over a copy. Phase 0 vendors
nothing. The Kalshi docs are a CC0 reference skill at
`.agents/skills/kalshi-docs/`, not a code dependency, so they do not live here.

If a later phase copies third-party source instead of depending on it:

1. Put it in `vendor/<project>/` at a recorded upstream commit.
2. Keep that project's `LICENSE` next to the copy.
3. Add an entry to `THIRD_PARTY_NOTICES.md` (project, commit, license, copyright, what changed).
4. Add a row to `docs/external-repositories.md`.
5. Do not edit the copy in place without writing the modification down.

Projects that were audited and explicitly rejected for vendoring include the
Kalshi SDK's perps client (use the package instead), every trading bot and
backtester in the audit, and pmxt. See `docs/external-repositories.md`.
