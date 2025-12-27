# Use multi-stage build for smaller image size
FROM python:3.11-slim as builder

# Build argument for optional Docling OCR support (adds ~2GB)
ARG ENABLE_DOCLING=false

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install core dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Optionally install Docling for advanced OCR (if enabled and requirements file exists)
# Create empty placeholder if file doesn't exist to prevent COPY failure
COPY requirements-docling.tx[t] ./
RUN if [ "$ENABLE_DOCLING" = "true" ] && [ -f requirements-docling.txt ]; then \
    pip install --user --no-cache-dir -r requirements-docling.txt; \
    fi

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with Gunicorn using Uvicorn workers
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main_api_app:app"]
