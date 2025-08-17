#!/bin/bash

# ATOM Web-Dev Cloud Preview Deployment Script
# Automatically deploys to free cloud providers from GitHub

set -e

echo "🚀 ATOM Cloud Preview Deployment Starting..."

# Configuration
REPO_URL=${GITHUB_REPO:-$(git config --get remote.origin.url)}
BRANCH=${GITHUB_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    error "Not in a git repository. Please initialize git first."
fi

# Install Netlify CLI if not present
if ! command -v netlify &> /dev/null; then
    log "Installing Netlify CLI..."
    npm install -g netlify-cli
fi

# Install Vercel CLI if not present
if ! command -v vercel &> /dev/null; then
    log "Installing Vercel CLI..."
    npm install -g vercel
fi

# Build the application
log "Building ATOM web application..."
cd atomic-docker/app_build_docker
npm ci --silent
npm run build

log "Build completed successfully"

# Cloud deployment functions

deploy_netlify() {
    log "Deploying to Netlify..."

    # Check if netlify.toml exists
    if [ ! -f "netlify.toml" ]; then
        log "Creating netlify.toml..."
        cat > netlify.toml << EOF
[build]
  command = "npm run build"
  publish = ".next"

[build.environment]
  NODE_VERSION = "18"

[[plugins]]
  package = "@netlify/plugin-nextjs"

[context.deploy-preview]
  command = "npm run build"
EOF
    fi

    # Deploy
    netlify deploy --prod --dir=.next --build
}

deploy_vercel() {
    log "Deploying to Vercel..."

    # Create vercel.json if it doesn't exist
    if [ ! -f "vercel.json" ]; then
        cat > vercel.json << EOF
{
  "version": 2,
  "builds": [{ "src": "package.json", "use": "@vercel/next" }],
  "github": {
    "autoAlias": true
  }
}
EOF
    fi

    # Check if VERCEL_TOKEN is set
    if [ -z "$VERCEL_TOKEN" ]; then
        log "Please set VERCEL_TOKEN environment variable for auto-deployment"
        vercel --prod
    else
        vercel --token $VERCEL_TOKEN --prod --yes
    fi
}

deploy_fly() {
    log "Deploying to fly.io..."

    # Check if fly.toml exists
    if [ ! -f "fly.toml" ]; then
        log "Creating fly.toml configuration..."
        cat > fly.toml << EOF
app = "atom-web-dev"
primary_region = "iad"

[build]
  [build.args]
    NEXT_PUBLIC_ANALYTICS_ID = "your-analytics-id"

[[services]]
  http_checks = []
  internal_port = 3000
  processes = ["app"]
  protocol = "tcp"
  script_checks = []

  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.tcp_checks]]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"
EOF
    fi

    fly deploy --remote-only
}

# Main deployment logic
case "${CLOUD_PROVIDER:-auto}" in
    netlify)
        deploy_netlify
        ;;
    vercel)
        deploy_vercel
        ;;
    fly)
        deploy_fly
        ;;
    auto)
        log "Auto-detecting best cloud provider..."

        # Check for existing configurations
        if [ -f "../../../config/deployment/netlify.toml" ]; then
            log "Found netlify.toml, deploying to Netlify..."
            deploy_netlify
        elif [ -f "../../../
