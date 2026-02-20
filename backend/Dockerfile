# Source: https://docs.docker.com/build/cache/backends/gha/
# Multi-stage build with layer caching optimization

FROM python:3.11-slim as builder

# Build arguments for optional dependencies
ARG ENABLE_DOCLING=false
ARG ENVIRONMENT=production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements FIRST (before source code)
# This layer is cached unless requirements.txt changes
COPY requirements.txt requirements-testing.txt requirements-docling.txt* ./

# Use BuildKit cache mount for pip cache
# --mount=type=cache caches pip downloads across builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Optional: Test dependencies (separate layer)
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ -f requirements-testing.txt ]; then \
        pip install --no-cache-dir -r requirements-testing.txt; \
    fi

# Optional: Docling dependencies (separate layer, only if enabled)
RUN if [ "$ENABLE_DOCLING" = "true" ] && [ -f requirements-docling.txt ]; then \
        pip install --no-cache-dir -r requirements-docling.txt; \
    fi

# Copy source code AFTER dependencies
# This layer is rebuilt on every code change (but dependencies remain cached)
COPY . .

# Create non-root user
RUN useradd -m -u 1000 atomuser && \
    chown -R atomuser:atomuser /app

# Production stage
FROM python:3.11-slim as production

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code from builder stage
COPY --from=builder --chown=atomuser:atomuser /app /app

# Set working directory and user
WORKDIR /app
USER atomuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
