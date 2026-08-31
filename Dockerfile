# syntax=docker/dockerfile:1.9

# =============================================================================
# Learning Assistant MCP Server — production image
#
# Multi-stage build:
#   1. builder  — resolves and installs the locked dependency set with `uv`
#                 into a self-contained virtualenv (/app/.venv).
#   2. runtime  — a slim Python image that only carries the venv + app code,
#                 runs as an unprivileged user, and exposes the MCP HTTP port.
#
# The runtime contract is unchanged from `uv run python -m app.main`:
#   - Streamable HTTP transport on ${HOST}:${PORT} (default 0.0.0.0:8006)
#   - GET /health for liveness/readiness
#   - config via environment variables (pydantic-settings); no .env is baked in
# =============================================================================

# --- Pinned bases -----------------------------------------------------------
# `uv` ships a combined image with a managed CPython; keep both stages on the
# same Python minor (3.13) so the venv copied forward is ABI-compatible.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:python3.13-bookworm-slim
ARG RUNTIME_IMAGE=python:3.13-slim-bookworm


# =============================================================================
# Stage 1 — builder
# =============================================================================
FROM ${UV_IMAGE} AS builder

# - bytecode compile for faster cold starts
# - copy (not hardlink) so the venv survives being moved to another stage
# - never fetch a Python at build time; use the one in the base image
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# 1) Dependency layer — depends only on the manifests, so it stays cached
#    across source-only changes. `--no-install-project` skips our own package;
#    `--no-dev` drops the pytest/ruff group.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

# 2) Project layer — add source and install the app itself into the venv.
COPY pyproject.toml uv.lock README.md ./
COPY main.py ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# =============================================================================
# Stage 2 — runtime
# =============================================================================
FROM ${RUNTIME_IMAGE} AS runtime

# - unbuffered stdout/stderr so logs reach the container runtime immediately
# - no .pyc writes at runtime (they are already compiled in the venv)
# - put the venv first on PATH so `python` == the app interpreter
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    HOST=0.0.0.0 \
    PORT=8006

# WeasyPrint native deps (Pango / Cairo / HarfBuzz / GDK-PixBuf) + a base font,
# for the `generate_pdf` tool.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
      libcairo2 libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Drop privileges: fixed non-root uid/gid, no login shell, no home writes.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

# Bring over the built venv and the application source, owned by the app user.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/main.py /app/main.py
COPY --from=builder --chown=app:app /app/app /app/app

USER app

EXPOSE 8006

# Container-level health probe hitting the app's own /health route.
# Uses ${PORT} so it follows a runtime port override.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,sys,urllib.request; \
url='http://127.0.0.1:'+os.environ.get('PORT','8006')+'/health'; \
sys.exit(0 if urllib.request.urlopen(url, timeout=4).status == 200 else 1)"

# uvicorn (under FastMCP's http transport) handles SIGTERM for graceful
# shutdown; run it as the main process.
CMD ["python", "-m", "app.main"]
