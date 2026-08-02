"""LLM OAuth connect + subscription-credential reuse routes (Phase D).

OpenAI/Anthropic/Google/Hugging Face OAuth flows for the BYOK credential
layer, including subscription-linked grants (ChatGPT Plus / Claude Pro reuse).
The credential intent (``oauth`` vs ``subscription``) is encoded in the OAuth
``state`` parameter so the callback persists ``credential_type`` correctly.

Security scope: consumer-session **cookie/token capture is OUT OF SCOPE** — only
OAuth-granted flows ship. See docs/security/LLM_GATEWAY_SUBSCRIPTION_REUSE.md.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.llm_credential_service import LLMCredentialService
from core.llm_oauth_handler import LLMOAuthHandler
from core.models import User
from core.security.auth_rate_limit import AuthRateLimiter

router = APIRouter(prefix="/api/v1/llm-oauth", tags=["LLM OAuth"])
logger = logging.getLogger(__name__)

# Rate limit OAuth callbacks to prevent code brute-force / DoS (same posture as
# the generic /api/v1/auth/oauth flow).
_oauth_limiter = AuthRateLimiter(limit=20, window_seconds=60)

VALID_CREDENTIAL_TYPES = ("oauth", "subscription")


def oauth_rate_limit(request: Request) -> None:
    """Rate limit OAuth callback attempts (20/min per IP).

    NOTE: ``AuthRateLimiter.check`` takes the FastAPI ``Request`` (it extracts
    the TCP peer IP itself, honoring ``TRUST_X_FORWARDED_FOR``) — not an IP
    string. Passing a bare string would crash with AttributeError.
    """
    allowed, _remaining = _oauth_limiter.check(request)
    if not allowed:
        raise HTTPException(
            status_code=429, detail="Too many OAuth attempts. Try again later."
        )


def _encryption_key() -> Optional[bytes]:
    """Fernet key for OAuth tokens, mirroring byok_endpoints / credential service.

    Returns the persisted ``BYOK_ENCRYPTION_KEY`` (bytes) when set, else None
    (dev plaintext-at-rest posture).
    """
    key = os.getenv("BYOK_ENCRYPTION_KEY")
    return key.encode() if key else None


def _build_state(provider_id: str, credential_type: str, user_id: str) -> str:
    """Encode provider + credential intent + CSRF-bound user in the state."""
    return f"llm:{provider_id}:{credential_type}:{user_id}"


def _parse_state(
    state: Optional[str], provider_id: str, user_id: str
) -> str:
    """Validate the callback ``state`` and return the credential intent.

    Rejects missing/malformed state (400), wrong provider (400), an invalid
    credential type (400), and a state bound to a different user (403 — OAuth
    CSRF: an attacker must not bind a victim's OAuth grant to their account).
    """
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state parameter")

    parts = state.split(":")
    if len(parts) != 4 or parts[0] != "llm":
        raise HTTPException(status_code=400, detail="Invalid OAuth state parameter")
    if parts[1] != provider_id:
        raise HTTPException(status_code=400, detail="OAuth state provider mismatch")
    if parts[2] not in VALID_CREDENTIAL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid credential type in state")
    if parts[3] != user_id:
        raise HTTPException(status_code=403, detail="OAuth state user mismatch")

    return parts[2]


def _credential_service(current_user: User) -> LLMCredentialService:
    return LLMCredentialService(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id or "default",
        workspace_id=getattr(current_user, "workspace_id", None) or "default",
    )


# ============================================================================
# Connect flow
# ============================================================================


@router.get("/{provider}/connect")
async def llm_oauth_connect(
    provider: str,
    credential_type: str = Query("oauth", pattern="^(oauth|subscription)$"),
    current_user: User = Depends(get_current_user),
):
    """Initiate an LLM-provider OAuth flow.

    ``credential_type`` chooses a regular token grant (``oauth``, default) or a
    subscription-linked grant (``subscription``) for ChatGPT Plus / Claude Pro
    reuse.
    """
    handler = LLMOAuthHandler(encryption_key=_encryption_key())
    state = _build_state(provider, credential_type, current_user.id)
    try:
        result = handler.get_authorization_url(provider, state=state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "authorization_url": result["authorization_url"],
        "state": state,
        "provider_id": provider,
        "credential_type": credential_type,
    }


@router.get("/{provider}/callback")
async def llm_oauth_callback(
    provider: str,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    _rl: None = Depends(oauth_rate_limit),
):
    """Complete an LLM-provider OAuth flow and persist the credential."""
    credential_type = _parse_state(state, provider, current_user.id)

    handler = LLMOAuthHandler(encryption_key=_encryption_key())
    try:
        tokens = await handler.exchange_code_for_tokens(provider, code)
        credential = handler.store_oauth_credentials(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id or "default",
            provider_id=provider,
            tokens=tokens,
            credential_type=credential_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM OAuth callback failed for {provider}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to complete LLM OAuth flow"
        )

    return {
        "success": True,
        "credential_id": credential.id,
        "provider_id": provider,
        "credential_type": credential_type,
        "message": (
            f"Connected {provider} subscription"
            if credential_type == "subscription"
            else f"Connected {provider}"
        ),
    }


# ============================================================================
# Management
# ============================================================================


@router.get("/credentials")
async def list_llm_oauth_credentials(
    current_user: User = Depends(get_current_user),
):
    """List the current user's LLM OAuth / subscription credentials."""
    svc = _credential_service(current_user)
    return {"success": True, "data": svc.list_oauth_credentials()}


@router.delete("/credentials/{credential_id}")
async def revoke_llm_oauth_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
):
    """Revoke an LLM OAuth / subscription credential (owner-scoped)."""
    svc = _credential_service(current_user)
    revoked = svc.revoke_oauth_credential(credential_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"success": True, "message": "Credential revoked"}


@router.get("/status")
async def llm_oauth_status(
    current_user: User = Depends(get_current_user),
):
    """Per-provider credential status for the current user."""
    svc = _credential_service(current_user)
    statuses = {}
    for provider_id in ("openai", "anthropic", "google", "huggingface"):
        statuses[provider_id] = svc.get_provider_status(provider_id)
    return {"success": True, "statuses": statuses}
