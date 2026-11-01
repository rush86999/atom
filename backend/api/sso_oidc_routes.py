"""
OIDC Single Sign-On routes for the Atom platform.

Verification approach:
    The authorization-code flow requests the standard ``openid email
    profile`` scope and a fresh ``nonce``. The token response's ID token is
    verified locally before any session is issued: the algorithm is pinned
    to an asymmetric JOSE algorithm announced by the provider (``RS256`` /
    ``ES256`` / ``PS256``...), the signature is checked against the
    provider's JWKS, and issuer, audience and nonce are validated. Identity
    claims come from the verified ID token (userinfo, when configured, is a
    supplementary server-to-server read; it can never override ``sub`` or
    the verified claims). This is what makes an invalid issuer, a forged
    signature or a replayed/mismatched nonce fail closed instead of
    becoming a session.

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

# Provider JWKS cache: jwks_uri -> (fetched_at, jwks_dict). Signing keys
# rotate; the TTL bounds staleness while avoiding a JWKS fetch per callback.
_JWKS_CACHE_TTL = 300
_jwks_cache: Dict[str, tuple] = {}

# Single-use, expiring OAuth2 state store (see module docstring limitation).
# Keys are SHA-256 digests of the state token; validation scans entries with
# hmac.compare_digest so the comparison itself is constant time (the dict is
# only used for pruning, not lookup). The value carries the nonce that the
# token endpoint's ID token must echo.
_STATE_TTL = 600
_pending_states: Dict[str, tuple] = {}

_SUPPORTED_ID_TOKEN_ALGS = frozenset({
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
})


def _store_state(state: str, nonce: str) -> None:
    _prune_states()
    _pending_states[hashlib.sha256(state.encode()).hexdigest()] = (
        time.time() + _STATE_TTL,
        nonce,
    )


def _consume_state(state: str) -> Optional[str]:
    """Single-use, expiring, constant-time state validation.

    Returns the nonce bound to the state, or ``None`` when the state is
    missing, unknown, expired or already consumed.
    """
    if not state:
        return None
    digest = hashlib.sha256(state.encode()).hexdigest()
    now = time.time()
    for key in list(_pending_states.keys()):
        if hmac.compare_digest(digest, key):
            expires_at, nonce = _pending_states.pop(key)
            return nonce if expires_at >= now else None
    return None


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
    """Fetch (with cache) {issuer}/.well-known/openid-configuration.

    The discovery document's own ``issuer`` must equal the configured issuer
    (OIDC Discovery §4.3). A provider that answers with another issuer is not
    admissible: following its endpoints would let a compromised/misconfigured
    discovery URL redirect the callback and token exchange elsewhere.
    """
    now = time.time()
    cached = _discovery_cache.get(issuer_url)
    if cached and now - cached[0] < _DISCOVERY_CACHE_TTL:
        return cached[1]

    url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        metadata = resp.json()

    announced_issuer = str(metadata.get("issuer") or "").strip()
    if announced_issuer and announced_issuer.rstrip("/") != issuer_url.rstrip("/"):
        raise ValueError(
            "OIDC discovery issuer mismatch: "
            f"configured {issuer_url!r}, provider announced {announced_issuer!r}"
        )

    for key in ("authorization_endpoint", "token_endpoint",
                "userinfo_endpoint", "jwks_uri"):
        if not metadata.get(key):
            raise ValueError(f"OIDC discovery document missing '{key}'")
    algorithms = metadata.get("id_token_signing_alg_values_supported")
    if not algorithms:
        raise ValueError(
            "OIDC discovery document does not announce ID-token signing algorithms"
        )
    _discovery_cache[issuer_url] = (now, metadata)
    return metadata


async def _get_jwks(jwks_uri: str) -> Dict[str, Any]:
    """Fetch (with cache) the provider's JSON Web Key Set.

    Only public keys are requested. Signature verification always happens
    locally; the provider never sends a pre-verified assertion.
    """
    now = time.time()
    cached = _jwks_cache.get(jwks_uri)
    if cached and now - cached[0] < _JWKS_CACHE_TTL:
        return cached[1]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_uri)
        resp.raise_for_status()
        jwks = resp.json()
    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise ValueError("OIDC JWKS document has no 'keys' array")
    _jwks_cache[jwks_uri] = (now, jwks)
    return jwks


def _select_jwk(jwks: Dict[str, Any], kid: Optional[str],
                algorithm: str) -> Dict[str, Any]:
    keys = [k for k in (jwks.get("keys") or []) if isinstance(k, dict)]
    if kid:
        keys = [k for k in keys if str(k.get("kid") or "") == str(kid)]
    elif len(keys) > 1:
        raise ValueError("OIDC ID token has no 'kid' and the JWKS has multiple keys")
    # Never fall back to a symmetric key or an unrelated algorithm.
    keys = [k for k in keys if str(k.get("kty") or "").upper() in {"RSA", "EC"}]
    if not keys:
        raise ValueError("OIDC JWKS contains no usable signing key for this token")
    if len(keys) > 1:
        raise ValueError("OIDC JWKS has multiple candidate keys for this token")
    return keys[0]


def _verify_id_token(id_token: str, cfg: Dict[str, Any],
                     metadata: Dict[str, Any], jwks: Dict[str, Any],
                     expected_nonce: str) -> Dict[str, Any]:
    """Verify an OIDC ID token and return its claims, or raise ValueError.

    Pinned checks: asymmetric algorithm, signature against JWKS, issuer,
    audience, expiry/not-before, and the nonce bound to the login state.
    """
    from jose import jwt as jose_jwt
    from jose.exceptions import JOSEError

    if not id_token:
        raise ValueError("token endpoint response missing id_token")

    try:
        header = jose_jwt.get_unverified_header(id_token)
    except JOSEError as exc:
        raise ValueError(f"ID token header is not a JWS: {exc}") from exc
    algorithm = str(header.get("alg") or "")
    if algorithm not in _SUPPORTED_ID_TOKEN_ALGS:
        raise ValueError(f"ID token algorithm {algorithm!r} is not accepted")

    announced = {
        str(a) for a in
        (metadata.get("id_token_signing_alg_values_supported") or [])
    }
    if announced and algorithm not in announced:
        raise ValueError(
            f"ID token algorithm {algorithm!r} was not announced by the provider"
        )

    key = _select_jwk(jwks, header.get("kid"), algorithm)
    issuer = str(metadata.get("issuer") or cfg.get("issuer_url") or "").rstrip("/")
    try:
        claims = jose_jwt.decode(
            id_token,
            key,
            algorithms=[algorithm],
            audience=cfg["client_id"],
            issuer=issuer,
            options={"verify_at_hash": False},
        )
    except JOSEError as exc:
        raise ValueError(f"ID token verification failed: {exc}") from exc

    token_nonce = str(claims.get("nonce") or "")
    if not expected_nonce or not token_nonce or not hmac.compare_digest(
            token_nonce, expected_nonce):
        raise ValueError("ID token nonce does not match the login state")
    if not str(claims.get("sub") or "").strip():
        raise ValueError("ID token has no subject")
    return claims


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
    nonce = secrets.token_urlsafe(32)
    _store_state(state, nonce)

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": _redirect_uri(request),
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    from urllib.parse import urlencode
    authorize_url = metadata["authorization_endpoint"] + "?" + urlencode(params)
    return RedirectResponse(url=authorize_url, status_code=302)


def _prune_states() -> None:
    now = time.time()
    for s in [s for s, (exp, _nonce) in _pending_states.items() if exp < now]:
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
    # constant time to prevent both replay and timing oracles. The consumed
    # state also carries the nonce the provider must echo in the ID token.
    expected_nonce = _consume_state(state)
    if not expected_nonce:
        logger.warning("OIDC callback rejected: invalid, expired or replayed state")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        metadata = await _get_discovery_document(cfg["issuer_url"])
        jwks = await _get_jwks(metadata["jwks_uri"])
    except (httpx.HTTPError, ValueError) as e:
        logger.error("OIDC discovery/JWKS fetch failed (error=%s)", e)
        raise HTTPException(status_code=502, detail="Failed to contact SSO identity provider")

    try:
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
    except httpx.HTTPError as e:
        logger.error("OIDC token exchange failed (error=%s)", e)
        raise HTTPException(status_code=502, detail="Failed to complete SSO exchange")
    except ValueError as e:
        logger.error("OIDC token response is not JSON (error=%s)", e)
        raise HTTPException(status_code=502, detail="Failed to complete SSO exchange")

    # The ID token is verified BEFORE the access token is used. Its issuer,
    # signature, audience and nonce must all match; a token from another
    # issuer, a forged signature or a replayed nonce never reaches user
    # provisioning.
    try:
        claims = _verify_id_token(
            tokens.get("id_token"), cfg, metadata, jwks, expected_nonce)
    except ValueError as e:
        # Signature/issuer/audience/nonce/format failures are authentication
        # failures, not retryable upstream outages.
        logger.warning("OIDC ID token rejected: %s", e)
        raise HTTPException(status_code=401, detail="Invalid SSO identity token")

    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="SSO token response missing access_token")

    # Supplementary profile read. Identity/subject still come from the
    # verified ID token; userinfo cannot replace it.
    userinfo = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            ui_resp = await client.get(
                metadata["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui_resp.raise_for_status()
            userinfo = ui_resp.json()
    except httpx.HTTPError as exc:
        # A verified ID token already carries the identity. Some
        # standards-compliant providers do not expose a usable userinfo
        # endpoint for this client; that must not turn a valid login into
        # a 500. Log and continue with the verified claims.
        logger.warning("OIDC userinfo unavailable; using verified ID-token claims: %s", exc)
        userinfo = {}
    except ValueError:
        userinfo = {}

    email = str(
        claims.get("email") or userinfo.get("email") or ""
    ).strip().lower()
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
            first_name=str(
                claims.get("given_name") or userinfo.get("given_name")
                or claims.get("name") or userinfo.get("name") or "SSO"
            )[:255],
            last_name=str(
                claims.get("family_name") or userinfo.get("family_name")
                or "User"
            )[:255],
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
