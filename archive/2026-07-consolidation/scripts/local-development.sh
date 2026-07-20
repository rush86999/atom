#!/bin/bash

# ATOM AI Web Development Studio - Local Development Setup
# Complete localhost development environment with real working endpoints
# Usage: ./local-development.sh [project-name]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME=${1:-my-atom-project}
CURRENT_DIR=$(pwd)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}🚀 Setting up ATOM AI Local Development Environment${NC}"
echo -e "${BLUE}Project: ${PROJECT_NAME}${NC}"
echo -e "${BLUE}Timestamp: ${TIMESTAMP}${NC}"

# Check prerequisites
check_prerequisites() {
    echo "${BLUE}📋 Checking prerequisites...${NC}"

    commands=("node" "npm" "git")
    for cmd in "${commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}❌ ${cmd} is not installed${NC}"
            exit 1
        fi
    done

    NODE_VERSION=$(node --version | cut -d'v' -f2)
    if [[ "$(printf '%s\n' "16.0.0" "$NODE_VERSION" | sort -V | head -n1)" != "16.0.0" ]]; then
        echo -e "${RED}❌ Node.js 16+ required (current: ${NODE_VERSION})${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Prerequisites met${NC}"
}

# Setup directory structure
setup_directory_structure() {
    echo -e "${BLUE}📁 Setting up directory structure...${NC}"

    mkdir -p "${CURRENT_DIR}/${PROJECT_NAME}"
    mkdir -p "${CURRENT_DIR}/${PROJECT_NAME}/web-client"
    mkdir -p "${CURRENT_DIR}/${PROJECT_NAME}/websocket-server"
    mkdir -p "${CURRENT_DIR}/${PROJECT_NAME}/build-scripts"
    mkdir -p "${CURRENT_DIR}/${PROJECT_NAME}/logs"

    echo -e "${GREEN}✅ Directory structure created${NC}"
}

# Setup Next.js client (cloud-based development)
setup_web_client() {
    echo -e "${BLUE}⚛️ Setting up Next.js cloud client...${NC}"

    WEB_CLIENT_DIR="${CURRENT_DIR}/${PROJECT_NAME}/web-client"

    cd "$WEB_CLIENT_DIR"

    # Create minimal Next.js setup
    cat > package.json << 'EOF'
{
  "name": "atom-web-client",
  "version": "2.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3002",
    "build": "next build && next export",
    "start": "next start"
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "socket.io-client": "^4.7.0"
  },
  "devDependencies": {
    "tailwindcss": "^3.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
EOF

    cat > next.config.js << 'EOF'
module.exports = {
  output: 'export',
+  images: {
+    unoptimized: true
+  },
+  trailingSlash: true
+}
EOF

    cat > tailwind.config.js << 'EOF'
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
EOF

    cat > postcss.config.js << 'EOF'
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
EOF

    cd "$CURRENT_DIR/${PROJECT_NAME}"
    echo -e "${GREEN}✅ Web client configured${NC}"
}

# Setup Node.js WebSocket server for real-time updates
setup_websocket_server() {
    echo -e "${BLUE}📡 Setting up WebSocket server...${NC}"

    WS_DIR="${CURRENT_DIR}/${PROJECT_NAME}/websocket-server"
    cd "$WS_DIR"

    cat > package.json << 'EOF'
{
  "name": "atom-websocket-server",
  "version": "2.0.0",
  "scripts": {
    "start": "node server.js",
    "dev": "nodemon server.js"
