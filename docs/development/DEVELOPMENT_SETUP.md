# Development Setup

> For contributors. Extends [Quick Start](../getting_started/quick-start.md)
> with testing, linting, type-checking, and the dev-loop ergonomics.

---

## Prerequisites

- **Python 3.11+** (3.14 works; the codebase is tested against 3.11)
- **Node.js 18+** and **npm 9+**
- **git**
- **openssl** (for generating `SECRET_KEY`)
- **sqlite3** CLI (optional but useful for inspecting the dev DB)
- **PostgreSQL 14+** (only if you want to test against Postgres — SQLite is the default)

Verify:
```bash
python3.11 --version && node --version && npm --version && git --version
```

---

## One-time setup

### 1. Clone

```bash
git clone https://github.com/rush86999/atom.git
cd atom
```

### 2. Backend venv + deps

```bash
cd backend
python3.11 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -r requirements-dev.txt  # pytest, mypy, etc. (if present)
cd ..
```

### 3. Frontend deps

```bash
cd frontend-nextjs
npm install --legacy-peer-deps
cd ..
```

### 4. Environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` — the minimum required:

```bash
DATABASE_URL=sqlite:///./atom_dev.db
SECRET_KEY=$(openssl rand -base64 48)   # paste the actual output, not the command
OPENAI_API_KEY=sk-...                    # at least one LLM provider
```

For local-only (free, no API key) LLM, use Ollama instead:
```bash
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:8b
```

---

## Daily dev loop

### Start the backend (with hot reload)

```bash
# From repo root — NOT from backend/
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn minimal_app:app --reload --port 8000
```

The `--reload` flag watches for file changes and restarts automatically.

**Aliases you can add to your shell**:

```bash
# ~/.zshrc or ~/.bashrc
alias atom-dev='cd /path/to/atom && PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn minimal_app:app --reload --port 8000'
alias atom-fe='cd /path/to/atom/frontend-nextjs && npm run dev'
```

### Start the frontend

```bash
cd frontend-nextjs
npm run dev
# → http://localhost:3000
```

### Verify both are up

```bash
curl http://localhost:8001/health/live    # backend liveness
curl http://localhost:8001/health/ready   # backend readiness
curl http://localhost:3000                # frontend HTML
```

---

## Admin password

On first boot, the bootstrap writes a random admin password to:

```
backend/logs/bootstrap_admin_password.txt   # mode 0600
```

For dev, set a known password in `backend/.env`:
```
ADMIN_PASSWORD=dev-only-not-for-production
```

Login: `POST /api/auth/login` with `{"username":"admin@example.com","password":"..."}`.

⚠️ **Never commit `.env` or the password file.** Both are in `.gitignore`.

---

## Testing

### Unit tests

```bash
# Run from repo root with PYTHONPATH set (matches launch env)
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m pytest backend/tests/unit/ -v

# Specific module
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m pytest backend/tests/unit/core/test_sandbox_policy.py -v

# With coverage
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m pytest backend/tests/ \
  --cov=core --cov-report=html
```

### E2E tests

```bash
cd backend/tests/e2e_ui
./scripts/start-e2e-env.sh
pytest . -v -n 4    # 4 parallel workers
```

### Frontend tests

```bash
cd frontend-nextjs
npm test             # jest
npm run test:e2e     # playwright (requires the dev server running)
```

---

## Type checking & linting

```bash
# mypy (enforced in CI)
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m mypy backend/core/ --config-file mypy.ini

# Frontend
cd frontend-nextjs
npm run lint
npm run type-check
```

---

## Database

### SQLite (default — zero setup)

Schema is created automatically via `Base.metadata.create_all` on first
boot. The dev DB lives at `backend/atom_dev.db`.

Inspect it:
```bash
sqlite3 backend/atom_dev.db ".tables"
sqlite3 backend/atom_dev.db "SELECT email, role FROM users;"
```

### Migrations (Alembic)

⚠️ **Run alembic from the repo root, not from `backend/`** — the local
`backend/alembic/` directory shadows the installed package.

```bash
./backend/venv/bin/alembic -c backend/alembic.ini current     # current rev
./backend/venv/bin/alembic -c backend/alembic.ini history     # all revisions
./backend/venv/bin/alembic -c backend/alembic.ini upgrade head # apply pending
./backend/venv/bin/alembic -c backend/alembic.ini downgrade -1 # rollback one
```

To create a new migration:
```bash
./backend/venv/bin/alembic -c backend/alembic.ini revision -m "description"
```

**SQLite hybrid-DB pattern**: the dev DB has schema advanced via
`Base.metadata.create_all` while alembic bookkeeping lags. New
migrations must use `op.batch_alter_table()` and guard with
`_table_exists()` / `_column_exists()`. See `CLAUDE.md` § Database
Migrations.

### PostgreSQL (optional, for production-parity testing)

```bash
createdb atom_dev
export DATABASE_URL="postgresql://user:pass@localhost:5432/atom_dev"
./backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

---

## Common dev tasks

### Add a new API route

1. Create the route file in `backend/api/your_routes.py`
2. Register it in `backend/main_api_app.py` (search for `app.include_router`) —
   that's the full app; registering in `minimal_app.py` won't expose the route
   in production.
3. Add auth via `Depends(get_current_user)` — see
   `CLAUDE.md` § Database Session Patterns
4. Write tests in `backend/tests/unit/api/test_your_routes.py`
5. Never leak `str(e)` to clients — see `CLAUDE.md` § Error Handling

### Add a new tool

1. Create `backend/tools/your_tool.py`
2. Register it in `backend/tools/registry.py`
3. If the tool touches the filesystem or network, verify it's covered
   by the [sandbox layer](../architecture/SANDBOX_LAYER.md)
4. Add tests in `backend/tests/unit/test_your_tool.py`

### Add a new LLM provider

1. Add to `PROVIDER_TIERS` and `COST_EFFICIENT_MODELS` in
   `backend/core/llm/byok_handler.py`
2. Add to `FRONTIER_MODELS` and `_FRONTIER_BY_PROVIDER` in
   `backend/core/hallucination_config.py` if it's frontier-class
3. Add to `CACHE_CAPABILITIES` in `backend/core/llm/cache_aware_router.py`
4. Add pricing to `backend/data/ai_pricing_cache.json`
5. Add provider definition to `backend/data/byok_config.json`
6. Write routing tests (see `backend/tests/unit/llm/test_glm_routing.py`
   for the template — copy it for your new provider)

### Run the full test suite before a PR

```bash
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m pytest backend/tests/unit/ -v
cd frontend-nextjs && npm test && cd ..
```

CI runs the same suite plus mypy — see `.github/workflows/`.

---

## Debugging

### Enable verbose logging

In `backend/.env`:
```
LOG_LEVEL=DEBUG
STRUCTLOG_LEVEL=DEBUG
```

Tail the structured log:
```bash
tail -f backend/logs/atom.log | jq .    # pretty-print JSON logs
```

### Drop into a debugger

Add this anywhere in backend code to drop into pdb:
```python
import pdb; pdb.set_trace()
```

The `--reload` uvicorn flag will restart and hit your breakpoint.

### Inspect the DB during a debug session

```bash
sqlite3 backend/atom_dev.db
> .tables
> SELECT * FROM agent_executions ORDER BY created_at DESC LIMIT 5;
> .quit
```

---

## Contributing

See [`CONTRIBUTING.md`](../../CONTRIBUTING.md) for:
- Security guidelines (NEVER commit `.claude/`, `.env`, secrets)
- PR process
- Commit message conventions
- Code quality standards (`backend/docs/CODE_QUALITY_STANDARDS.md`)

---

**Last Updated**: June 30, 2026
