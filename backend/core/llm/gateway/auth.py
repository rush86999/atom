"""Gateway identity resolution and authentication.

Order of precedence for a gateway request secret:
    1. ``x-api-key`` header (``atom_sk_*`` gateway key)
    2. ``Authorization: Bearer atom_sk_*`` gateway key
    3. JWT (via ``core.auth.get_current_user`` — cookie fallback, revocation,
       and ACTIVE-status checks are reused)
    4. Otherwise -> 401

Gateway keys are stored as SHA-256 hashes only (plaintext never persisted).
See docs/architecture/LLM_GATEWAY.md.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import GatewayApiKey, User, UserStatus

logger = logging.getLogger(__name__)

# Per-key sliding-window rate limit state (in-memory). key_hash -> deque of
# request timestamps within the current 60s window.
_RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_state: Dict[str, Deque[float]] = {}
_rate_limit_lock = threading.Lock()


@dataclass
class GatewayIdentity:
    """Resolved identity for a gateway request."""

    user_id: str
    tenant_id: str
    workspace_id: str
    auth_method: str  # "api_key" | "jwt"
    api_key_id: Optional[str] = None
    user: Optional[User] = None
    rate_limit_per_minute: int = 60

    def to_audit(self) -> Dict[str, str]:
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "auth_method": self.auth_method,
            "api_key_id": self.api_key_id or "",
        }


def hash_api_key(plaintext: str) -> str:
    """SHA-256 hash of a gateway key (the only form ever stored)."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_key_prefix(plaintext: str) -> str:
    """``atom_sk_`` + 4 random chars for human identification.

    The prefix is generated independently of the secret material (not derived
    from the key's hex tail) so the stored/displayed prefix cannot narrow a
    brute-force of the full key. Previously this used ``plaintext[-4:]``,
    exposing 4 hex chars of the key.
    """
    import secrets as _secrets
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "atom_sk_" + "".join(_secrets.choice(alphabet) for _ in range(4))


def _check_rate_limit(key_hash: str, limit_per_minute: int) -> None:
    """Sliding-window per-key rate limit -> 429 when exceeded."""
    if limit_per_minute <= 0:
        return
    now = time.time()
    with _rate_limit_lock:
        timestamps = _rate_limit_state.setdefault(key_hash, __import__("collections").deque())
        # Purge timestamps outside the window
        while timestamps and now - timestamps[0] >= _RATE_LIMIT_WINDOW_SECONDS:
            timestamps.popleft()
        if len(timestamps) >= limit_per_minute:
            logger.warning(f"Gateway rate limit exceeded for key {key_hash[:8]}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        timestamps.append(now)
        # Purge dead keys: drop entries whose deque is fully outside the window
        # so a key used once and never again doesn't leak forever. A key that's
        # still in use keeps its deque (it'll be repopulated on the next call).
        if len(_rate_limit_state) > 1000:
            stale = [
                k for k, v in _rate_limit_state.items()
                if not v or now - v[-1] >= _RATE_LIMIT_WINDOW_SECONDS
            ]
            for k in stale:
                _rate_limit_state.pop(k, None)


def _extract_secret(request: Request) -> Optional[str]:
    """Return the gateway secret from x-api-key or Authorization: Bearer."""
    x_api_key = request.headers.get("x-api-key")
    if x_api_key:
        return x_api_key.strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def _resolve_api_key(
    plaintext: str, db: Session, request: Request
) -> GatewayIdentity:
    """Resolve identity from an ``atom_sk_*`` gateway key."""
    key_hash = hash_api_key(plaintext)
    row = db.query(GatewayApiKey).filter(GatewayApiKey.key_hash == key_hash).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "Invalid API key"}},
        )

    now = datetime.now(timezone.utc)
    if not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "API key revoked"}},
        )
    if row.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "API key revoked"}},
        )
    if row.expires_at is not None and row.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "API key expired"}},
        )

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "Invalid API key"}},
        )
    # Round-43 rule: reject non-ACTIVE users even with a valid key.
    user_status = getattr(user, "status", UserStatus.ACTIVE.value)
    if str(user_status) != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "User account is not active"}},
        )

    rate_limit = row.rate_limit_per_minute or 60
    _check_rate_limit(key_hash, rate_limit)

    # Best-effort usage bump (never fails the request).
    try:
        row.last_used = now
        row.total_requests = (row.total_requests or 0) + 1
        db.commit()
    except Exception:
        db.rollback()

    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    return GatewayIdentity(
        user_id=row.user_id,
        tenant_id=row.tenant_id or resolve_tenant_id(row.user_id),
        workspace_id=row.workspace_id or resolve_workspace_id(row.user_id),
        auth_method="api_key",
        api_key_id=row.id,
        user=user,
        rate_limit_per_minute=rate_limit,
    )


async def _resolve_jwt(request: Request, token: str, db: Session) -> GatewayIdentity:
    """Resolve identity from a JWT via the standard auth dependency."""
    from core.auth import get_current_user

    user = await get_current_user(request, token, db)
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    return GatewayIdentity(
        user_id=user.id,
        tenant_id=resolve_tenant_id(user.id),
        workspace_id=resolve_workspace_id(user.id),
        auth_method="jwt",
        user=user,
    )


async def get_gateway_identity(
    request: Request, db: Session = Depends(get_db)
) -> GatewayIdentity:
    """Resolve the gateway identity for a request (dependency).

    Secret order: ``x-api-key`` -> ``Authorization: Bearer atom_sk_*`` -> JWT.
    Raises 401 when no valid identity can be established.
    """
    secret = _extract_secret(request)
    if secret:
        if secret.startswith("atom_sk_"):
            return await _resolve_api_key(secret, db, request)
        # JWT-shaped bearer token (3 dot-separated segments) -> standard auth.
        if secret.count(".") == 2:
            return await _resolve_jwt(request, secret, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "Invalid API key"}},
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "Missing API key"}},
    )
