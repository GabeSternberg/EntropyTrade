FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.22 /uv /uvx /bin/
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv sync --frozen --no-dev && chown -R app:app /app
USER app

ENTRYPOINT ["uv", "run", "entropytrade"]
