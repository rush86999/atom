# Getting Started

Quick start guides, installation options, and first steps with Atom.

## 📚 Quick Navigation

### Essential Guides (verified working June 2026)
- **[Quick Start](quick-start.md)** ⭐ — Fastest path to a running local server (start here)
- **[First Steps](FIRST_STEPS.md)** — What to do after the server is running
- **[Troubleshooting](TROUBLESHOOTING.md)** — Common errors and fixes
- **[Installation](INSTALLATION.md)** — Complete installation guide (pip + Docker variants)
- **[Installation Options](installation-options.md)** — Installation variants
- **[Mac Mini Install](mac-mini-install.md)** — Mac mini specific setup
- **[Install Script](install-script.md)** — Automated installation script

## 🚀 Quick Start

### Option 1: Native (SQLite, no external DB) ⭐ RECOMMENDED for first-run

**Verified working June 2026.** See [quick-start.md](./quick-start.md) for
the full version; the essentials:

```bash
git clone https://github.com/rush86999/atom.git
cd atom

# Backend deps
cd backend && python3.11 -m venv venv && ./venv/bin/pip install -r requirements.txt

# Frontend deps
cd ../frontend-nextjs && npm install --legacy-peer-deps && cd ..

# Configure (edit backend/.env with DATABASE_URL, SECRET_KEY, an LLM key)
cp backend/.env.example backend/.env

# Launch backend (FROM REPO ROOT — main_api_app.py uses backend.* imports;
# main_api_app:app is the FULL app, all 80+ routers)
PYTHONPATH=$PWD:$PWD/backend DISABLE_AUTH_RATE_LIMIT=1 \
  ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001

# In a second terminal: frontend
cd frontend-nextjs && npm run dev -- -p 3001
```

- **Frontend (UI)**: http://localhost:3001
- **Backend API**: http://localhost:8001
- **API docs (Swagger)**: http://localhost:8001/docs
- **Admin password**: auto-generated at `backend/logs/bootstrap_admin_password.txt` (mode 0600)

### Option 2: Docker

```bash
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env   # edit: generate SECRET_KEY/JWT_SECRET_KEY/BYOK_ENCRYPTION_KEY + one LLM key
docker compose -f docker-compose-personal.yml up -d --build
```

`docker-compose-personal.yml` is the single-user SQLite stack (no Postgres/Redis).
The backend Dockerfile runs `main_api_app:app` (the full app), mapped to host
port 8001. Frontend on :3001. For the full production stack (Postgres + Redis +
piece-engine), use `docker-compose.yml`.

### Option 3: DigitalOcean (1 click)
[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

## 📋 What You'll Need

### Requirements
- **Python**: 3.11+
- **Node.js**: 18+, **npm**: 9+
- **Database**: SQLite (default — zero setup) or PostgreSQL (production)
- **LLM API Key**: at least one provider (OpenAI, Anthropic, DeepSeek, Gemini, GLM, MiniMax, or Ollama for free local)
- **Optional**: Docker for containerized deployment

### LLM Provider Keys
```bash
# Add to backend/.env — at least one required for agent features
OPENAI_API_KEY=sk-...                 # https://platform.openai.com/api-keys
# ANTHROPIC_API_KEY=sk-ant-...        # https://console.anthropic.com/
# DEEPSEEK_API_KEY=...                # https://platform.deepseek.com/
# GEMINI_API_KEY=...                  # https://aistudio.google.com/app/apikey
# GLM_API_KEY=...                     # https://open.bigmodel.cn/usercenter/apikeys (GLM-5.2)
# MINIMAX_API_KEY=...                 # https://platform.minimaxi.com/
# OLLAMA_BASE_URL=http://localhost:11434/v1   # free, local — no key
```

## 🎯 First Steps After Install

See **[FIRST_STEPS.md](./FIRST_STEPS.md)** for the full walkthrough. Summary:

1. **Confirm auth**: login → get JWT → `/api/users/me`
2. **Pick an LLM provider**: edit `backend/.env`, restart
3. **Create your first agent**: `POST /api/agents`
4. **Try a workflow**: `POST /api/agent/route`
5. **Open the UI**: http://localhost:3000/auth/signin

## 🔧 Configuration

### Minimum required env vars (backend/.env)
```bash
DATABASE_URL=sqlite:///./atom_dev.db
SECRET_KEY=<run: openssl rand -base64 48>   # MUST be set or JWTs reset on restart
OPENAI_API_KEY=sk-...                        # at least one LLM provider
```

A complete template with all options is at `backend/.env.example` (every var
has a working default). The full reference — every variable, its default, and
what it does — is at [`docs/reference/ENVIRONMENT_VARIABLES.md`](../reference/ENVIRONMENT_VARIABLES.md).

## ❓ Troubleshooting

See **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** for the full guide. Most common:

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'backend.api'` | Run uvicorn from repo root with `PYTHONPATH=$PWD:$PWD/backend` |
| `ModuleNotFoundError: No module named 'main'` | Use `main_api_app:app` (full app) or `minimal_app:app` (smoke). There is no `backend/main.py`. |
| `Could not validate credentials` | `SECRET_KEY` not set — tokens reset on restart |
| Admin password lost | Read `backend/logs/bootstrap_admin_password.txt` or set `ADMIN_PASSWORD` in `.env` |
| Port in use | Use a different `--port` (e.g. `--port 8002`); update `frontend-nextjs/.env.local`'s `NEXT_PUBLIC_API_URL` to match |

## 📖 Next Steps

- **[User Guide Index](../USER_GUIDE_INDEX.md)** — Complete user documentation
- **[Agent System](../agents/README.md)** — Learn about agents
- **[Architecture](../architecture/README.md)** — How the pieces fit
- **[Execution Sandbox Layer](../architecture/SANDBOX_LAYER.md)** — How blast radius is bounded
- **[Development Setup](../development/DEVELOPMENT_SETUP.md)** — For contributors
- **[Operations](../operations/README.md)** — Deployment and monitoring

## 📖 Related Documentation

- **Installation** — Detailed installation (`INSTALLATION.md`)
- **[Development](../development/README.md)** — Development setup
- **`CLAUDE.md`** (repo root) — Engineering reference

---

*Last Updated: July 2026*

