# ATOM Development Setup Guide

> **Last Updated**: August 2026

## Quick Start

### Prerequisites
- **Python 3.11+** (required)
- **Node.js 22+** (required, Next.js 16.2.2)
- **Git** (for cloning and version control)

### Starting the Application

#### Option 1: Makefile (Recommended)

```bash
make setup       # one-shot: venv + deps + .env
make backend     # full backend on :8001
make frontend    # frontend dev server on :3001
make dev         # both together (tmux or two terminals)
```

#### Option 2: Manual Start

**Backend (Python/FastAPI):**
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

**Frontend (Next.js):**
```bash
cd frontend-nextjs
npm install --legacy-peer-deps
npm run dev -- -p 3001
```

## Accessing the Application

Once both services are running:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3001 | Main application UI |
| **Backend API** | http://localhost:8001 | API server (v8.0.0, 197 routers) |
| **API Docs** | http://localhost:8001/docs | Interactive API documentation (Swagger UI) |
| **Health Check** | http://localhost:8001/health/live | Backend liveness probe |

## Environment Configuration

### Backend Environment (`backend/.env`)

**Key settings for development:**
- `DATABASE_URL=sqlite:///./atom_dev.db` — SQLite (default, zero setup)
- `SECRET_KEY=<openssl rand -base64 48>` — required for persistent JWTs
- `BYPASS_RATE_LIMIT=1` — lift rate limits for dev (set by `make backend`)
- LLM providers are optional — server boots without any (LLM features disabled until configured via Settings > AI or `.env`)

### Frontend Environment (`frontend-nextjs/.env.local`)

Auto-created with:
```env
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_APP_NAME=ATOM Platform
```

## Troubleshooting

### Backend Issues

**Problem: "Module not found" errors**
```bash
# You're probably inside backend/ — run from repo root
cd /path/to/atom
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --port 8001
```

**Problem: Port 8001 already in use**
```bash
# Find and kill the process
lsof -i :8001          # macOS/Linux
kill -9 <PID>
# Or use a different port: --port 8002
```

**Problem: `Could not import module "main"`**
- There is no `backend/main.py`. Use `main_api_app:app` (full app) or `minimal_app:app` (smoke).

**Problem: Database errors**
```bash
rm backend/atom_dev.db   # delete dev DB
# Restart server — bootstrap recreates everything
```

### Frontend Issues

**Problem: `npm install` fails with peer-dep conflicts**
```bash
cd frontend-nextjs
npm install --legacy-peer-deps
```

**Problem: Frontend can't reach backend**
1. Verify backend: `curl http://localhost:8001/health/live`
2. Check `frontend-nextjs/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8001`
3. Restart the frontend dev server after editing `.env.local`

### Common Issues

**Problem: Virtual environment activation fails**
```bash
cd backend
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Development Workflow

### Making Changes

1. **Backend changes**: Edit Python files in `backend/`
   - FastAPI auto-reloads on file changes (`--reload` flag)
   - Check terminal for errors

2. **Frontend changes**: Edit files in `frontend-nextjs/`
   - Next.js hot-reloads automatically
   - Check browser console for errors

### Running Tests

**Backend:**
```bash
make test               # unit tests
# or
cd backend && pytest tests/ -q --tb=short
```

**E2E UI:**
```bash
make test-e2e           # E2E journey suite
# or
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh && pytest -v -n 4
```

**Frontend:**
```bash
cd frontend-nextjs && npm test
```

### Type Checking

**Backend (mypy):**
```bash
cd backend && mypy --config-file mypy.ini core/ api/
```

**Frontend (TypeScript):**
```bash
cd frontend-nextjs && npx tsc --noEmit
```

## Architecture Overview

```
ATOM Platform
├── backend/              # Python 3.11 + FastAPI API server
│   ├── main_api_app.py  # Main entry point (v8.0.0, 197 routers)
│   ├── minimal_app.py   # Smoke subset (~125 routes)
│   ├── core/            # Core business logic
│   ├── api/             # Route handlers
│   ├── tools/           # Agent tools
│   ├── integrations/    # 44+ integrations
│   ├── llm/             # LLM providers, BYOK, gateway
│   ├── tests/           # 1250+ test files
│   └── requirements.txt # Python dependencies
│
└── frontend-nextjs/     # Next.js 16.2.2 (Pages Router)
    ├── pages/           # Next.js pages (Pages Router)
    ├── components/      # React 18.3 components
    ├── hooks/           # Custom hooks
    ├── lib/             # Utilities
    └── package.json     # Node.js dependencies
```

## Next Steps

1. **Configure API Keys**: Update `backend/.env` with your actual API keys
2. **Explore API**: Visit http://localhost:8001/docs
3. **Test Features**: Try creating workflows, integrations, etc.
4. **Read the docs**: [Documentation Index](../INDEX.md)

## Getting Help

- Check the [API Documentation](http://localhost:8001/docs) when running
- Review error messages in terminal output
- Read `CLAUDE.md` in the repo root for the engineering reference
- File issues at https://github.com/rush86999/atom/issues

---

*Last Updated: August 2026*
