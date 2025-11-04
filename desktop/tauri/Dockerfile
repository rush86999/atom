# Multi-stage build for ATOM Desktop with GitHub Integration
FROM node:18-alpine AS frontend-builder

# Install system dependencies
RUN apk add --no-cache \
    git \
    python3 \
    make \
    g++

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy source code
COPY . .

# Build frontend
RUN npm run build

# Build Tauri application
FROM node:18-alpine AS tauri-builder

# Install system dependencies for Tauri
RUN apk add --no-cache \
    curl \
    wget \
    gnupg \
    libgtk-3-dev \
    libwebkit2gtk-4.0-dev \
    libappindicator3-dev \
    librsvg2-dev \
    patchelf \
    python3 \
    make \
    g++ \
    openssl-dev

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy frontend build
WORKDIR /app
COPY --from=frontend-builder /app/dist ./dist
COPY --from=frontend-builder /app/node_modules ./node_modules
COPY --from=frontend-builder /app/src ./src
COPY --from=frontend-builder /app/package*.json ./
COPY --from=frontend-builder /app/src-tauri ./src-tauri

# Install Tauri CLI
RUN npm install -g @tauri-apps/cli

# Build Tauri app
RUN npm run tauri build

# Production image
FROM node:18-alpine AS production

# Install runtime dependencies
RUN apk add --no-cache \
    curl \
    ca-certificates \
    libgtk-3-0 \
    libwebkit2gtk-4.0-37 \
    libappindicator3-1 \
    librsvg2-2 \
    xorg-server-xvfb

# Create app user
RUN addgroup -g 1001 -S atom && \
    adduser -S atom -u 1001 -G atom

# Set working directory
WORKDIR /app

# Copy built application
COPY --from=tauri-builder --chown=atom:atom /app/src-tauri/target/release/bundle/ ./

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/cache && \
    chown -R atom:atom /app

# Switch to non-root user
USER atom

# Expose ports
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Start the application
CMD ["xvfb-run", "--auto-servernum", "./atom-desktop"]