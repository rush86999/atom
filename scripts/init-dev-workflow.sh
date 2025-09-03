
# ATOM AI Web Development Workflow Setup
# Complete cloud-desktop development environment
# Usage: ./init-dev-workflow.sh [project-name] [provider]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_NAME=${1:-my-web-app}
CLOUD_PROVIDER=${2:-auto}
REPO_NAME="${PROJECT_NAME}-web"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}🚀 Setting up ATOM AI Cloud-Desktop Development Environment${NC}"
echo -e "${BLUE}Project: ${PROJECT_NAME}${NC}"
echo -e "${BLUE}Provider: ${CLOUD_PROVIDER}${NC}"
echo -e "${BLUE}Started: $(date)${NC}"

# Check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."

    # Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js not found. Please install Node.js 18+${NC}"
        exit 1
    fi

    # Git
    if ! command -v git &> /dev/null; then
        echo -e "${RED}❌ Git not found. Please install Git${NC}"
        exit 1
    fi

    # Docker (for desktop app)
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}⚠️  Docker not found - desktop build will skip${NC}"
    fi

    echo -e "${GREEN}✅ Prerequisites check complete${NC}"
}

# Initialize Git repository
init_git_repo() {
    echo "📁 Initializing Git repository..."

    if [ ! -d .git ]; then
        git init
        git checkout -b main
    fi

    # Create .gitignore
    cat > .gitignore << 'EOF'
# Dependencies
node_modules/
.pnpm-store/
.DS_Store
thumbs.db

# Build outputs
.next/
.out/
dist/
build/

# Environment variables
.env
.env.local
.env.production

# Logs
*.log
logs/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db
EOF

    git add .gitignore
    git commit -m "chore: initial repository setup"
    echo -e "${GREEN}✅ Git repository ready${NC}"
}

# Setup Next.js project
init_nextjs_app() {
    echo "⚛️ Setting up Next.js project..."

    cd frontend-nextjs/app_build_docker

    # Install dependencies
    npm ci

    # Install deployment tools
    npm install -D vercel netlify-cli J
    npm install -D wait-on concurrently

    # Create Next.js config for cloud deployment
    cat > next.config.js << 'EOF'
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true
  },
  trailingSlash: true,
  distDir: 'out',
  env: {
    CUSTOM_KEY: 'my-value',
  },
}

module.exports = nextConfig
EOF

    # Create package.json scripts for deployment
    cat > package.json << 'EOF'
{
  "name": "@atom/web-dev",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "export": "next export",
    "deploy": "npm run build && npm run export",
    "dev:cloud": "concurrently \"npm run dev\" \"npm run monitor:cloud\"",
    "monitor:cloud": "node ../../scripts/monitor-deployments.js",
    "preview:netlify": "netlify deploy --dir=out --prod",
    "preview:vercel": "vercel --prod",
    "preview:all": "npm run preview:vercel && npm run preview:netlify",
    "build:watch": "npm run build && npm run export",
    "tunnel": "npm run dev & ngrok http 3000"
  },
  "dependencies": {
    "next": "14.0.4",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "tailwindcss": "3.3.6",
    "autoprefixer": "10.4.16",
    "postcss": "8.4.32"
  },
  "devDependencies
