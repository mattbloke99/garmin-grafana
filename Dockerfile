# ============================================
# STAGE 1: Builder - Install all dependencies
# ============================================
FROM ghcr.io/astral-sh/uv:0.6.17-python3.13-bookworm-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies (only needed during build)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies system-wide by setting UV_PROJECT_ENVIRONMENT
# This makes uv sync install to system Python instead of creating a venv
# Retries included for ARM64 builds which occasionally have DNS issues
ENV UV_PROJECT_ENVIRONMENT=/usr/local
RUN uv pip install --system setuptools wheel && \
    (uv sync --locked || uv sync --locked || uv sync --locked)

# ============================================
# STAGE 2: Runtime - Minimal final image
# ============================================
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Tell uv to use system Python instead of creating venvs
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Install only runtime dependencies (no build tools)
# This keeps the image small while maintaining functionality
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy uv for convenience
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /usr/local/bin/uv

WORKDIR /app

# Copy Python packages from builder (installed system-wide, not in venv)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy application source and project metadata
COPY src /app/
COPY pyproject.toml uv.lock /app/

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "garmin_grafana/garmin_fetch.py"]
