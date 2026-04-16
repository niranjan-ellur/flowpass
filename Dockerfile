# syntax=docker/dockerfile:1.7
# Multi-stage build keeps the runtime image small and fast to cold-start on Cloud Run.

FROM python:3.11-slim AS builder

# uv is the fastest way to install Python deps; copy the static binary in.
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

WORKDIR /app

# Copy lockfile + project metadata first for better layer caching.
COPY pyproject.toml uv.lock ./

# Install deps into a project-local .venv; --frozen ensures we honor the lockfile.
RUN uv sync --frozen --no-dev --no-install-project

# Now copy source and install the project itself.
COPY app ./app
RUN uv sync --frozen --no-dev


FROM python:3.11-slim AS runtime

# Create a non-root user for the app. Running as root inside containers is a
# common finding in security scans; this avoids it.
RUN groupadd --system app && useradd --system --gid app --home-dir /app appuser

WORKDIR /app

# Copy the built virtualenv and the application code.
COPY --from=builder --chown=app:app /app /app

# PATH ensures the .venv python is found first.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

USER appuser

EXPOSE 8080

# Cloud Run sets $PORT; uvicorn must bind to it. Using sh -c so the env var expands.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]