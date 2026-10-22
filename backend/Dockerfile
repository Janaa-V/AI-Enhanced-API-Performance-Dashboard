# Backend image. Two stages: the first installs the locked dependencies with uv, the second
# receives only the finished virtual environment and the code, and runs as a non-root user.
# Base images are pinned by digest so every build starts from the same bytes; bump the digests
# on purpose to pick up security patches.

FROM ghcr.io/astral-sh/uv:0.12.16@sha256:adc68cd785ca65ea25c0611043b0a00b4ea3a22e1b54102fc084406d888082ee AS uv

FROM python:3.14-slim@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1 AS build

COPY --from=uv /uv /usr/local/bin/uv

# Compile bytecode now rather than on first import; copy files instead of hard-linking from the
# cache (the cache is a build-time mount); use the image's Python, never download another.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, so editing the code does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project


FROM python:3.14-slim@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1 AS runtime

LABEL org.opencontainers.image.title="api-performance-dashboard-backend" \
      org.opencontainers.image.source="https://github.com/Janaa-V/AI-Enhanced-API-Performance-Dashboard"

# Logs go straight to stdout; the code is read-only to the app user, so Python cannot write
# bytecode next to it anyway.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Owned by root: the app user can read and run the code but not change it.
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY app ./app
RUN python -m compileall -q app migrations scripts

USER app

EXPOSE 8000

# /health also checks the database, so an unhealthy container means "cannot serve requests".
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/health\", timeout=4)"]

# One worker on purpose: the AI cache, single-flight and hourly quota live in process memory,
# so more workers would multiply the quota. Scale with more containers only once that state
# moves out of the process. `exec` makes uvicorn PID 1, so it receives SIGTERM and shuts down
# cleanly. Hosting platforms set PORT; 8000 otherwise.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
