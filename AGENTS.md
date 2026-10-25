# Development workflow

Use a feature branch for each major phase, starting from updated main. Preserve earlier
recovery branches and unrelated changes. Work independently within the approved phase.

After completing a phase, run Ruff lint/format, strict mypy and pytest. Fetch origin,
integrate current main without rewriting history, verify the resulting main and push both
the phase branch and main. The user explicitly authorized this workflow on 2026-10-25.
Never force-push. Stop for review before starting the next major phase unless the user
explicitly authorizes it. Initial work on an incomplete phase stays on its feature branch.

Preserve source provenance, point-in-time clocks, settlement semantics and protected
holdout boundaries. Never enable production submission or place real-money orders without
separate explicit approval. Research credentials are separate from exchange credentials.
