import logging
import os
import socket
from typing import Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db, engine
from core.models import User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/onboarding", tags=["Onboarding"])


def _ensure_onboarding_columns() -> None:
    """Add users.onboarding_completed/onboarding_step if the database predates
    the alembic migration that defines them (create_all never alters existing
    tables). Duplicate-column errors mean the columns already exist — that's
    success. Works on SQLite and PostgreSQL.
    """
    statements = (
        "ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN onboarding_step VARCHAR DEFAULT 'welcome'",
    )
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as exc:  # duplicate column, already applied
                if "duplicate column" not in str(exc).lower():
                    logger.warning("onboarding column ensure failed: %s", exc)


try:
    _ensure_onboarding_columns()
except Exception as exc:  # never block app startup on this
    logger.warning("onboarding column ensure skipped: %s", exc)


def _probe_ollama(host: str, port: int, timeout: float = 1.5) -> bool:
    """TCP probe the Ollama daemon. Returns True if it accepts a connection.

    Kept dependency-free (no httpx) so the wizard stays fast and reliable
    even on cold cache. We don't care about HTTP semantics — if the port
    accepts a TCP connection, Ollama is running and the wizard can offer the
    "Use local Ollama (free)" 1-click path.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

class OnboardingUpdate(BaseModel):
    step: Optional[str] = None
    completed: Optional[bool] = None

@router.post("/update")
async def update_onboarding_status(
    update_data: OnboardingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the authenticated user's onboarding progress.
    """
    if update_data.step is not None:
        current_user.onboarding_step = update_data.step

    if update_data.completed is not None:
        current_user.onboarding_completed = update_data.completed

    db.commit()
    db.refresh(current_user)

    return router.success_response(
        data={
            "onboarding_step": current_user.onboarding_step,
            "onboarding_completed": current_user.onboarding_completed
        },
        message="Onboarding status updated successfully"
    )

@router.get("/status")
async def get_onboarding_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get the authenticated user's current onboarding status.
    """
    return router.success_response(
        data={
            "onboarding_step": current_user.onboarding_step,
            "onboarding_completed": current_user.onboarding_completed
        }
    )


@router.get("/progress")
async def get_onboarding_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate first-job onboarding state for the dashboard checklist.

    Returns wizard status plus the three "getting started" signals the UI
    renders as a checklist: provider configured, agent exists, first agent
    job executed.
    """
    from core.models import AgentExecution, AgentRegistry

    provider_configured = _provider_configured()

    # Mirror the visibility rules of GET /api/agents/ (AgentGovernanceService
    # ._workspace_scope_condition): NULL/"default"-workspace agents are shared
    # and visible to everyone, so they count as "you have an agent" — the
    # checklist must agree with what the Agents page actually shows.
    from sqlalchemy import or_

    scope_filter = or_(
        AgentRegistry.workspace_id.is_(None),
        AgentRegistry.workspace_id == "default",
        AgentRegistry.tenant_id == current_user.tenant_id,
        AgentRegistry.workspace_id == current_user.workspace_id,
        AgentRegistry.user_id == current_user.id,
    )
    has_agent = (
        db.query(AgentRegistry.id).filter(scope_filter).first() is not None
    )

    first_job_done = (
        db.query(AgentExecution.id).filter(
            (AgentExecution.tenant_id == current_user.tenant_id)
            | (AgentExecution.workspace_id == current_user.workspace_id)
        ).first()
        is not None
    )

    if not first_job_done:
        # The guided "first job" path is chat — count any message the user
        # sent. (chat_sessions.message_count is not maintained by the
        # backend, so count chat_messages joined to the user's sessions.)
        from core.models import ChatMessage, ChatSession

        first_job_done = (
            db.query(ChatMessage.id).join(
                ChatSession, ChatMessage.conversation_id == ChatSession.id
            ).filter(
                ChatSession.user_id == current_user.id,
                ChatMessage.role == "user",
            ).first()
            is not None
        )

    return router.success_response(
        data={
            "onboarding_completed": bool(current_user.onboarding_completed),
            "onboarding_step": current_user.onboarding_step,
            "provider_configured": provider_configured,
            "has_agent": has_agent,
            "first_job_done": first_job_done,
        }
    )


# Env vars whose presence means a cloud LLM provider is usable without BYOK.
_PROVIDER_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENCODE_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
)


def _provider_configured() -> bool:
    """True when any LLM provider is usable: a BYOK key saved through the
    wizard/Settings, or a provider key in the environment. File-based check —
    cheap and safe to call per request.
    """
    if any(os.getenv(k) for k in _PROVIDER_ENV_KEYS):
        return True
    try:
        from core.byok_endpoints import get_byok_manager

        return len(get_byok_manager().api_keys) > 0
    except Exception as exc:
        logger.debug("provider_configured BYOK check failed: %s", exc)
        return False


@router.get("/probe-ollama")
async def probe_ollama(
    current_user: User = Depends(get_current_user),
):
    """Probe whether a local Ollama daemon is reachable.

    Powers the "Use local Ollama (free)" card in the onboarding wizard.
    Reads OLLAMA_BASE_URL if set (so a custom port/host is respected),
    otherwise defaults to localhost:11434.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Parse just host+port from the base URL; tolerate missing scheme.
    host = "localhost"
    port = 11434
    try:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = parsed.port
        elif parsed.scheme == "http" and not parsed.port:
            port = 80
        elif parsed.scheme == "https" and not parsed.port:
            port = 443
    except Exception as parse_err:
        logger.warning("probe-ollama: failed to parse OLLAMA_BASE_URL=%s (%s)", base_url, parse_err)

    reachable = _probe_ollama(host, port)
    return router.success_response(
        data={
            "reachable": reachable,
            "host": host,
            "port": port,
            # Surface the install link so the frontend card stays in sync with
            # whatever canonical docs URL Ollama is using.
            "install_url": "https://ollama.com/download",
        },
        message="Ollama reachable" if reachable else "Ollama not detected",
    )
