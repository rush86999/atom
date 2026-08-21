"""
OIDC Single Sign-On routes for the Atom platform.

Verification approach note (IMPORTANT):
    ID-token signature verification is NOT performed locally (no JWKS
    fetching / RS256 key validation). Instead, the module uses the
    authorization-code flow and then calls the IdP's ``userinfo`` endpoint
    with the access token obtained directly from the IdP's token endpoint
    over TLS. This is secure because the identity assertions never transit
    the browser: both the code->token exchange and the userinfo call are
    direct server-to-server HTTPS requests to the issuer. If local ID-token
    signature verification is needed later, add a JWKS client (e.g.
    python-jose's ``jwk`` module) — the required libs are already available.

Token delivery to the frontend:
    ``frontend-nextjs/lib/backendAuth.ts`` and ``lib/identity.ts`` read the
    session token from localStorage keys ``auth_token`` and ``token``
    (see backendAuth.ts lines ~62-63). The callback therefore returns a
    small HTML page that stores the JWT under both keys and then redirects
    to ``/?sso=success``.

State management:
    The OAuth2 ``state`` parameter is a random 256-bit token stored in a
    server-side dict with a 10-minute expiry, consumed on first use
    (single-use). Comparison uses ``hmac.compare_digest`` (constant time).
    LIMITATION: in-memory storage is single-process only; a multi-worker
    deployment needs shared storage (Redis) for state.
"""
import hashlib
import hmac
import logging
import secrets
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, get_current_user
from core.database import get_db
from core.models import SSOConfiguration, User, UserRole, UserStatus
from core.personal_scope import PERSONAL_TENANT_ID
from core.privsec.token_encryption import decrypt_token, encrypt_token
from core.security_dependencies import require_permission
from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/auth/sso/oidc", tags=["SSO OIDC"])

from core.rbac_service import Permission  # noqa: E402

# Provider identifier used for the global SSOConfiguration row.
_OIDC_PROVIDER = "oidc"

# OIDC discovery document cache: issuer_url -> (fetched_at, metadata).
# Refreshed at most every 5 minutes to avoid a discovery round-trip per login.
_DISCOVERY_CACHE_TTL = 300
_discovery_cache: Dict[str, tuple] = {}

# Single-use, expiring OAuth2 state store (see module docstring limitation).
# Keys are SHA-256 digests of the state token; validation scans entries with
# hmac.compare_digest so the comparison itself is constant time (the dict is
# only used for pruning, not lookup).
_STATE_TTL = 600
_pending_states: Dict[str, float] = {}


def _store_state(state: str) -> None:
    _prune_states()
    _pending_states[hashlib.sha256(state.encode()).hexdigest()] = time.time() + _STATE_TTL


def _consume_state(state: str) -> bool:
    """Single-use, expiring, constant-time state validation."""
    if not state:
        return False
    digest = hashlib.sha256(state.encode()).hexdigest()
    now = time.time()
    for key in list(_pending_states.keys()):
        if hmac.compare_digest(digest, key):
            expired = _pending_states.pop(key) < now
            return not expired
    return False


# ============================================================================
# Config resolution
# ============================================================================

class OIDCConfigUpdate(BaseModel):
    issuer_url: str = Field(..., min_length=8, max_length=500)
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: str = Field(..., min_length=1, max_length=512)
    enabled: bool = False
    default_role: str = Field(default=UserRole.MEMBER.value, max_length=50)
    allowed_domains: Optional[List[str]] = None


def _resolve_config(db: Session) -> Optional[Dict[str, Any]]:
    """Merge DB config (preferred) with ATOM_OIDC_* env fallback."""
    try:
        row = (
            db.query(SSOConfiguration)
            .filter(SSOConfiguration.provider == _OIDC_PROVIDER)
            .first()
        )
    except Exception as e:
        # Fresh deployments may not have run migrations yet — degrade to the
        # env fallback rather than 500-ing the login endpoint.
        logger.warning("SSO configuration table unavailable (error=%s)", e)
        row = None
    if row and row.config:
        cfg = dict(row.config)
        secret = cfg.pop("client_secret_encrypted", "")
        cfg["client_secret"] = decrypt_token(secret) if secret else ""
        cfg["enabled"] = bool(row.enabled)
        return cfg

    import os
    issuer = os.getenv("ATOM_OIDC_ISSUER")
    client_id = os.getenv("ATOM_OIDC_CLIENT_ID")
    client_secret = os.getenv("ATOM_OIDC_CLIENT_SECRET")
    enabled = os.getenv("ATOM_OIDC_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    if issuer and client_id and client_secret:
        return {
            "issuer_url": issuer,
            "client_id": client_id,
            "client_secret": client_secret,
            "enabled": enabled,
            "default_role": UserRole.MEMBER.value,
            "allowed_domains": None,
        }
    return None


def _sanitized(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    out.pop("client_secret", None)
    out["client_secret_configured"] = bool(cfg.get("client_secret"))
    return out


async def _get_discovery_document(issuer_url: str) -> Dict[str, Any]:
    """Fetch (with cache) {issuer}/.well-known/openid-configuration."""
    now = time.time()
    cached = _discovery_cache.get(issuer_url)
    if cached and now - cached[0] < _DISCOVERY_CACHE_TTL:
        return cached[1]

    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        metadata = resp.json()

    for key in ("authorization_endpoint", "token_endpoint", "userinfo_endpoint"):
        if not metadata.get(key):
            raise ValueError(f"OIDC discovery document missing '{key}'")
    _discovery_cache[issuer_url] = (now, metadata)
    return metadata


# ============================================================================
# Admin config endpoints
# ============================================================================

@router.put("/config")
async def upsert_oidc_config(
    payload: OIDCConfigUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
):
    """Upsert the global OIDC SSO configuration (admin only)."""
    # Validate default_role against the UserRole enum.
    try:
        UserRole(payload.default_role)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Unknown default_role: {payload.default_role}")

    row = (
        db.query(SSOConfiguration)
        .filter(SSOConfiguration.provider == _OIDC_PROVIDER)
        .first()
    )
    # SECURITY: client_secret is Fernet-encrypted at rest via the shared
    # privsec helper (BYOK_ENCRYPTION_KEY) and never returned by GET.
    stored_config = {
        "issuer_url": payload.issuer_url.rstrip("/"),
        "client_id": payload.client_id,
        "client_secret_encrypted": encrypt_token(payload.client_secret),
        "default_role": payload.default_role,
        "allowed_domains": payload.allowed_domains or [],
    }
    if row:
        row.config = stored_config
        row.enabled = payload.enabled
    else:
        row = SSOConfiguration(
            tenant_id=PERSONAL_TENANT_ID,
            provider=_OIDC_PROVIDER,
            config=stored_config,
            enabled=payload.enabled,
        )
        db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "success": True,
        "message": "OIDC SSO configuration saved",
        "config": _sanitized({
            "issuer_url": stored_config["issuer_url"],
            "client_id": stored_config["client_id"],
            "client_secret": payload.client_secret,
            "enabled": row.enabled,
            "default_role": stored_config["default_role"],
            "allowed_domains": stored_config["allowed_domains"],
        }),
    }


@router.get("/config")
async def get_oidc_config(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
):
    """Sanitized view of the OIDC SSO configuration (admin only)."""
    cfg = _resolve_config(db)
    if not cfg:
        return {"configured": False, "enabled": False, "source": None}
    try:
        source = "database" if db.query(SSOConfiguration).filter(
            SSOConfiguration.provider == _OIDC_PROVIDER
        ).first() else "environment"
    except Exception:
        source = "environment"
    return {"configured": True, "source": source, "config": _sanitized(cfg)}


# ============================================================================
# Login flow
# ============================================================================

def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/auth/sso/oidc/callback"


@router.get("/login")
async def oidc_login(request: Request, db: Session = Depends(get_db)):
    """302 redirect to the IdP authorization endpoint."""
    cfg = _resolve_config(db)
    if not cfg:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=409,
            detail="SSO is not configured. An administrator must configure OIDC SSO first.",
        )
    if not cfg.get("enabled"):
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="SSO is disabled")

    try:
        metadata = await _get_discovery_document(cfg["issuer_url"])
    except Exception as e:
        logger.error("OIDC discovery failed for issuer (issuer=%r, error=%s)", cfg["issuer_url"], e)
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="Failed to contact SSO identity provider")

    state = secrets.token_urlsafe(32)
    _store_state(state)

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": _redirect_uri(request),
        "scope": "openid email profile",
        "state": state,
    }
    from urllib.parse import urlencode
    authorize_url = metadata["authorization_endpoint"] + "?" + urlencode(params)
    return RedirectResponse(url=authorize_url, status_code=302)


def _prune_states() -> None:
    now = time.time()
    for s in [s for s, exp in _pending_states.items() if exp < now]:
        _pending_states.pop(s, None)


_CALLBACK_HTML = """<!DOCTYPE html>
<html><head><title>SSO Login</title></head>
<body>
<p>Signing you in…</p>
<script>
(function () {{
  var t = {token_json};
  try {{
    localStorage.setItem("auth_token", t);
    localStorage.setItem("token", t);
  }} catch (e) {{}}
  window.location.replace("{redirect}");
}})();
</script>
</body></html>
"""


@router.get("/callback")
async def oidc_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Validate state, exchange code, fetch userinfo, issue session JWT."""
    from fastapi import HTTPException

    if error:
        raise HTTPException(status_code=400, detail=f"SSO provider returned error: {error}")

    cfg = _resolve_config(db)
    if not cfg or not cfg.get("enabled"):
        raise HTTPException(status_code=503, detail="SSO is disabled or not configured")

    # SECURITY: state must be present, single-use, unexpired, compared in
    # constant time to prevent both replay and timing oracles.
    if not _consume_state(state):
        logger.warning("OIDC callback rejected: invalid, expired or replayed state")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        metadata = await _get_discovery_document(cfg["issuer_url"])

        # Code -> token exchange (direct TLS connection to the IdP).
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _redirect_uri(request),
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError("token endpoint response missing access_token")

        # Identity comes from the userinfo endpoint over TLS — see the module
        # docstring for why local ID-token signature verification is skipped.
        async with httpx.AsyncClient(timeout=10.0) as client:
            ui_resp = await client.get(
                metadata["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui_resp.raise_for_status()
            userinfo = ui_resp.json()
    except httpx.HTTPError as e:
        logger.error("OIDC token/userinfo exchange failed (error=%s)", e)
        raise HTTPException(status_code=502, detail="Failed to complete SSO exchange")

    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="SSO identity does not include an email address")

    allowed = cfg.get("allowed_domains") or []
    if allowed:
        domain = email.rsplit("@", 1)[-1]
        if domain not in [d.strip().lower() for d in allowed if d.strip()]:
            logger.warning("OIDC login rejected: email domain not allowed (domain=%r)", domain)
            raise HTTPException(status_code=403, detail="Email domain is not permitted for SSO login")

    from sqlalchemy import func
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user:
        # Ensure the account is usable via SSO.
        if user.status != UserStatus.ACTIVE.value:
            user.status = UserStatus.ACTIVE.value
        user.is_active = True
    else:
        # NOTE: the User model has no auth_provider column; nothing is stored
        # on the row to mark SSO provenance (adding a migration is out of scope).
        user = User(
            email=email,
            hashed_password=None,  # SSO-provisioned users have no local password
            first_name=(userinfo.get("given_name") or userinfo.get("name") or "SSO")[:255],
            last_name=(userinfo.get("family_name") or "User")[:255],
            role=cfg.get("default_role") or UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value,
            is_active=True,
            tenant_id=PERSONAL_TENANT_ID,
        )
        db.add(user)
        logger.info("OIDC auto-provisioned user (email=%r, role=%s)", email, user.role)

    from datetime import datetime, timezone
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Same JWT session helper the normal login endpoint uses
    # (core/auth_endpoints.py login_for_access_token).
    from datetime import timedelta
    access_jwt = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    import json as _json
    html = _CALLBACK_HTML.format(
        token_json=_json.dumps(access_jwt),
        redirect="/?sso=success",
    )
    return HTMLResponse(content=html)
