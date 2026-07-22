# Atom — Quick Start (Verified Working July 2026)

> **Fastest path to a running local server.** Verified end-to-end (backend
> boots, health endpoints respond, login returns a JWT). For the full
> guide with troubleshooting, see [`docs/guides/QUICKSTART.md`](../guides/QUICKSTART.md).

---

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend runtime |
| npm | 9+ | Frontend deps |
| git | any | Clone the repo |

Verify:
```bash
python3.11 --version && node --version && npm --version
```

---

## 1. Clone & install (one-time, ~3 minutes)

```bash
git clone https://github.com/rush86999/atom.git
cd atom

# Backend deps in a venv
cd backend
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt

# Frontend deps
cd ../frontend-nextjs
npm install --legacy-peer-deps
cd ..
```

## 2. Configure environment

Create `backend/.env` (the `backend/` directory, not the repo root):

```bash
# backend/.env — copy the template (every var has a working default)
cp backend/.env.example backend/.env
```

Then set the two things the template can't default for you:
```bash
# backend/.env
DATABASE_URL=sqlite:///./atom_dev.db     # SQLite = zero external setup
SECRET_KEY=<run: openssl rand -base64 48>  # MUST be set or JWTs reset on restart
OPENAI_API_KEY=sk-...                     # At least one LLM provider required
# ANTHROPIC_API_KEY=sk-ant-...            # Optional alternates
# DEEPSEEK_API_KEY=...
# Or go fully local: ATOM_LOCAL_ONLY=true + OLLAMA_BASE_URL=http://localhost:11434/v1
```

A complete template lives at `backend/.env.example`; the full reference
(every var, its default, what it does) is at
[`docs/reference/ENVIRONMENT_VARIABLES.md`](../reference/ENVIRONMENT_VARIABLES.md).

## 3. Launch the backend

Run the **FULL app** (`main_api_app:app`, all 80+ routers). **From the repo
root** (not from `backend/`):

```bash
cd /path/to/atom
PYTHONPATH=$PWD:$PWD/backend DISABLE_AUTH_RATE_LIMIT=1 \
  ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

`DISABLE_AUTH_RATE_LIMIT=1` only lifts the registration rate-limit so you can
create test users freely; remove it for any shared/production deployment.

> **Minimal app (smoke only):** `minimal_app.py` boots a ~125-route subset for
> fast checks (`uvicorn minimal_app:app --port 8000`). It lacks skills,
> marketplace, workflows, canvas, integrations, etc. Use `main_api_app:app`
> (above) to actually use Atom. The `scripts/dev.sh` helper launches
> `minimal_app:app` — use `make backend` for the full app.

### Where's my admin password?

On first boot the app auto-creates `admin@example.com` and writes a
randomly-generated password to a **file** (not stdout — stdout is too
easy to leak via log aggregators):

```
backend/logs/bootstrap_admin_password.txt   # mode 0600, owner-only readable
```

Read it:
```bash
cat backend/logs/bootstrap_admin_password.txt
```

To control the password yourself, set `ADMIN_PASSWORD` in `backend/.env`
before launching.

## 4. Verify it works

```bash
# Liveness (sub-10ms)
curl http://localhost:8001/health/live
# → {"status":"alive","timestamp":"..."}

# Readiness (database + disk checks)
curl http://localhost:8001/health/ready

# Interactive API docs
open http://localhost:8001/docs
```

## 5. Log in

```bash
PWD_VAL=$(cat backend/logs/bootstrap_admin_password.txt)

TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin@example.com\",\"password\":\"$PWD_VAL\"}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"

# Authenticated request
curl http://localhost:8001/api/users/me -H "Authorization: Bearer $TOKEN"
```

## 6. Launch the frontend (optional, for the UI)

In a second terminal:

```bash
cd /path/to/atom/frontend-nextjs
npm run dev -- -p 3001
# → http://localhost:3001
```

Sign in at http://localhost:3001/auth/signin with
`admin@example.com` + the password from step 3. The backend is
CORS-enabled for `http://localhost:3001` by default.

---

## Common errors

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'backend.api'` | Run from repo root with `PYTHONPATH=$PWD:$PWD/backend` (see step 3) |
| `ModuleNotFoundError: No module named 'main'` / `Could not import module "main"` | You're using `main:app` — there is no `backend/main.py`. Use `main_api_app:app` (the full app) or `minimal_app:app` (smoke). |
| `Could not validate credentials` on every request | `SECRET_KEY` not set — tokens reset on restart. Set it in `backend/.env` |
| Admin password lost | Delete the user and restart, or set `ADMIN_PASSWORD` in `backend/.env` |
| Port 8001 in use | Use `--port 8002` (or any free port). Update `frontend-nextjs/.env.local`'s `NEXT_PUBLIC_API_URL` to match. |
| `npm install` fails | Use `npm install --legacy-peer-deps` (peer-dep conflicts in the Next.js stack) |

For the full troubleshooting guide see [`docs/getting_started/TROUBLESHOOTING.md`](./TROUBLESHOOTING.md).

---

## What's next

- **Explore the API**: http://localhost:8001/docs (Swagger UI)
- **Add LLM providers**: edit `backend/.env` and restart (GLM-5.2, Gemini, MiniMax, Ollama all supported)
- **Run the test suite**: `pytest backend/tests/unit/ -v`
- **Production setup** (PostgreSQL): see [`docs/guides/QUICKSTART.md`](../guides/QUICKSTART.md) § Production Setup
- **Docker setup** (single-user SQLite stack): `cp .env.personal .env && docker compose -f docker-compose-personal.yml up -d --build` (Frontend :3001, Backend :8001)

---

**Last Updated**: July 2026 · **Status**: Verified working ✅
