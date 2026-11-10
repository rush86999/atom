"""
OIDC Single Sign-On routes for the Atom platform.

Verification approach:
    The authorization-code flow requests the standard ``openid email
    profile`` scope and a fresh ``nonce``. The token response's ID token is
    verified locally before any session is issued: the algorithm is pinned
    to an asymmetric JOSE algorithm announced by the provider (``RS256`` /
    ``ES256`` / ``PS256``...), the signature is checked against the
    provider's JWKS, and issuer, audience and nonce are validated. Identity
    claims come from the verified ID token. If that token omits the email,
    a UserInfo response may supply it only when its ``sub`` exactly equals
    the verified subject and that same response carries a boolean
    ``email_verified=true``; it can never override signed claims or
    contribute a foreign profile. This is what makes an invalid issuer, a
    forged signature or a replayed/mismatched nonce fail closed instead of
    becoming a session.

Token delivery to the frontend:
    The legacy ``/login`` + ``/callback`` pair is retained for direct
    backend API compatibility only: it returns a backend-origin HTML page
    that stores the backend JWT in localStorage and redirects to the
    backend root. That flow is explicitly not the same-origin browser web
    handoff and is not claimed as complete web/browser SSO.

    The ``/web/login`` + ``/web/callback`` + ``/web/exchange`` routes are
    the browser handoff: the OIDC callback returns only an opaque one-use
    browser-bound code to the configured ``APP_URL`` origin, and the
    exchange returns the ordinary backend bearer as JSON after current
    User/config/tenant authority is atomically claimed. The existing
    NextAuth SDK bridge (``establishWebSession`` +
    ``persistBackendToken``) then owns the web session and raw API token.

State management:
    The OAuth2 ``state`` parameter is a random 256-bit token. Only its
    SHA-256 digest is persisted, in the existing ``oauth_states`` table,
    together with a 10-minute expiry, the ID-token nonce, a digest of a
    separate HttpOnly SameSite=Lax browser-binding cookie, the current
    issuer/client/config generation, and the exact callback target. A
    conditional DELETE of that row is the single-use arbiter across
    processes; comparisons are constant-time and the state is consumed
    before any provider code exchange.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlencode, urlsplit

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    create_access_token,
    credential_session_binding,
    get_current_user,
)
from core.config import get_config
from core.database import get_db
from core.sql_json import json_field_equals
from core.models import (
    OAuthState,
    SSOConfiguration,
    Tenant,
    User,
    UserRole,
    UserStatus,
)
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

# Durable, single-use OAuth2 state lifetime. The URL state token is stored as
# a digest in the existing OAuthState table; the browser cookie carries a
# separate high-entropy binding token whose digest is kept in extra_data.
_STATE_TTL = 600
_STATE_COOKIE_DEVELOPMENT = "atom_oidc_state"
_STATE_COOKIE_SECURE = "__Host-atom_oidc_state"
_WEB_LOGIN_PURPOSE = "oidc_web_login"
_WEB_HANDOFF_PROVIDER = "oidc_web_handoff"
_WEB_HANDOFF_TTL = 120
_WEB_CALLBACK_PATH = "/api/auth/sso/oidc/web/callback"
_WEB_LANDING_PATH = "/auth/sso/callback"
_WEB_SOURCE_SECRET_PREFIX = b"atom-oidc-web-handoff-credential\0"

# Retired in-memory store. Kept only as an inert compatibility symbol for
# external test harnesses that clear it; the durable state path never reads or
# writes this dictionary.
_pending_states: Dict[str, tuple] = {}

_SUPPORTED_ID_TOKEN_ALGS = frozenset({
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
})


def _state_cookie_secure(request: Request) -> bool:
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    return environment == "production" or request.url.scheme == "https"


def _state_cookie_name(request: Request) -> str:
    return (
        _STATE_COOKIE_SECURE if _state_cookie_secure(request)
        else _STATE_COOKIE_DEVELOPMENT
    )


def _state_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _state_expired(row: OAuthState) -> bool:
    expires_at = getattr(row, "expires_at", None)
    if expires_at is None:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires_at


def _trusted_web_origin() -> Optional[str]:
    """Return the configured web origin, or None for any ambiguous value."""
    try:
        raw = get_config().server.app_url
    except Exception:  # noqa: BLE001 — missing configuration fails closed
        return None
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = urlsplit(raw.strip())
        port = parsed.port
    except ValueError:
        return None
    scheme = str(parsed.scheme or "").lower()
    host = str(parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if parsed.path not in ("", "/"):
        return None
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    default_port = (scheme == "https" and port == 443) or (
        scheme == "http" and port == 80)
    netloc = host if port is None or default_port else f"{host}:{port}"
    return f"{scheme}://{netloc}"


def _safe_return_to(value: Any) -> Optional[str]:
    """Validate a same-origin relative post-login target."""
    if not isinstance(value, str):
        return None
    if not value or len(value) > 2048 or value != value.strip():
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    if "\\" in value:
        return None
    if not value.startswith("/") or value.startswith("//"):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return None

    decoded = value
    for _ in range(3):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    else:
        return None
    if decoded != decoded.strip():
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in decoded):
        return None
    if "\\" in decoded:
        return None
    if not decoded.startswith("/") or decoded.startswith("//"):
        return None
    decoded_parsed = urlsplit(decoded)
    if decoded_parsed.scheme or decoded_parsed.netloc:
        return None
    path = str(decoded_parsed.path or "")
    if any(segment in {".", ".."} for segment in path.split("/")):
        return None
    lower_path = path.lower()
    for blocked in ("/api/auth", "/auth", "/login"):
        if lower_path == blocked or lower_path.startswith(blocked + "/"):
            return None
    return value


def _pkce_pair(metadata: Dict[str, Any]) -> tuple:
    """Return an S256 verifier/challenge, refusing advertised downgrade."""
    methods = metadata.get("code_challenge_methods_supported")
    if methods is not None:
        if not isinstance(methods, (list, tuple)) or "S256" not in {
                str(method) for method in methods}:
            raise ValueError("OIDC provider does not announce PKCE S256")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _credential_commitment(user: User) -> str:
    """Keyed, non-revealing commitment to the exact current credential."""
    binding = credential_session_binding(user)
    return hmac.new(
        str(SECRET_KEY or "").encode("utf-8"),
        _WEB_SOURCE_SECRET_PREFIX + binding.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _user_snapshot_digest(user: User) -> str:
    material = {
        "id": str(user.id or ""),
        "email": str(user.email or ""),
        "status": str(user.status or ""),
        "is_active": user.is_active is True,
        "role": str(user.role or ""),
        "tenant_id": user.tenant_id,
        "workspace_id": user.workspace_id,
    }
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
    ).hexdigest()


def _user_claim_predicate(user: User):
    """Correlated exact current User row for an atomic handoff exchange."""
    return exists(
        select(User.id).where(
            User.id == str(user.id),
            User.email == str(user.email or ""),
            User.status == str(user.status or ""),
            User.is_active.is_(True),
            User.role == str(user.role or ""),
            _exact(User.tenant_id, user.tenant_id),
            _exact(User.workspace_id, user.workspace_id),
            _exact(User.hashed_password, user.hashed_password),
        )
    )


def _config_row(db: Session) -> Optional[SSOConfiguration]:
    return (
        db.query(SSOConfiguration)
        .filter(SSOConfiguration.provider == _OIDC_PROVIDER)
        .first()
    )


def _authoritative_tenant_id(db: Session) -> Optional[str]:
    """Resolve the configured/default tenant without creating one."""
    try:
        row = _config_row(db)
        tenant_id = (
            str(row.tenant_id) if row is not None and row.tenant_id
            else PERSONAL_TENANT_ID
        )
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == tenant_id)
            .populate_existing()
            .first()
        )
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        logger.error(
            "OIDC tenant resolution failed (error_class=%s)",
            type(exc).__name__)
        return None
    if tenant is None or getattr(tenant, "is_active", None) is not True:
        return None
    return tenant_id


def _client_secret_commitment(secret: Any) -> str:
    """Keyed, non-revealing commitment to the effective client secret."""
    material = (
        b"atom-oidc-effective-client-secret\0"
        + str(secret or "").encode("utf-8")
    )
    return hmac.new(
        str(SECRET_KEY or "").encode("utf-8"),
        material,
        hashlib.sha256,
    ).hexdigest()


def _config_authority(
    db: Session, cfg: Dict[str, Any], redirect_target: str
) -> Optional[Dict[str, Any]]:
    """Freeze every config field the callback is allowed to trust."""
    try:
        row = _config_row(db)
    except Exception as exc:  # noqa: BLE001 — unreadable generation fails closed
        logger.error(
            "OIDC config generation read failed (error_class=%s)",
            type(exc).__name__)
        return None
    material = {
        "issuer_url": str(cfg.get("issuer_url") or "").rstrip("/"),
        "client_id": str(cfg.get("client_id") or ""),
        "default_role": str(cfg.get("default_role") or ""),
        "allowed_domains": list(cfg.get("allowed_domains") or []),
        "enabled": bool(cfg.get("enabled")),
        "redirect_uri": str(redirect_target or ""),
        "client_secret_commitment": _client_secret_commitment(
            cfg.get("client_secret")),
    }
    encrypted_secret = None
    generation_value = None
    if row is not None:
        generation_value = row.updated_at or row.created_at
        material["generation"] = str(
            generation_value or row.id)
        material["tenant_id"] = str(row.tenant_id or "")
        material["config_row_id"] = str(row.id or "")
        config_payload = row.config if isinstance(row.config, dict) else {}
        encrypted_secret = config_payload.get("client_secret_encrypted")
        if not isinstance(encrypted_secret, str):
            encrypted_secret = None
    return {
        "digest": hashlib.sha256(
            json.dumps(
                material, sort_keys=True, separators=(",", ":"), default=str,
            ).encode("utf-8")
        ).hexdigest(),
        "row": row,
        "material": material,
        "generation_value": generation_value,
        "encrypted_secret": encrypted_secret,
    }


def _config_fingerprint(
    db: Session, cfg: Dict[str, Any], redirect_target: str
) -> Optional[str]:
    """Freeze the current SSO config generation and exact callback target."""
    authority = _config_authority(db, cfg, redirect_target)
    return authority["digest"] if authority is not None else None


def _exact(column: Any, value: Any):
    return column.is_(None) if value is None else column == value


def _config_claim_predicate(
    db: Session, authority: Dict[str, Any], state_tenant_id: Any
):
    """Correlated current-config predicate for the atomic state claim."""
    row = authority["row"]
    material = authority["material"]
    if row is None:
        # Environment-only config: a database row appearing before the claim
        # means the effective authority source changed.
        return ~exists(
            select(SSOConfiguration.id).where(
                SSOConfiguration.provider == _OIDC_PROVIDER,
            )
        )

    predicates = [
        SSOConfiguration.id == str(row.id),
        SSOConfiguration.provider == _OIDC_PROVIDER,
        SSOConfiguration.tenant_id == str(state_tenant_id),
        SSOConfiguration.enabled.is_(True),
        json_field_equals(
            db, SSOConfiguration.config, "$.issuer_url",
            material["issuer_url"]),
        json_field_equals(
            db, SSOConfiguration.config, "$.client_id",
            material["client_id"]),
        json_field_equals(
            db, SSOConfiguration.config, "$.default_role",
            material["default_role"]),
        json_field_equals(
            db, SSOConfiguration.config, "$.allowed_domains",
            json.dumps(
                material["allowed_domains"],
                separators=(",", ":"),
                default=str,
            )),
    ]
    generation_value = authority.get("generation_value")
    if generation_value is not None:
        predicates.append(SSOConfiguration.updated_at == generation_value)
    encrypted_secret = authority.get("encrypted_secret")
    if isinstance(encrypted_secret, str):
        predicates.append(json_field_equals(
            db, SSOConfiguration.config, "$.client_secret_encrypted",
            encrypted_secret))
    return exists(select(SSOConfiguration.id).where(*predicates))


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
    subject = claims.get("sub") if isinstance(claims, dict) else None
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("ID token has no string subject")
    return claims


def _trusted_text(value: Any) -> Optional[str]:
    """Return a non-empty string claim value without coercing other types."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _resolve_verified_identity(
    claims: Dict[str, Any], userinfo: Dict[str, Any]
) -> Optional[Dict[str, str]]:
    """Resolve identity only from verified, subject-bound OIDC claims.

    Signed ID-token claims are the primary source. A signed email is usable
    only when the issuer marks it with a real boolean ``email_verified=true``.
    If the signed token omits email, a UserInfo profile may supply it only when
    that profile's ``sub`` exactly equals the verified ID-token subject and the
    same profile carries a boolean ``email_verified=true``. A signed explicit
    non-true marker is never replaced by a positive profile marker.

    Names follow the same subject binding: signed claims win; a profile may
    fill gaps only when its subject is exactly the signed subject. A foreign
    or subject-less profile contributes no identity or profile fields.
    """
    if not isinstance(claims, dict):
        return None
    subject = claims.get("sub")
    # ``sub`` is an opaque identifier. Validate that it is a non-blank string,
    # then keep every codepoint exactly as issued: no trim, casefold or other
    # normalization before exact UserInfo subject comparison.
    if not isinstance(subject, str) or not subject.strip():
        return None

    trusted_profile: Dict[str, Any] = {}
    if isinstance(userinfo, dict):
        profile_subject = userinfo.get("sub")
        if isinstance(profile_subject, str) and profile_subject == subject:
            trusted_profile = userinfo

    if "email" in claims:
        signed_email = _trusted_text(claims.get("email"))
        if signed_email is None or claims.get("email_verified") is not True:
            return None
        email = signed_email
    else:
        # A signed non-true marker is an explicit statement that the issuer did
        # not verify this identity's email. The supplementary profile cannot
        # lend it a positive marker.
        if ("email_verified" in claims
                and claims.get("email_verified") is not True):
            return None
        profile_email = _trusted_text(trusted_profile.get("email"))
        if (profile_email is None
                or trusted_profile.get("email_verified") is not True):
            return None
        email = profile_email

    def profile_text(key: str) -> Optional[str]:
        return _trusted_text(trusted_profile.get(key))

    first_name = (
        _trusted_text(claims.get("given_name"))
        or profile_text("given_name")
        or _trusted_text(claims.get("name"))
        or profile_text("name")
        or "SSO"
    )
    last_name = (
        _trusted_text(claims.get("family_name"))
        or profile_text("family_name")
        or "User"
    )
    return {
        "sub": subject,
        "email": email.lower(),
        "first_name": first_name,
        "last_name": last_name,
    }


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
        raise HTTPException(
            status_code=409,
            detail="SSO is not configured. An administrator must configure OIDC SSO first.",
        )
    if not cfg.get("enabled"):
        raise HTTPException(status_code=503, detail="SSO is disabled")

    tenant_id = _authoritative_tenant_id(db)
    if not tenant_id:
        logger.error("OIDC login refused: authoritative tenant unavailable")
        raise HTTPException(status_code=503, detail="SSO is unavailable")

    try:
        metadata = await _get_discovery_document(cfg["issuer_url"])
    except Exception as e:
        logger.error("OIDC discovery failed for issuer (issuer=%r, error=%s)", cfg["issuer_url"], e)
        raise HTTPException(status_code=502, detail="Failed to contact SSO identity provider")

    redirect_target = _redirect_uri(request)
    config_digest = _config_fingerprint(db, cfg, redirect_target)
    if not config_digest:
        raise HTTPException(status_code=503, detail="SSO is unavailable")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    browser_binding = secrets.token_urlsafe(32)
    state_row = OAuthState(
        tenant_id=tenant_id,
        user_id=None,
        state=_state_digest(state),
        provider=_OIDC_PROVIDER,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL),
        redirect_uri=redirect_target,
        extra_data={
            "nonce": nonce,
            "browser_digest": _state_digest(browser_binding),
            "config_digest": config_digest,
        },
    )
    try:
        db.add(state_row)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — state must be durable before redirect
        db.rollback()
        logger.error(
            "OIDC state persistence failed "
            "(stage=login_commit, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be started",
        )

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_target,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    from urllib.parse import urlencode
    authorize_url = metadata["authorization_endpoint"] + "?" + urlencode(params)
    response = RedirectResponse(url=authorize_url, status_code=302)
    response.set_cookie(
        key=_state_cookie_name(request),
        value=browser_binding,
        max_age=_STATE_TTL,
        path="/",
        secure=_state_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    return response


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


def _existing_user_is_active(user: User) -> bool:
    """External SSO may sign in only an account that is currently usable."""
    status = getattr(user, "status", "")
    status = getattr(status, "value", status)
    return (
        str(status or "") == UserStatus.ACTIVE.value
        and getattr(user, "is_active", None) is True
    )


def _claim_existing_user_admission(
    db: Session, user: User
) -> Optional[User]:
    """CAS-claim an existing account and stamp ``last_login`` in one write.

    External SSO verifies the IdP identity; it does not own the local account
    lifecycle. The conditional UPDATE binds the exact row that admitted the
    request (identity, current email, active/status/role, raw tenant/workspace,
    and the credential material used by the session binding). A peer
    deactivation, scope move or credential change that commits first makes the
    claim match zero rows, so this request is refused before any token exists.

    The ORM object is never mutated for the claim: no dirty-flush path can
    overwrite the peer's committed authority, and ``synchronize_session=False``
    keeps the identity map from pretending the write happened.
    """
    from datetime import datetime, timezone

    from sqlalchemy import update

    if not _existing_user_is_active(user):
        return None

    snapshot = {
        name: getattr(user, name) for name in (
            "id", "email", "status", "is_active", "role",
            "tenant_id", "workspace_id", "hashed_password")
    }
    now = datetime.now(timezone.utc)
    with db.no_autoflush:
        claimed = db.execute(
            update(User)
            .where(
                User.id == snapshot["id"],
                User.email == snapshot["email"],
                User.status == snapshot["status"],
                User.is_active.is_(True),
                User.role == snapshot["role"],
                User.tenant_id == snapshot["tenant_id"],
                User.workspace_id == snapshot["workspace_id"],
                User.hashed_password == snapshot["hashed_password"],
            )
            .values(last_login=now)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            db.rollback()
            return None
        current = (
            db.query(User)
            .filter(User.id == snapshot["id"])
            .populate_existing()
            .first()
        )
    if current is None or not _existing_user_is_active(current):
        db.rollback()
        return None
    return current


def _consume_callback_state(
    db: Session,
    request: Request,
    state: Optional[str],
    cfg: Dict[str, Any],
    redirect_target: str,
    *,
    purpose: Optional[str] = None,
    required_metadata: tuple = (),
) -> Dict[str, Any]:
    """Validate and atomically consume the durable browser-bound state.

    The conditional DELETE is the single-use arbiter across processes and
    connections. Every identity/binding check and its constant-time comparison
    happens before that delete and before any provider exchange.
    """
    if not state:
        logger.warning("OIDC state rejected stage=missing")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")

    digest = _state_digest(state)
    try:
        row = (
            db.query(OAuthState)
            .filter(
                OAuthState.state == digest,
                OAuthState.provider == _OIDC_PROVIDER,
            )
            .populate_existing()
            .first()
        )
    except Exception as exc:  # noqa: BLE001 — unreadable state fails closed
        db.rollback()
        logger.error(
            "OIDC state lookup failed "
            "(stage=lookup, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )

    if row is None:
        logger.warning("OIDC state rejected stage=unknown")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")
    if not hmac.compare_digest(str(row.state or ""), digest):
        logger.warning("OIDC state rejected stage=digest")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")
    if _state_expired(row):
        logger.warning("OIDC state rejected stage=expired")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")

    cookie_value = request.cookies.get(_state_cookie_name(request))
    if not cookie_value:
        logger.warning("OIDC state rejected stage=browser_missing")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")
    extra_data = row.extra_data if isinstance(row.extra_data, dict) else {}
    if purpose is not None and extra_data.get("purpose") != purpose:
        logger.warning("OIDC state rejected stage=purpose")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")
    metadata_values: Dict[str, str] = {}
    for key in required_metadata:
        value = extra_data.get(key)
        if not isinstance(value, str) or not value:
            logger.warning("OIDC state rejected stage=metadata")
            raise HTTPException(
                status_code=401, detail="Invalid or expired SSO state")
        metadata_values[key] = value
    stored_browser = extra_data.get("browser_digest")
    if (
        not isinstance(stored_browser, str)
        or not hmac.compare_digest(
            stored_browser, _state_digest(cookie_value))
    ):
        logger.warning("OIDC state rejected stage=browser_mismatch")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")

    authority = _config_authority(db, cfg, redirect_target)
    if authority is None:
        logger.error("OIDC state rejected stage=config_unavailable")
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    stored_config = extra_data.get("config_digest")
    if (
        not isinstance(stored_config, str)
        or not hmac.compare_digest(stored_config, authority["digest"])
    ):
        logger.warning("OIDC state rejected stage=config_changed")
        raise HTTPException(
            status_code=409,
            detail="SSO configuration changed. Start sign-in again.",
        )

    if not hmac.compare_digest(
            str(row.redirect_uri or ""), str(redirect_target or "")):
        logger.warning("OIDC state rejected stage=redirect_changed")
        raise HTTPException(
            status_code=409,
            detail="SSO callback target changed. Start sign-in again.",
        )

    try:
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == str(row.tenant_id or ""))
            .populate_existing()
            .first()
        )
    except Exception as exc:  # noqa: BLE001 — unreadable tenant fails closed
        db.rollback()
        logger.error(
            "OIDC state tenant lookup failed "
            "(stage=tenant_lookup, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    if tenant is None or getattr(tenant, "is_active", None) is not True:
        logger.error("OIDC state rejected stage=tenant_missing")
        raise HTTPException(status_code=503, detail="SSO is unavailable")

    nonce = extra_data.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        logger.warning("OIDC state rejected stage=nonce_missing")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")

    accepted_tenant_id = row.tenant_id
    accepted_redirect_uri = row.redirect_uri
    now = datetime.now(timezone.utc)
    active_tenant = exists(
        select(Tenant.id).where(
            Tenant.id == OAuthState.tenant_id,
            Tenant.is_active.is_(True),
        )
    )
    current_config = _config_claim_predicate(
        db, authority, accepted_tenant_id)
    state_snapshot = [
        OAuthState.id == row.id,
        OAuthState.state == digest,
        OAuthState.provider == _OIDC_PROVIDER,
        _exact(OAuthState.tenant_id, row.tenant_id),
        _exact(OAuthState.user_id, row.user_id),
        _exact(OAuthState.redirect_uri, row.redirect_uri),
        OAuthState.expires_at == row.expires_at,
        OAuthState.expires_at > now,
        json_field_equals(
            db, OAuthState.extra_data, "$.nonce", nonce),
        json_field_equals(
            db, OAuthState.extra_data, "$.browser_digest", stored_browser),
        json_field_equals(
            db, OAuthState.extra_data, "$.config_digest", stored_config),
    ]
    for key, value in metadata_values.items():
        state_snapshot.append(json_field_equals(
            db, OAuthState.extra_data, f"$.{key}", value))
    try:
        claimed = db.execute(
            delete(OAuthState)
            .where(*state_snapshot, active_tenant, current_config)
            .execution_options(synchronize_session=False)
        )
    except Exception as exc:  # noqa: BLE001 — unconfirmed delete fails closed
        db.rollback()
        logger.error(
            "OIDC state consume failed "
            "(stage=delete, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    if claimed.rowcount != 1:
        db.rollback()
        logger.warning("OIDC state rejected stage=replayed")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO state")
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001 — uncertain commit fails closed
        db.rollback()
        logger.error(
            "OIDC state consume commit failed "
            "(stage=commit, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    return {
        "nonce": nonce,
        "tenant_id": accepted_tenant_id,
        "redirect_uri": accepted_redirect_uri,
        "browser_digest": stored_browser,
        "config_digest": stored_config,
        "extra_data": extra_data,
    }


def _admit_oidc_user(
    db: Session,
    claims: Dict[str, Any],
    userinfo: Dict[str, Any],
    cfg: Dict[str, Any],
) -> User:
    """Resolve or JIT-provision the canonical User without issuing a JWT."""
    identity = _resolve_verified_identity(claims, userinfo)
    if identity is None:
        logger.warning(
            "OIDC callback rejected: no verified, subject-bound email identity")
        raise HTTPException(
            status_code=401,
            detail="SSO identity does not include a verified email address",
        )
    email = identity["email"]

    allowed = cfg.get("allowed_domains") or []
    if allowed:
        domain = email.rsplit("@", 1)[-1]
        if domain not in [d.strip().lower() for d in allowed if d.strip()]:
            logger.warning(
                "OIDC login rejected: email domain not allowed (domain=%r)",
                domain)
            raise HTTPException(
                status_code=403,
                detail="Email domain is not permitted for SSO login",
            )

    from sqlalchemy import func
    user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .populate_existing()
        .first()
    )
    if user:
        if not _existing_user_is_active(user):
            logger.warning(
                "OIDC callback refused: existing account is not active "
                "(user_id=%s)", user.id)
            raise HTTPException(
                status_code=403,
                detail="Account is not active for SSO sign-in",
            )
        try:
            user = _claim_existing_user_admission(db, user)
        except Exception as exc:  # noqa: BLE001 — DB errors fail closed
            db.rollback()
            logger.error(
                "OIDC existing-account admission failed (error_class=%s)",
                type(exc).__name__)
            raise HTTPException(
                status_code=503,
                detail="SSO sign-in could not be completed",
            )
        if user is None:
            raise HTTPException(
                status_code=409,
                detail="SSO account authorization changed. Sign in again.",
            )
        return user

    user = User(
        email=email,
        hashed_password=None,  # SSO-provisioned users have no local password
        first_name=identity["first_name"][:255],
        last_name=identity["last_name"][:255],
        role=cfg.get("default_role") or UserRole.MEMBER.value,
        status=UserStatus.ACTIVE.value,
        is_active=True,
        tenant_id=PERSONAL_TENANT_ID,
        last_login=datetime.now(timezone.utc),
    )
    db.add(user)
    logger.info(
        "OIDC auto-provisioned user (email=%r, role=%s)", email, user.role)
    try:
        db.flush()
    except Exception as exc:  # noqa: BLE001 — DB errors fail closed
        db.rollback()
        logger.error(
            "OIDC auto-provisioning failed (error_class=%s)",
            type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    return user


@router.get("/callback")
async def oidc_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Validate state, exchange code, fetch userinfo, issue session JWT."""
    if error:
        raise HTTPException(status_code=400, detail=f"SSO provider returned error: {error}")

    cfg = _resolve_config(db)
    if not cfg or not cfg.get("enabled"):
        raise HTTPException(status_code=503, detail="SSO is disabled or not configured")

    # SECURITY: the durable state row is validated against the initiating
    # browser cookie, current config generation and exact callback target, then
    # atomically consumed before any upstream code exchange.
    redirect_target = _redirect_uri(request)
    claimed_state = _consume_callback_state(
        db, request, state, cfg, redirect_target)
    expected_nonce = claimed_state["nonce"]

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
                    "redirect_uri": redirect_target,
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

    user = _admit_oidc_user(db, claims, userinfo, cfg)

    # Same JWT session helper the normal login endpoint uses
    # (core/auth_endpoints.py login_for_access_token). The admission and JIT
    # insert are still uncommitted; this single commit either admits both the
    # user change and the session or rolls all of it back.
    from datetime import timedelta
    try:
        access_jwt = create_access_token(
            data={"sub": user.id},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            user=user,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — uncertain commit fails closed
        db.rollback()
        logger.error(
            "OIDC session commit failed (error_class=%s)",
            type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )

    import json as _json
    html = _CALLBACK_HTML.format(
        token_json=_json.dumps(access_jwt),
        redirect="/?sso=success",
    )
    response = HTMLResponse(content=html)
    response.delete_cookie(
        key=_state_cookie_name(request),
        path="/",
        secure=_state_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    return response


# ============================================================================
# Same-origin browser web handoff
# ============================================================================

_WEB_LOGIN_METADATA = (
    "purpose",
    "source_origin",
    "return_to",
    "web_callback_url",
    "pkce_verifier_encrypted",
    "pkce_method",
)

_WEB_HANDOFF_METADATA = (
    "purpose",
    "browser_digest",
    "config_digest",
    "source_origin",
    "return_to",
    "web_callback_url",
    "user_digest",
    "credential_commitment",
)


class WebExchangeRequest(BaseModel):
    code: str = Field(..., min_length=16, max_length=512)


def _web_error_redirect(web_origin: str, code: str) -> RedirectResponse:
    response = RedirectResponse(
        url=f"{web_origin}/login?{urlencode({'sso_error': code})}",
        status_code=302,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


async def _exchange_oidc_code(
    cfg: Dict[str, Any],
    metadata: Dict[str, Any],
    code: str,
    redirect_target: str,
    code_verifier: Optional[str] = None,
) -> Dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_target,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                metadata["token_endpoint"],
                data=data,
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
    except httpx.HTTPError:
        logger.error("OIDC token exchange failed (stage=web_exchange)")
        raise HTTPException(
            status_code=502,
            detail="Failed to complete SSO exchange",
        )
    except ValueError:
        logger.error("OIDC token response is not JSON (stage=web_exchange)")
        raise HTTPException(
            status_code=502,
            detail="Failed to complete SSO exchange",
        )
    if not isinstance(tokens, dict):
        raise HTTPException(
            status_code=502, detail="Failed to complete SSO exchange")
    return tokens


async def _fetch_oidc_userinfo(
    metadata: Dict[str, Any], access_token: str
) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            ui_resp = await client.get(
                metadata["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ui_resp.raise_for_status()
            userinfo = ui_resp.json()
    except httpx.HTTPError as exc:
        logger.warning(
            "OIDC userinfo unavailable; using verified ID-token claims: %s",
            exc)
        return {}
    except ValueError:
        return {}
    return userinfo if isinstance(userinfo, dict) else {}


@router.get("/web/login")
async def oidc_web_login(
    request: Request,
    return_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Start a same-origin browser OIDC flow with PKCE and a durable state."""
    web_origin = _trusted_web_origin()
    if not web_origin:
        raise HTTPException(status_code=503, detail="SSO web origin is unavailable")
    target = "/dashboard" if return_to is None else _safe_return_to(return_to)
    if target is None:
        raise HTTPException(status_code=400, detail="Invalid return target")

    cfg = _resolve_config(db)
    if not cfg:
        raise HTTPException(
            status_code=409,
            detail="SSO is not configured. An administrator must configure OIDC SSO first.",
        )
    if not cfg.get("enabled"):
        raise HTTPException(status_code=503, detail="SSO is disabled")
    tenant_id = _authoritative_tenant_id(db)
    if not tenant_id:
        logger.error("OIDC web login refused: authoritative tenant unavailable")
        raise HTTPException(status_code=503, detail="SSO is unavailable")

    try:
        metadata = await _get_discovery_document(cfg["issuer_url"])
    except Exception as e:
        logger.error(
            "OIDC discovery failed for issuer (issuer=%r, error=%s)",
            cfg["issuer_url"], e)
        raise HTTPException(
            status_code=502,
            detail="Failed to contact SSO identity provider",
        )
    try:
        verifier, challenge = _pkce_pair(metadata)
    except ValueError:
        logger.error("OIDC web login refused: PKCE S256 unavailable")
        raise HTTPException(
            status_code=503,
            detail="SSO provider does not support PKCE S256",
        )

    redirect_target = f"{web_origin}{_WEB_CALLBACK_PATH}"
    config_digest = _config_fingerprint(db, cfg, redirect_target)
    if not config_digest:
        raise HTTPException(status_code=503, detail="SSO is unavailable")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    browser_binding = secrets.token_urlsafe(32)
    state_row = OAuthState(
        tenant_id=tenant_id,
        user_id=None,
        state=_state_digest(state),
        provider=_OIDC_PROVIDER,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL),
        redirect_uri=redirect_target,
        extra_data={
            "purpose": _WEB_LOGIN_PURPOSE,
            "nonce": nonce,
            "browser_digest": _state_digest(browser_binding),
            "config_digest": config_digest,
            "source_origin": web_origin,
            "return_to": target,
            "web_callback_url": redirect_target,
            "pkce_verifier_encrypted": encrypt_token(verifier),
            "pkce_method": "S256",
        },
    )
    try:
        db.add(state_row)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — state must be durable before redirect
        db.rollback()
        logger.error(
            "OIDC web state persistence failed "
            "(stage=web_login_commit, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be started",
        )

    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_target,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = metadata["authorization_endpoint"] + "?" + urlencode(params)
    response = RedirectResponse(url=authorize_url, status_code=302)
    response.set_cookie(
        key=_state_cookie_name(request),
        value=browser_binding,
        max_age=_STATE_TTL,
        path="/",
        secure=_state_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/web/callback")
async def oidc_web_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Complete OIDC and redirect the browser with an opaque handoff code."""
    web_origin = _trusted_web_origin()
    if not web_origin:
        raise HTTPException(status_code=503, detail="SSO web origin is unavailable")
    if error:
        return _web_error_redirect(web_origin, "provider_error")

    cfg = _resolve_config(db)
    if not cfg or not cfg.get("enabled"):
        return _web_error_redirect(web_origin, "unavailable")

    redirect_target = f"{web_origin}{_WEB_CALLBACK_PATH}"
    try:
        claimed_state = _consume_callback_state(
            db,
            request,
            state,
            cfg,
            redirect_target,
            purpose=_WEB_LOGIN_PURPOSE,
            required_metadata=_WEB_LOGIN_METADATA,
        )
    except HTTPException as exc:
        if exc.status_code == 409:
            return _web_error_redirect(web_origin, "authority_changed")
        if exc.status_code == 401:
            return _web_error_redirect(web_origin, "invalid_state")
        return _web_error_redirect(web_origin, "unavailable")

    if not code:
        return _web_error_redirect(web_origin, "missing_code")

    if claimed_state["extra_data"].get("pkce_method") != "S256":
        db.rollback()
        return _web_error_redirect(web_origin, "invalid_state")
    try:
        verifier = decrypt_token(
            claimed_state["extra_data"].get("pkce_verifier_encrypted"))
    except Exception:  # noqa: BLE001 — unreadable verifier fails closed
        logger.warning("OIDC web PKCE verifier unavailable")
        return _web_error_redirect(web_origin, "invalid_state")
    try:
        metadata = await _get_discovery_document(cfg["issuer_url"])
        jwks = await _get_jwks(metadata["jwks_uri"])
        tokens = await _exchange_oidc_code(
            cfg, metadata, code, redirect_target, code_verifier=verifier)
    except HTTPException:
        return _web_error_redirect(web_origin, "unavailable")
    except (httpx.HTTPError, ValueError):
        logger.warning("OIDC web exchange preparation failed")
        return _web_error_redirect(web_origin, "unavailable")

    try:
        claims = _verify_id_token(
            tokens.get("id_token"),
            cfg,
            metadata,
            jwks,
            claimed_state["nonce"],
        )
    except ValueError:
        logger.warning("OIDC web ID token rejected")
        return _web_error_redirect(web_origin, "invalid_identity")

    access_token = tokens.get("access_token")
    if not access_token:
        return _web_error_redirect(web_origin, "unavailable")
    userinfo = await _fetch_oidc_userinfo(metadata, access_token)

    try:
        user = _admit_oidc_user(db, claims, userinfo, cfg)
    except HTTPException as exc:
        db.rollback()
        if exc.status_code in (401, 403):
            return _web_error_redirect(web_origin, "account_refused")
        if exc.status_code == 409:
            return _web_error_redirect(web_origin, "authority_changed")
        return _web_error_redirect(web_origin, "unavailable")

    authority = _config_authority(db, cfg, redirect_target)
    source_origin = claimed_state["extra_data"].get("source_origin")
    return_to = claimed_state["extra_data"].get("return_to")
    web_callback_url = claimed_state["extra_data"].get("web_callback_url")
    if (
        authority is None
        or not hmac.compare_digest(
            authority["digest"], claimed_state["config_digest"])
        or source_origin != web_origin
        or web_callback_url != redirect_target
        or _safe_return_to(return_to) != return_to
    ):
        db.rollback()
        logger.warning("OIDC web handoff rejected: authority changed")
        return _web_error_redirect(web_origin, "authority_changed")

    handoff_code = secrets.token_urlsafe(32)
    handoff_url = f"{web_origin}{_WEB_LANDING_PATH}"
    handoff_row = OAuthState(
        tenant_id=claimed_state["tenant_id"],
        user_id=user.id,
        state=_state_digest(handoff_code),
        provider=_WEB_HANDOFF_PROVIDER,
        expires_at=datetime.now(timezone.utc) + timedelta(
            seconds=_WEB_HANDOFF_TTL),
        redirect_uri=handoff_url,
        extra_data={
            "purpose": _WEB_HANDOFF_PROVIDER,
            "browser_digest": claimed_state["browser_digest"],
            "config_digest": claimed_state["config_digest"],
            "source_origin": web_origin,
            "return_to": return_to,
            "web_callback_url": handoff_url,
            "user_digest": _user_snapshot_digest(user),
            "credential_commitment": _credential_commitment(user),
        },
    )
    try:
        db.add(handoff_row)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — uncertain handoff fails closed
        db.rollback()
        logger.error(
            "OIDC web handoff persistence failed "
            "(stage=web_handoff_commit, error_class=%s)", type(exc).__name__)
        return _web_error_redirect(web_origin, "unavailable")

    response = RedirectResponse(
        url=f"{handoff_url}?{urlencode({'code': handoff_code})}",
        status_code=302,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.post("/web/exchange")
async def oidc_web_exchange(
    payload: WebExchangeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Exchange an opaque browser-bound handoff code for a backend bearer."""
    web_origin = _trusted_web_origin()
    if not web_origin:
        raise HTTPException(status_code=503, detail="SSO web origin is unavailable")
    if request.headers.get("origin") != web_origin:
        raise HTTPException(status_code=403, detail="Origin is not permitted")

    digest = _state_digest(payload.code)
    try:
        row = (
            db.query(OAuthState)
            .filter(
                OAuthState.state == digest,
                OAuthState.provider == _WEB_HANDOFF_PROVIDER,
            )
            .populate_existing()
            .first()
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(
            "OIDC web handoff lookup failed "
            "(stage=exchange_lookup, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")
    if not hmac.compare_digest(str(row.state or ""), digest):
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")
    if _state_expired(row):
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")

    cookie_value = request.cookies.get(_state_cookie_name(request))
    if not cookie_value:
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")
    extra_data = row.extra_data if isinstance(row.extra_data, dict) else {}
    handoff_metadata: Dict[str, str] = {}
    for key in _WEB_HANDOFF_METADATA:
        value = extra_data.get(key)
        if not isinstance(value, str) or not value:
            raise HTTPException(
                status_code=401, detail="Invalid or expired SSO handoff")
        handoff_metadata[key] = value
    if handoff_metadata["purpose"] != _WEB_HANDOFF_PROVIDER:
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")
    stored_browser = handoff_metadata["browser_digest"]
    if (
        not isinstance(stored_browser, str)
        or not hmac.compare_digest(
            stored_browser, _state_digest(cookie_value))
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")

    if handoff_metadata["source_origin"] != web_origin:
        raise HTTPException(status_code=409, detail="SSO authority changed")
    if handoff_metadata["web_callback_url"] != f"{web_origin}{_WEB_LANDING_PATH}":
        raise HTTPException(status_code=409, detail="SSO authority changed")
    if row.redirect_uri != f"{web_origin}{_WEB_LANDING_PATH}":
        raise HTTPException(status_code=409, detail="SSO authority changed")
    return_to = handoff_metadata["return_to"]
    if _safe_return_to(return_to) != return_to:
        raise HTTPException(status_code=409, detail="SSO authority changed")

    cfg = _resolve_config(db)
    if not cfg or not cfg.get("enabled"):
        raise HTTPException(status_code=503, detail="SSO is unavailable")
    authority = _config_authority(
        db, cfg, f"{web_origin}{_WEB_CALLBACK_PATH}")
    stored_config = handoff_metadata["config_digest"]
    if (
        authority is None
        or not isinstance(stored_config, str)
        or not hmac.compare_digest(stored_config, authority["digest"])
    ):
        raise HTTPException(status_code=409, detail="SSO authority changed")

    user = (
        db.query(User)
        .filter(User.id == str(row.user_id or ""))
        .populate_existing()
        .first()
    )
    if user is None or not _existing_user_is_active(user):
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")
    stored_user_digest = handoff_metadata["user_digest"]
    stored_credential = handoff_metadata["credential_commitment"]
    if (
        not hmac.compare_digest(
            stored_user_digest, _user_snapshot_digest(user))
        or not hmac.compare_digest(
            stored_credential, _credential_commitment(user))
    ):
        raise HTTPException(status_code=409, detail="SSO authority changed")

    now = datetime.now(timezone.utc)
    active_tenant = exists(
        select(Tenant.id).where(
            Tenant.id == OAuthState.tenant_id,
            Tenant.is_active.is_(True),
        )
    )
    current_config = _config_claim_predicate(
        db, authority, row.tenant_id)
    state_snapshot = [
        OAuthState.id == row.id,
        OAuthState.state == digest,
        OAuthState.provider == _WEB_HANDOFF_PROVIDER,
        _exact(OAuthState.tenant_id, row.tenant_id),
        _exact(OAuthState.user_id, row.user_id),
        _exact(OAuthState.redirect_uri, row.redirect_uri),
        OAuthState.expires_at == row.expires_at,
        OAuthState.expires_at > now,
    ]
    for key in _WEB_HANDOFF_METADATA:
        state_snapshot.append(json_field_equals(
            db, OAuthState.extra_data, f"$.{key}", handoff_metadata[key]))
    try:
        claimed = db.execute(
            delete(OAuthState)
            .where(
                *state_snapshot,
                active_tenant,
                current_config,
                _user_claim_predicate(user),
            )
            .execution_options(synchronize_session=False)
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.error(
            "OIDC web handoff claim failed "
            "(stage=exchange_delete, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=401, detail="Invalid or expired SSO handoff")

    email = user.email
    try:
        access_token = create_access_token(
            data={"sub": user.id},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            user=user,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — uncertain commit yields no token
        db.rollback()
        logger.error(
            "OIDC web handoff commit failed "
            "(stage=exchange_commit, error_class=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="SSO sign-in could not be completed",
        )

    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "email": email,
            "return_to": return_to,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.delete_cookie(
        key=_state_cookie_name(request),
        path="/",
        secure=_state_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    return response
