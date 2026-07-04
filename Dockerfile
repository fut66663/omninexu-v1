# OmniNexu MVP Dockerfile
# Python 3.12 + uv → slim image, single worker, ~200MB

FROM python:3.12-slim

# System deps: libpq5 for psycopg2, curl for healthcheck
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ── Layer 1: dependencies only (cached unless pyproject.toml/uv.lock change)
# --no-install-project skips building omninexu itself (src/ not copied yet)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Layer 2: application code + install project
COPY src/ src/
COPY migrations/ migrations/
COPY scripts/ scripts/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8000/v1/health || exit 1

CMD ["uv", "run", "uvicorn", "src.omninexu.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
