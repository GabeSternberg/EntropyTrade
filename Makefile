.PHONY: check lint format typecheck test

check: lint typecheck test

lint:
	uv run ruff check backend
	uv run ruff format --check backend

format:
	uv run ruff format backend
	uv run ruff check backend --fix

typecheck:
	uv run mypy

test:
	uv run pytest
