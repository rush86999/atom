"""
Atom Backend - Application Entry Point

Launch locally:
    cd /Users/rushiparikh/projects/atom
    PYTHONPATH=/Users/rushiparikh/projects/atom:/Users/rushiparikh/projects/atom/backend \
        ./backend/venv/bin/python -m uvicorn main:app --reload --port 8000

This module is intentionally minimal but functional: it loads environment
variables, wires the core routers (health, auth, agents, workflow, canvas),
bootstraps an admin user on startup, and enables permissive CORS for local
frontend development.

For the full-featured launcher (all 40+ routers, middleware, scheduler), see
main_api_app.py — note that file is mid-refactor and currently broken.
"""
import logging
import os

from dotenv import load_dotenv

# Load .env BEFORE any module that reads env vars (database, auth, etc.)
load_dotenv()

# Resolve relative SQLite paths against the backend/ directory.
# .env typically has DATABASE_URL=sqlite:///./atom_dev.db — the './' resolves
# against the process cwd, which may be the repo root (not backend/). Anchor
# it to this file's directory so the DB is found regardless of launch cwd.
_db_url = os.getenv("DATABASE_URL", "")
if _db_url.startswith("sqlite:///") and ":memory:" not in _db_url:
    _path_part = _db_url[len("sqlite:///"):]
    # Strip leading query string if present
    _path_only = _path_part.split("?")[0]
    if not os.path.isabs(_path_only):
        _backend_dir = os.path.dirname(os.path.abspath(__file__))
        _resolved = os.path.join(_backend_dir, _path_only.lstrip("./"))
        os.environ["DATABASE_URL"] = f"sqlite:///{_resolved}"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.agent_routes import router as agent_router
from backend.api.auth_routes import router as auth_router
from backend.api.canvas_routes import router as canvas_router
from backend.api.enterprise_auth_endpoints import router as enterprise_auth_router
from backend.api.health_routes import router as health_router
from backend.api.user_management_routes import router as user_mgmt_router
from backend.api.workflow_debugging import router as workflow_router

logger = logging.getLogger("ATOM_MAIN")

app = FastAPI(
    title="Atom API",
    description="AI-powered business automation platform",
    version="6.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS (permissive for local dev; tighten via ALLOWED_ORIGINS in prod) ---
_allowed = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health_router)
app.include_router(enterprise_auth_router)  # /api/auth/login, /api/auth/register
app.include_router(auth_router)              # /api/auth/mobile/*
app.include_router(user_mgmt_router)        # /api/users/*
app.include_router(agent_router)
app.include_router(workflow_router)
app.include_router(canvas_router)


@app.on_event("startup")
def _startup_bootstrap() -> None:
    """Create the default admin user on first launch.

    Idempotent — skips if admin@example.com already exists. Password is drawn
    from ADMIN_PASSWORD env var, or securely generated and logged once.
    """
    try:
        from backend.core.admin_bootstrap import ensure_admin_user

        ensure_admin_user()
    except Exception as exc:  # pragma: no cover - startup logging only
        logger.warning("Admin bootstrap skipped: %s", exc)


@app.get("/")
async def read_root():
    return {"name": "Atom API", "version": "6.0.0", "docs": "/docs"}
