import logging
import os
import socket
from typing import Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/onboarding", tags=["Onboarding"])


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
