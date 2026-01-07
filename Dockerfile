# ============================================
# STAGE 1: Builder - Install all dependencies
# ============================================
FROM python:3.13-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies for packages with C extensions
# gcc, musl-dev, linux-headers: Required for numpy, msgpack, pydantic-core, charset-normalizer
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    g++ \
    libffi-dev

# Install uv (Python package installer)
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /usr/local/bin/uv

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
FROM python:3.13-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Tell uv to use system Python instead of creating venvs
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Install runtime dependencies for compiled packages
# libstdc++: Required by numpy, pandas
# libgcc: Required by most C extensions
RUN apk add --no-cache libstdc++ libgcc libffi

# Copy uv for convenience (though not needed since packages are pre-installed)
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /usr/local/bin/uv

WORKDIR /app

# Copy Python packages from builder (installed system-wide, not in venv)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy application source and project metadata
COPY src /app/
COPY pyproject.toml uv.lock /app/

# Create non-root user
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/sh -D appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "garmin_grafana/garmin_fetch.py"]
