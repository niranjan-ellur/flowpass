# syntax=docker/dockerfile:1.7
# Multi-stage build keeps the runtime image small and fast to cold-start on Cloud Run.

FROM python:3.11-slim AS builder

# uv is the fastest way to install Python deps; copy the static binary in.
COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /usr/local/bin/uv

WORKDIR /app

# Copy lockfile + project metadata first for better layer caching.
COPY pyproject.toml uv.lock ./

# Install deps into a project-local .venv; --frozen ensures we honor the lockfile.
RUN uv sync --frozen --no-dev --no-install-project

# Now copy source and install the project itself.
COPY app ./app
RUN uv sync --frozen --no-dev


FROM python:3.11-slim AS runtime

# Create a non-root user with a known numeric UID so that COPY --chown
# in the next step can resolve it without depending on the name being
# visible to the cross-stage chown resolver.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid 1001 --home-dir /app appuser

WORKDIR /app

# Copy the built virtualenv and application code using numeric uid:gid,
# which is the portable way to chown when the source stage lacks the user.
COPY --from=builder --chown=1001:1001 /app /app

# PATH ensures the .venv python is found first.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

USER 1001

EXPOSE 8080

# Cloud Run sets $PORT; uvicorn must bind to it. Using sh -c so the env var expands.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]