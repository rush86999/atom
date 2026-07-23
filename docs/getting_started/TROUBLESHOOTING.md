# Troubleshooting

> Common errors and verified fixes. If your issue isn't here, check
> [Quick Start](./quick-start.md) first, then read the logs:
> ```bash
> tail -f backend/logs/atom.log     # structured logs
> ```

---

## Backend won't start

### `ModuleNotFoundError: No module named 'backend.api'`

**Cause**: You ran the launch command from inside `backend/` instead of
the repo root.

**Fix**: Launch from the repo root with both paths on PYTHONPATH:
```bash
cd /path/to/atom
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

**Why**: `backend/main_api_app.py` uses `from backend.api...` imports which
require the repo root on `PYTHONPATH`. The `$PWD:$PWD/backend` pattern puts
both on the search path so bare-name imports (`from advanced_workflow_orchestrator import ...`)
AND `backend.*` imports both resolve.

### `ModuleNotFoundError: No module named 'main'`

**Cause**: You're using `main:app` as the entrypoint. There is **no**
`backend/main.py` — the canonical full app is `main_api_app:app`.

**Fix**: Use `main_api_app:app` (the full app, all 80+ routers):
```bash
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --port 8001
```
`minimal_app:app` (~125-route smoke subset) also exists for fast checks.

### `Could not import module "main"` (uvicorn error)

**Cause**: Same as above — `main:app` doesn't exist.

**Fix**: Use `main_api_app:app`. Verify the venv + module resolve:
```bash
ls backend/venv/bin/python        # should exist
ls backend/main_api_app.py        # should exist
```

### `Error loading ASGI app`

**Cause**: Most often you passed a module name that doesn't exist. The
canonical entrypoint is `main_api_app:app`. (If you saw old docs telling
you `main_api_app` was "broken" and to use `main` — that advice was
backwards and has been corrected.)

**Fix**:
```bash
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --port 8001
```

---

## Authentication issues

### `Could not validate credentials` on every authenticated request

**Two causes**:

1. **`SECRET_KEY` not set in `.env`** — JWTs are signed with a random
   key that changes on every restart. Generate a persistent one:
   ```bash
   openssl rand -base64 48
   ```
   Put it in `backend/.env` as `SECRET_KEY=...` and restart.

2. **Token expired** — JWTs expire after 1 hour by default. Re-run the
   login curl from [Quick Start](./quick-start.md) step 5.

### Admin password lost

The password is written to `backend/logs/bootstrap_admin_password.txt`
on first boot. If you've lost it:

**Option A** — set a known password before launch:
```bash
# In backend/.env
ADMIN_PASSWORD=your-new-password
```
Then restart. On restart the bootstrap resets the admin password to this
value.

**Option B** — delete the admin user and let bootstrap recreate:
```bash
sqlite3 backend/atom_dev.db "DELETE FROM users WHERE email='admin@example.com'"
# Then restart the server
```

### Login returns 200 but `/api/users/me` returns 401

**Cause**: The `Authorization` header is missing or malformed.

**Fix**: The header must be exactly `Authorization: Bearer <token>`:
```bash
TOKEN="eyJhbGc..."   # paste the full token
curl http://localhost:8001/api/users/me -H "Authorization: Bearer $TOKEN"
```

---

## Database issues

### `sqlite3.OperationalError: no such table: X`

**Cause**: Schema hasn't been created. On first boot, `Base.metadata.create_all`
runs automatically — but if the DB was deleted or the bootstrap was
interrupted, tables may be missing.

**Fix**: Stop the server, delete the dev DB, restart:
```bash
rm backend/atom_dev.db
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

The bootstrap will recreate everything.

### `no such table: model_catalog` (warning in logs)

**Cause**: A non-critical warning during model-router initialization.
The `model_catalog` table is optional (used for model exclusion in
routing). The app continues without it.

**Fix**: None needed — safe to ignore. If you want it gone:
```bash
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -c "
from core.database import Base, engine
from core.models import ModelCatalog  # adjust import if needed
Base.metadata.create_all(engine, tables=[ModelCatalog.__table__])
"
```

### PostgreSQL: `connection refused` / `authentication failed`

**Cause**: Wrong `DATABASE_URL` or PostgreSQL isn't running.

**Fix**:
```bash
pg_isready                              # verify Postgres is up
psql $DATABASE_URL -c "SELECT 1;"       # verify credentials
```

The `DATABASE_URL` format is
`postgresql://user:password@host:5432/dbname`.

### Alembic: `No module named 'alembic.config'`

**Cause**: The local `backend/alembic/` directory shadows the installed
`alembic` package.

**Fix**: Run alembic from the repo root, not from `backend/`:
```bash
cd /path/to/atom
./backend/venv/bin/alembic -c backend/alembic.ini current
./backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

### Alembic: `duplicate column` or `no such table` errors

**Cause**: The dev DB is a hybrid — schema advanced via
`Base.metadata.create_all`, alembic bookkeeping lags. This is the
documented SQLite hybrid-DB pattern.

**Fix**: Stamp to the nearest mergepoint then upgrade:
```bash
./backend/venv/bin/alembic -c backend/alembic.ini stamp <merge_rev> --purge
./backend/venv/bin/alembic -c backend/alembic.ini upgrade head
```

See `CLAUDE.md` § Database Migrations for the full reconciliation procedure.

---

## Frontend issues

### `npm install` fails with peer-dep conflicts

**Fix**: Use the legacy resolver:
```bash
cd frontend-nextjs
npm install --legacy-peer-deps
```

### Frontend can't reach backend (`Network Error`)

**Cause**: Backend isn't running, or it's on a different port.

**Fix**:
1. Verify backend: `curl http://localhost:8001/health/live`
2. Check `frontend-nextjs/.env.local`:
   ```
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
   ```
3. Restart the frontend dev server after editing `.env.local`.

### Sign-in page shows but login fails

**Cause**: Frontend is hitting a different backend than the one your
admin user was created on, OR the password file was regenerated.

**Fix**:
1. Read the current password: `cat backend/logs/bootstrap_admin_password.txt`
2. Sign in at http://localhost:3000/auth/signin with that password

---

## LLM / agent issues

### Agents return errors or "no provider configured"

**Cause**: No LLM provider key is set in `backend/.env`.

**Fix**: Set at least one (see [First Steps](./FIRST_STEPS.md) § 2).
Restart the server after editing `.env`.

### Ollama agent returns `ConnectionRefusedError`

**Cause**: Ollama isn't running locally.

**Fix**:
```bash
ollama serve                            # start Ollama
ollama pull llama3:8b                   # pull a model
curl http://localhost:11434/v1/models   # verify it's up
```

Then set in `backend/.env`:
```
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:8b
```

### Agent stuck at STUDENT tier

This is **by design** — new agents start read-only. They graduate to
INTERN after accumulating successful executions. To force-promote for
testing:
```bash
curl -X POST http://localhost:8001/api/agents/{agent_id}/promote \
  -H "Authorization: Bearer $TOKEN"
```

⚠️ Don't do this in production — see
[`docs/security/TRUST_VS_SANDBOX.md`](../security/TRUST_VS_SANDBOX.md)
for why tier is routing, not security.

---

## Performance

### Slow first request after launch

**Cause**: First request triggers lazy imports and embedding model
loads. Subsequent requests are fast.

**Fix**: None needed — warmup is one-time. Verify with:
```bash
# First request: ~5s
time curl http://localhost:8001/health/ready

# Second request: <50ms
time curl http://localhost:8001/health/ready
```

### High memory usage

**Cause**: LanceDB (vector store) loads embedding models into memory.
FastEmbed (default) uses ~200MB; heavier models use more.

**Fix**: Reduce embedding footprint in `backend/.env`:
```
EMBEDDING_PROVIDER=fastembed
FASTEMBED_MODEL=BAAI/bge-small-en-v1.5    # smallest model
```

---

## Getting more help

1. **Read the logs**: `tail -f backend/logs/atom.log`
2. **Check health**: `curl http://localhost:8001/health/ready`
3. **Browse the API**: http://localhost:8001/docs (Swagger UI)
4. **Search the codebase**: `grep -r "error message" backend/core/`
5. **Read `CLAUDE.md`**: the engineering reference covers everything

For bugs, file an issue at
https://github.com/rush86999/atom/issues with:
- The exact command you ran
- The full error message (not just the last line)
- Output of `curl http://localhost:8001/health/ready`
- Output of `cat backend/.env` **with secrets redacted**

---

**Last Updated**: July 2026
