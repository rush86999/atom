# Dockerfile for Atom Functions
# Builds the functions service from the new location in frontend-nextjs/project/functions

FROM node:18-alpine AS base

# Install Python and build dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    && pip3 install --upgrade pip

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile --production=false

# Copy function source code
COPY . .

# Build TypeScript functions
RUN yarn build:functions || echo "No build script found, proceeding with source files"

# Install Python dependencies
RUN pip3 install flask flask-sock fastapi uvicorn elevenlabs deepgram-sdk
RUN if [ -f requirements.txt ]; then pip3 install -r requirements.txt; fi

# Create a non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Change ownership of the app directory to the non-root user
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose the port the app runs on
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/healthz || exit 1

# Start the functions server (Node.js for TypeScript functions)
# Python functions will need to be started separately or integrated
CMD ["yarn", "start:functions"]
