# Use multi-stage build for smaller image size
FROM python:3.11-slim as builder

# Build argument for optional Docling OCR support
ARG ENABLE_DOCLING=false

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install core dependencies
COPY requirements.txt .
# Optimization: Install CPU-only torch first to avoid downloading huge CUDA binaries
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Optionally install Docling for advanced OCR
COPY requirements-docling.txt* ./
RUN if [ "$ENABLE_DOCLING" = "true" ] && [ -f requirements-docling.txt ]; then \
    pip install --no-cache-dir -r requirements-docling.txt; \
    fi

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Change ownership of the app directory to appuser
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with Gunicorn
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main_api_app:app"]
