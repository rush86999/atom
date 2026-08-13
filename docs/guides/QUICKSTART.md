# Atom Platform - Quick Start Guide

> **Last Updated:** August 2026  
> **Status:** Production ready ✅ (launch command verified working)

---

## Quick Launch (SQLite, no external DB)

The fastest path to a running backend — verified working as of August 2026.

### 1. Clone & Install
```bash
git clone https://github.com/rush86999/atom.git
cd atom

# Backend dependencies (use the venv if present, else pip install)
cd backend
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt

# Frontend dependencies
cd ../frontend-nextjs
npm install --legacy-peer-deps
cd ..
```

### 2. Environment Configuration
Create `backend/.env` (copy from `backend/.env.example` and fill in):

```bash
# Database (SQLite for local dev — no external DB required)
DATABASE_URL=sqlite:///./atom_dev.db

# JWT signing key — generate with: openssl rand -base64 48
# MUST be set for JWT sessions to persist across restarts.
SECRET_KEY=<your-generated-key>

# AI Providers (optional — server boots without any; LLM features disabled)
# Options: OPENCODE_API_KEY (recommended), any provider key, or ATOM_LOCAL_ONLY=true + Ollama
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=...
# DEEPSEEK_API_KEY=...
# GOOGLE_API_KEY=...
# OPENCODE_API_KEY=oc_...        # Low-cost subscription (~90% savings)
# ATOM_LOCAL_ONLY=true           # Fully local mode (requires Ollama)
# OLLAMA_BASE_URL=http://localhost:11434/v1
```

### 3. Launch the Backend
```bash
# From the repo root (NOT from backend/ — main_api_app.py uses backend.* imports)
cd /path/to/atom
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

On first launch, the app auto-creates `admin@example.com` and writes a randomly-generated password to a **file** (not stdout — stdout is too easy to leak via log aggregators):

```
backend/logs/bootstrap_admin_password.txt   # mode 0600, owner-only readable
```

Read it:
```bash
cat backend/logs/bootstrap_admin_password.txt
```

The startup log will show:
```
INFO:ATOM_BOOTSTRAP:BOOTSTRAP: User admin@example.com found. Resetting password...
WARNING:ATOM_BOOTSTRAP:BOOTSTRAP: Generated temporary password written to .../logs/bootstrap_admin_password.txt (mode 0600). Set ADMIN_PASSWORD env var for production.
```

To control the password, set `ADMIN_PASSWORD` in `backend/.env` before launching (recommended for production).

### 4. Verify Health
```bash
curl http://localhost:8001/health/live    # → {"status":"alive"}
curl http://localhost:8001/health/ready   # → database + disk checks
curl http://localhost:8001/docs           # → OpenAPI Swagger UI
```

### 5. Login
```bash
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"<password-from-log>"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl http://localhost:8001/api/users/me -H "Authorization: Bearer $TOKEN"
# → {"email":"admin@example.com","role":"workspace_admin", ...}
```

### 6. Launch the Frontend (optional)
```bash
cd frontend-nextjs
npm run dev   # → http://localhost:3001
```

The backend is CORS-enabled for `http://localhost:3001` by default.

---

## Production Setup (PostgreSQL)

### 1. Database
```bash
createdb atom_production
export DATABASE_URL="postgresql://user:password@localhost:5432/atom_production"
```

### 2. Run Migrations
```bash
cd backend
# Note: run alembic from OUTSIDE the backend/ dir to avoid the local
# alembic/ package shadowing the installed alembic binary.
cd ..
DATABASE_URL="postgresql://..." ./backend/venv/bin/alembic \
  -c backend/alembic.ini upgrade head
```

### 3. Launch
```bash
ENVIRONMENT=production \
SECRET_KEY=<strong-key> \
DATABASE_URL=postgresql://... \
PYTHONPATH=$PWD:$PWD/backend \
./backend/venv/bin/python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8001
```

In production, `SECRET_KEY` is **required** (the app refuses to start without it).

---

## Docker Launch (Personal Edition)

```bash
cp .env.personal .env   # edit: generate SECRET_KEY/JWT_SECRET_KEY/BYOK_ENCRYPTION_KEY + one LLM key
docker compose -f docker-compose-personal.yml up -d --build
# Frontend: http://localhost:3001   Backend: http://localhost:8001   Swagger: http://localhost:8001/docs
```

The Personal Edition compose runs the **full app** (`main_api_app:app`) on SQLite — no Postgres/Redis required. The backend Dockerfile sets `WORKDIR /app/backend` and `PYTHONPATH=/app:/app/backend` so both bare and `backend.*` imports resolve. For the full production stack (Postgres + Redis + piece-engine), use `docker-compose.yml`.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'backend.api'"
Launch from the **repo root**, not from `backend/`. `main_api_app.py` uses `from backend.api...` imports which require the repo root on `PYTHONPATH`. Use `main_api_app:app` (the full app) — there is no `backend/main.py`.

### "Could not validate credentials" (401 on every authenticated request)
Two possible causes:
1. `SECRET_KEY` not set in `.env` — tokens are signed with a random key that changes on restart. Set a persistent `SECRET_KEY`.
2. Historical bug: `core/auth.get_current_user` didn't read the `user_id` JWT claim used by EnterpriseAuthService. Fixed (now reads sub/id/user_id).

### Admin password lost
Delete the admin user from the DB and restart — the bootstrap will recreate it:
```bash
sqlite3 backend/atom_dev.db "DELETE FROM users WHERE email='admin@example.com'"
```
Or set `ADMIN_PASSWORD` in `backend/.env` before launching.

### Alembic commands fail with "No module named 'alembic.config'"
The local `backend/alembic/` directory shadows the installed `alembic` package. Run alembic from outside `backend/`:
```bash
cd /path/to/atom
./backend/venv/bin/alembic -c backend/alembic.ini current
```

---

## Quick Examples

### Multi-Agent Workflow
```
You: "Analyze sales data and create marketing strategy"
Atom: [Activates Meta-Agent Router → Classifies as TASK intent →
       FleetAdmiral recruits analyst + marketing agents →
       Conductor Agent orchestrates PARALLEL execution →
       Canvas presents results with interactive charts]
```

### Memory-Enhanced Response
```
You: "What did we decide about the Q4 budget?"
Atom: "Based on Episode #45 (Budget Review, Oct 15): You approved $50K
       for marketing with a 30-day review condition. [Canvas shows the
       original budget chart you approved with your feedback highlighted]"
```

### GraphRAG Multi-Hop Query
```
You: "Show how our pricing connects to customer churn"
Atom: "Tracing relationships: Pricing → (hop 1) → Customer Signups →
       (hop 2) → Usage Patterns → (hop 3) → Churn Risk. [Canvas shows
       knowledge graph with 12 connected entities]"
```

---

## Key Features at a Glance

### 🤖 Multi-Agent Orchestration
- **Queen Agent** — Structured workflow automation (scheduled, repeatable)
- **Fleet Admiral** — Open-ended task resolution (dynamic specialist recruitment)
- **Conductor Agent** — 5 execution strategies (SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE)
- **Maturity Tiers** — STUDENT → INTERN → SUPERVISED → AUTONOMOUS (graduation at 10/25/50 clean episodes)

### 💼 Office Automation & Canvas
- Real-time Excel/Word/PPTX co-editing (no Microsoft Office required)
- Formula-evaluating workbook runtime (LibreOffice → `formulas` lib → openpyxl)
- Interactive Canvas co-editing with live WebSocket sync
- Bi-directional agent↔document sync

### 🧩 Mini-Apps (Aug 2026)
- Agent-authored stateful canvas apps (Firecracker microVM)
- Per-instance user↔agent chat
- Versioned copy-on-install distribution

### 🔌 46+ Business Integrations
CRM (Salesforce, HubSpot), Communication (Slack, Teams, Gmail, Discord), Project Management (Jira, Linear, Notion, GitHub), Finance (Stripe, QuickBooks, Xero), Support (Zendesk, Freshdesk), Storage (Google Drive, OneDrive), and more.

### 🧠 Memory & Intelligence
- Per-turn fact extraction (5 categories, sub-ms SQL + LanceDB semantic)
- Episodic memory (hybrid PG+LanceDB, 4 retrieval modes)
- GraphRAG (6 entity types, multi-hop, Leiden communities, JIT verification)
- Learning LLM Router (feedback-based re-ranking)
- Self-evolution (Reflection Pool → Memento-Skills → AlphaEvolver)

### 🛡️ Security (Default-On)
- Execution sandbox (FS scope, tool whitelist, caps, Firecracker microVM)
- Encrypted credentials (Fernet, production fails closed)
- Per-agent capability bindings (zero-trust tool scoping)
- Outbound gatekeeper (rate limits, masking, HITL approval)
- Data-taint tracking (restricted data blocks egress)

---

## Common Tasks

### Run Tests
```bash
# Unit tests
PYTHONPATH=$PWD:$PWD/backend pytest backend/tests/unit/ -v

# E2E tests (requires running backend)
cd backend/tests/e2e_ui && ./scripts/start-e2e-env.sh
pytest backend/tests/e2e_ui/ -v -n 4
```

### Build for Production
```bash
cd frontend-nextjs
npm run build
npm start
```

### Configure Additional LLM Providers
Edit `backend/.env` and add provider keys:
```bash
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=...
GOOGLE_API_KEY=...
OPENCODE_API_KEY=oc_...
# Or fully local:
ATOM_LOCAL_ONLY=true
OLLAMA_BASE_URL=http://localhost:11434/v1
```

[LLM Providers Guide →](../guides/LLM_PROVIDERS.md)

---

## Architecture Overview

### Tech Stack
- **Frontend**: Next.js 15, React 18, TypeScript
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0
- **Database**: PostgreSQL (prod) / SQLite (dev) + embedded LanceDB
- **Vector Store**: LanceDB (embedded) / S3-R2 (SaaS)
- **Message Queue**: Redis (RQ) — optional, degrades gracefully
- **Desktop**: Tauri (macOS menubar)
- **Mobile**: React Native (Expo)

### Project Structure
```
atom/
├── backend/                    # Python FastAPI backend
│   ├── core/                   # Core modules (agents, governance, memory, sandbox)
│   ├── api/                    # REST API routes
│   ├── tools/                  # Agent tools (canvas, browser, office, integrations)
│   ├── integrations/           # 46+ service integrations
│   ├── models.py               # SQLAlchemy models
│   └── main_api_app.py         # Full app entry point (v8.0.0, 197 routers)
├── frontend-nextjs/            # Next.js web UI
├── mobile/                     # React Native (Expo)
├── menubar/                    # Tauri macOS menubar
├── docs/                       # Documentation
└── Makefile                    # Common tasks
```

---

## Next Steps

1. **Read the User Guide** → [guides/USER_GUIDE.md](../guides/USER_GUIDE.md)
2. **Explore Agent Governance** → [guides/AGENT_MATURITY_GOVERNANCE.md](../guides/AGENT_MATURITY_GOVERNANCE.md)
3. **Set up LLM Providers** → [guides/LLM_PROVIDERS.md](../guides/LLM_PROVIDERS.md)
4. **Try Mini-Apps** → [guides/MINI_APPS_GUIDE.md](../guides/MINI_APPS_GUIDE.md)
5. **Configure Integrations** → [integrations/THIRD_PARTY_INTEGRATIONS.md](../integrations/THIRD_PARTY_INTEGRATIONS.md)
6. **Deploy to Production** → [operations/production-readiness.md](../operations/production-readiness.md)

---

**Last Updated:** August 2026  
**Status:** Production ready ✅