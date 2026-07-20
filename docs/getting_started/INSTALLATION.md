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

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    image: rush86999/atom-backend:latest
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=sqlite:///data/atom.db
      - ATOM_DMM_LEVEL5_ENABLED=true
    volumes:
      - atom-data:/data
  frontend:
    image: rush86999/atom-frontend:latest
    ports:
      - "3001:3001"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8001
```

To run:
```bash
docker compose up -d
```

### Method 2: Manual Clone & Virtual Environment (Local Dev)
Ideal for contribution and running the latest changes from `main`:

```bash
git clone https://github.com/rush86999/atom.git
cd atom

# 1. Setup Backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 2. Setup Frontend
cd ../frontend-nextjs
npm install --legacy-peer-deps
npm run dev -- -p 3001
```

### Method 3: Automated Installer Script
Atom provides a one-shot shell script to automate repository cloning, dependency resolution, virtual environment creation, and initial DB migration:

```bash
curl -fsSL https://raw.githubusercontent.com/rush86999/atom/main/scripts/install.sh | bash
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
   ollama run llama3
   ```
   Configure `.env` to route local execution queries:
   ```bash
   ATOM_LOCAL_ONLY=true
   OLLAMA_HOST=http://localhost:11434
   ```

### Enterprise Deployment (PostgreSQL + Redis)
For multi-user orchestration:
- Database: Configure `DATABASE_URL=postgresql://user:pass@host:5432/atom` in `.env`.
- Task Queue: Configure `REDIS_URL=redis://localhost:6379/0` for EventBus routing.
