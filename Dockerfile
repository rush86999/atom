# ==========================================
# STAGE 1: Frontend Builder
# ==========================================
FROM node:22-slim AS frontend-builder
WORKDIR /app
COPY frontend-nextjs/package.json frontend-nextjs/package-lock.json* ./
RUN npm install --legacy-peer-deps
COPY frontend-nextjs/ .
RUN npm run build

# ==========================================
# STAGE 2: Backend Builder
# ==========================================
FROM python:3.11-slim AS backend-builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==========================================
# STAGE 3: Final Production Runner
# ==========================================
FROM python:3.11-slim AS runner

# Install Node.js 22 in the Python environment
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user for security (matching backend Dockerfile)
RUN useradd -m -u 1000 atomuser && \
    chown -R atomuser:atomuser /app

# Copy Python packages from backend-builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy Backend Source
COPY backend /app/backend

# Copy Frontend Standalone Output
# Note: Next.js standalone includes the minimal node_modules needed
COPY --from=frontend-builder /app/.next/standalone /app/frontend-nextjs
COPY --from=frontend-builder /app/.next/static /app/frontend-nextjs/.next/static
COPY --from=frontend-builder /app/public /app/frontend-nextjs/public

# Copy Startup Script
COPY scripts/start-dual-app.sh /app/start-dual-app.sh
RUN chmod +x /app/start-dual-app.sh && \
    chown -R atomuser:atomuser /app

# Switch to non-root user
USER atomuser

# Environment Variables
ENV PORT=3000
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose Frontend Port (Next.js)
EXPOSE 3000
# Backend port is internal-only or used via proxy, but we'll expose for visibility
EXPOSE 8000

# Start both services
CMD ["/app/start-dual-app.sh"]
