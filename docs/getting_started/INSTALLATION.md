# Atom Installation Guide

This document describes all verified setup options for the Atom platform, including manual git clone, docker-compose, script automation, and platform-specific deployments.

> [!NOTE]
> For a quick local setup, see the [🚀 Quick Start Guide](./quick-start.md) (manual git clone + venv — takes ~5 minutes).

---

## Why This Exists

### ❌ The Problem
Running multi-agent frameworks locally often requires configuring complex system dependencies (compilers, local databases, node modules, python packages, ONNX runtimes). A single version conflict or mismatch can render the entire system inoperable.

### 🎯 The Impact
Manual, un-containerized configurations slow down developer onboarding, lead to hard-to-debug library conflicts (e.g. SQLite version mismatch, python-venv collision), and complicate the transition from local testing to high-availability production clusters.

### 🛡️ Our Solution
Atom provides three independent, structured installation options to match execution goals:
1. **Docker-First (Stable/Production)**: One-command containerized services bundling PostgreSQL, Redis, and SQLite for conflict-free isolation.
2. **Git Clone & venv (Development/HTR)**: Step-by-step local bootstrap setup for active codebase modifications and E2E QA testing.
3. **Automated Shell Installer**: One-shot script resolving local system tools, setting up virtual environments, and migrating database tables automatically.

---

## 🛠️ Installation Methods

### Method 1: Docker Compose (Personal & Enterprise)
Docker Compose is the recommended path for deploying stable releases.

**Personal Edition** (single-user SQLite stack, no external services):
```bash
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env
# Edit .env — generate SECRET_KEY, JWT_SECRET_KEY, BYOK_ENCRYPTION_KEY
# (openssl rand -base64 32) and set one LLM key OR ATOM_LOCAL_ONLY=true
docker compose -f docker-compose-personal.yml up -d --build
# Frontend: http://localhost:3001   Backend: http://localhost:8001
```

**Full stack** (PostgreSQL + Redis + piece-engine + browser-node):
```bash
docker compose up -d --build
# Uses docker-compose.yml. Requires SECRET_KEY + JWT_SECRET_KEY in .env.
```

The Personal Edition compose file (`docker-compose-personal.yml`) runs the
**full app** (`main_api_app:app`, v8.0.0, 197 routers) on SQLite. The backend
Dockerfile sets `WORKDIR /app/backend` and `PYTHONPATH=/app:/app/backend` so
both bare and `backend.*` imports resolve.

### Method 2: Manual Clone & Virtual Environment (Local Dev)
Ideal for contribution and running the latest changes from `main`:

```bash
git clone https://github.com/rush86999/atom.git
cd atom

# One-shot bootstrap (recommended):
make setup

# — OR do it manually:

# 1. Setup Backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit: SECRET_KEY + one LLM key (or ATOM_LOCAL_ONLY=true)

# 2. Setup Frontend
cd ../frontend-nextjs
npm install --legacy-peer-deps

# 3. Launch (from repo root — main_api_app:app is the FULL app, v8.0.0)
cd ..
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
# In another terminal: cd frontend-nextjs && npm run dev -- -p 3001
# — OR use the Makefile: make backend / make frontend / make dev
```

### Method 3: Quick Start Script
After cloning, run the one-shot bootstrap script (same as `make setup`):

```bash
git clone https://github.com/rush86999/atom.git
cd atom
./scripts/quickstart.sh   # venv + backend deps + frontend deps + .env generation
```

### Method 4: Makefile (recommended for contributors)

```bash
make setup       # one-shot: venv + deps + .env
make backend     # run full backend on :8001
make frontend    # run frontend dev server on :3001
make dev         # run both (tmux or two terminals)
make test        # run backend unit tests
make test-e2e    # run E2E journey suite
```

---

## 🖥️ Platform-Specific Guidelines

### Mac Mini Deployment
Deploying Atom on a dedicated host (e.g., Apple Silicon Mac Mini) for office automation:

1. **Hardware Dependencies**: Ensure Xcode Command Line Tools are active:
   ```bash
   xcode-select --install
   ```
2. **Local Inference (Ollama)**: Optimize local models by enabling Apple Silicon GPU acceleration:
   ```bash
   brew install ollama
   ollama run llama3:8b
   ```
   Configure `.env` to route local execution queries:
   ```bash
   ATOM_LOCAL_ONLY=true
   OLLAMA_BASE_URL=http://localhost:11434/v1
   ```

### Enterprise Deployment (PostgreSQL + Redis)
For multi-user orchestration:
- Database: Configure `DATABASE_URL=postgresql://user:pass@host:5432/atom` in `.env`.
- Task Queue: Configure `REDIS_URL=redis://localhost:6379/0` for EventBus routing.
