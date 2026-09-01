"""
OAuth Integration Routes

Provides unified OAuth callback endpoints for all third-party integrations.
Handles OAuth flows for Google, LinkedIn, Microsoft, Salesforce, Slack, GitHub, Asana, Notion, Trello, and Dropbox.
"""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import IntegrationToken, OAuthToken, User
from core.security.auth_rate_limit import AuthRateLimiter
from core.oauth_handler import (
    ASANA_OAUTH_CONFIG,
    BOX_OAUTH_CONFIG,
    DROPBOX_OAUTH_CONFIG,
    GITHUB_OAUTH_CONFIG,
    GOOGLE_OAUTH_CONFIG,
    LINKEDIN_OAUTH_CONFIG,
    MICROSOFT_OAUTH_CONFIG,
    NOTION_OAUTH_CONFIG,
    SALESFORCE_OAUTH_CONFIG,
    SLACK_OAUTH_CONFIG,
    TRELLO_OAUTH_CONFIG,
    WHATSAPP_OAUTH_CONFIG,
    ZOHO_OAUTH_CONFIG,
    OAuthHandler,
)

router = BaseAPIRouter(prefix="/api/v1/auth/oauth", tags=["OAuth"])
logger = logging.getLogger(__name__)

# Rate limit OAuth callbacks to prevent code brute-force / DoS
_oauth_limiter = AuthRateLimiter(limit=20, window_seconds=60)

# One grant fans out to several IntegrationToken provider rows at callback
# time (see _handle_callback_logic); revoke must fan out identically.
_TOKEN_FANOUT: Dict[str, list] = {
    "microsoft": ["microsoft", "outlook"],
    "zoho": [
        "zoho",
        "zoho_books",
        "zoho_inventory",
        "zoho_crm",
        "zoho_workdrive",
    ],
}


def _state_hmac_key() -> bytes:
    """HMAC key for signing OAuth state tokens — derived from the JWT secret.

    Deliberately reuses ``core.auth.SECRET_KEY`` so there is exactly ONE secret
    resolution policy in the app: raise in production if unset, random
    dev fallback. A standalone hardcoded fallback here would be a static secret
    any repo reader could use to forge state tokens (OAuth CSRF / token-binding).
    """
    from core.auth import SECRET_KEY as _auth_secret

    return hashlib.sha256(_auth_secret.encode()).digest()


def _build_state(provider: str, user_id: str) -> str:
    """Build a signed, unforgeable, per-user OAuth ``state`` token.

    Format: ``oauth_v1:{provider}:{user_id}:{nonce}:{exp}:{sig}``. The HMAC
    signature binds the state to the provider AND the initiating user, and the
    nonce makes each value unique. Replaces the old static, predictable state
    (``{provider}_oauth``) which let an attacker who completed their own flow
    forge the callback state and bind THEIR provider tokens to a victim's
    account (OAuth CSRF / token-binding attack).
    """
    payload = f"oauth_v1:{provider}:{user_id}"
    nonce = secrets.token_urlsafe(16)
    exp = str(int(time.time()) + 600)  # 10-minute validity
    sig = hmac.new(
        _state_hmac_key(), f"{payload}:{nonce}:{exp}".encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{nonce}:{exp}:{sig}"


def _validate_state(state: Optional[str], provider: str, user_id: Optional[str] = None) -> bool:
    """Validate a callback ``state``: signature, provider, user binding, expiry."""
    if not state:
        return False
    parts = state.split(":")
    if len(parts) != 6 or parts[0] != "oauth_v1":
        return False
    payload_provider, state_user, nonce, exp, sig = parts[1], parts[2], parts[3], parts[4], parts[5]
    if payload_provider != provider:
        return False
    if user_id and state_user != user_id:
        return False
    try:
        if int(exp) < int(time.time()):
            return False
    except ValueError:
        return False
    payload = f"oauth_v1:{payload_provider}:{state_user}"
    expected = hmac.new(
        _state_hmac_key(), f"{payload}:{nonce}:{exp}".encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


def _get_user_id_from_state(state: Optional[str], provider: str) -> Optional[str]:
    """Extract and verify user_id from valid state token."""
    if not state:
        return None
    parts = state.split(":")
    if len(parts) != 6 or parts[0] != "oauth_v1":
        return None
    payload_provider, state_user, nonce, exp, sig = parts[1], parts[2], parts[3], parts[4], parts[5]
    if payload_provider != provider:
        return None
    try:
        if int(exp) < int(time.time()):
            return None
    except ValueError:
        return None
    payload = f"oauth_v1:{payload_provider}:{state_user}"
    expected = hmac.new(
        _state_hmac_key(), f"{payload}:{nonce}:{exp}".encode(), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(sig, expected):
        return state_user
    return None


def oauth_rate_limit(request: Request) -> None:
    """Rate limit OAuth callback attempts (20/min per IP).

    NOTE: ``AuthRateLimiter.check`` takes the FastAPI ``Request`` (it extracts
    the TCP peer IP itself, honoring ``TRUST_X_FORWARDED_FOR``) — not an IP
    string. Passing a bare string crashes with AttributeError, turning every
    OAuth callback into a 500 and silently disabling the rate limit.
    """
    allowed, _remaining = _oauth_limiter.check(request)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many OAuth attempts. Try again later.")

# ============================================================================
# Helpers
# ============================================================================

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get current user from JWT Bearer token.

    SECURITY: Previously this function trusted a client-supplied ``X-User-ID``
    header with no verification, allowing any caller to impersonate any user
    by simply setting that header. This is a CVE-class authentication bypass.

    Now delegates to the unified ``core.auth.get_current_user`` which verifies
    a JWT (Bearer header or NextAuth cookie) and resolves the user from the DB.
    """
    from core.auth import get_current_user as _core_get_current_user

    # Extract the Bearer token from the Authorization header ourselves.
    # core.auth.oauth2_scheme only binds when FastAPI injects it as a
    # dependency; this wrapper is called directly (not as a FastAPI dep), so
    # passing token=None unconditionally meant the Authorization header was
    # never read and every Bearer call /api/v1/auth/oauth/* 401'd.
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    return await _core_get_current_user(request=request, token=token, db=db)

async def _handle_callback_logic(provider: str, code: str, config: Any, request: Request, db: Session, user: Optional[User] = None):
    """Common logic for handling OAuth callbacks."""
    try:
        oauth_handler = OAuthHandler(config)
        token_data = await oauth_handler.exchange_code_for_tokens(code)
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        token_type = token_data.get("token_type", "Bearer")
        scopes = token_data.get("scope", "").split(",") if isinstance(token_data.get("scope"), str) else []
        
        if not access_token:
            # The authorization code was already consumed (codes are single-use).
            # If an IntegrationToken already exists for this provider+user, the
            # first exchange succeeded — return success silently. With NO stored
            # token this is a real exchange failure (e.g. redirect_uri mismatch
            # on first connect); returning None makes the callback redirect to
            # the failure page instead of pretending the connect worked.
            try:
                # Local import: a later block in this function re-imports
                # IntegrationToken inside its own try, which would otherwise
                # make the name an unbound local here.
                from core.models import IntegrationToken as _IntegrationToken
                check_user = user or await get_current_user(request, db)
                provider_names = [provider]
                if provider == "microsoft":
                    provider_names.append("outlook")
                existing = db.query(_IntegrationToken).filter(
                    _IntegrationToken.user_id == check_user.id,
                    _IntegrationToken.provider.in_(provider_names),
                    _IntegrationToken.status == "active",
                ).first()
            except Exception as e:
                logger.warning(f"Could not check for existing {provider} IntegrationToken: {e}")
                existing = None
            if existing:
                logger.warning(f"No access_token in {provider} token response — existing active IntegrationToken found (code reuse); treating as success")
                return token_data
            logger.error(
                f"{provider} token exchange returned no access_token and no token "
                "is stored for this user — failing the connect"
            )
            return None

        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            
        import hashlib
        current_user = user
        if not current_user:
            current_user = await get_current_user(request, db)

        _access_hash = hashlib.sha256(access_token.encode()).hexdigest()
        _refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest() if refresh_token else None

        existing_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.client_id == f"{provider}_client"
        ).first()

        if existing_token:
            existing_token.access_token_hash = _access_hash
            if _refresh_hash:
                existing_token.refresh_token_hash = _refresh_hash
            existing_token.scope = " ".join(scopes) if scopes else ""
            existing_token.access_token_expires_at = expires_at
            existing_token.is_active = True
        else:
            new_token = OAuthToken(
                id=str(uuid.uuid4()),
                client_id=f"{provider}_client",
                tenant_id=current_user.tenant_id or "default",
                user_id=current_user.id,
                access_token_hash=_access_hash,
                refresh_token_hash=_refresh_hash,
                scope=" ".join(scopes) if scopes else "",
                access_token_expires_at=expires_at,
                is_active=True
            )
            db.add(new_token)

        # Also populate IntegrationToken for services like OutlookService
        try:
            from core.models import IntegrationToken
            from core.privsec.token_encryption import encrypt_token

            provider_keys = [provider]
            if provider == "microsoft":
                provider_keys.append("outlook")
            if provider == "zoho":
                # One Zoho app grant covers all four suite services; each
                # service resolves its own token row by exact provider name
                # (zoho_books/zoho_inventory/zoho_crm — workdrive falls back
                # to generic "zoho"), so fan the same credentials out to all.
                provider_keys += [
                    "zoho_books",
                    "zoho_inventory",
                    "zoho_crm",
                    "zoho_workdrive",
                ]

            # R88: credentials belong to the user who consented. Copying the
            # encrypted tokens into EVERY active user's IntegrationToken rows
            # turned any user's connect (or an attacker's token-binding flow)
            # into fleet-wide credential injection. Opt back in explicitly
            # for single-operator deployments via
            # ATOM_OAUTH_SHARED_INTEGRATION_TOKENS=true.
            _shared_tokens = os.getenv(
                "ATOM_OAUTH_SHARED_INTEGRATION_TOKENS", ""
            ).strip().lower() == "true"

            user_ids_to_sync = {current_user.id}
            if _shared_tokens:
                from core.models import UserStatus
                active_users = db.query(User).filter(
                    User.status == UserStatus.ACTIVE
                ).all()
                for u in active_users:
                    user_ids_to_sync.add(u.id)

            # Zoho token responses carry the datacenter API domain (e.g.
            # https://www.zohoapis.com / .in / .eu). Stored on the canonical
            # "zoho" row so the sync adapter (ZohoAdapter) targets the right
            # datacenter instead of env defaults.
            zoho_api_domain = token_data.get("api_domain")
            for target_uid in user_ids_to_sync:
                for p_key in provider_keys:
                    existing_integration = db.query(IntegrationToken).filter(
                        IntegrationToken.user_id == target_uid,
                        IntegrationToken.provider == p_key
                    ).first()

                    if existing_integration:
                        existing_integration.access_token = encrypt_token(access_token)
                        if refresh_token:
                            existing_integration.refresh_token = encrypt_token(refresh_token)
                        existing_integration.expires_at = expires_at
                        existing_integration.status = "active"
                        existing_integration.scope = " ".join(scopes) if scopes else ""
                        if p_key == "zoho" and zoho_api_domain:
                            existing_integration.instance_url = zoho_api_domain
                        if p_key == "zoho":
                            # Record the accounts DC that issued this grant so
                            # later refreshes hit the same DC (a .com refresh
                            # yields a token that 401s against .ca APIs).
                            try:
                                from urllib.parse import urlparse as _urlparse
                                _base = f"{_urlparse(config.auth_url).scheme}://{_urlparse(config.auth_url).netloc}"
                                meta = existing_integration.credential_metadata or {}
                                meta["accounts_base"] = _base
                                existing_integration.credential_metadata = meta
                            except Exception:
                                pass
                        logger.info(f"Updated IntegrationToken for provider={p_key}, user={target_uid}")
                    else:
                        # Guarded exactly like the update path above: urlparse
                        # on a non-string (mocked/absent auth_url) must not
                        # abort IntegrationToken creation entirely.
                        try:
                            _meta = {
                                "accounts_base": (
                                    f"{urlparse(config.auth_url).scheme}://{urlparse(config.auth_url).netloc}"
                                )
                            }
                        except Exception:
                            _meta = None
                        new_integration = IntegrationToken(
                            id=str(uuid.uuid4()),
                            tenant_id=current_user.tenant_id or "default",
                            user_id=target_uid,
                            workspace_id=getattr(current_user, "workspace_id", None) or "default",
                            provider=p_key,
                            access_token=encrypt_token(access_token),
                            refresh_token=encrypt_token(refresh_token) if refresh_token else None,
                            expires_at=expires_at,
                            status="active",
                            scope=" ".join(scopes) if scopes else "",
                            instance_url=zoho_api_domain if p_key == "zoho" else None,
                            credential_metadata=(_meta if p_key == "zoho" else None),
                        )
                        db.add(new_integration)
                        logger.info(f"Created IntegrationToken for provider={p_key}, user={target_uid}")
        except Exception as it_err:
            logger.error(f"Failed to populate IntegrationToken record: {it_err}", exc_info=True)

        db.commit()

        # Start the Outlook poller on connect (Personal Edition / NAT-friendly
        # complement to the Graph push webhook). Uses the module-level pipeline
        # singleton so the polling task survives this request.
        if provider == "microsoft":
            try:
                from integrations.atom_communication_ingestion_pipeline import (
                    ingestion_pipeline,
                )

                if ingestion_pipeline.start_outlook_poller():
                    logger.info("Outlook polling stream started after Microsoft OAuth connect")
                    try:
                        from integrations.outlook_realtime import outlook_realtime

                        outlook_realtime.start_renew_loop()
                        user_id_for_sub = str(target_uid or "default")
                        import asyncio as _asyncio

                        _asyncio.get_running_loop().create_task(
                            outlook_realtime.ensure_subscription(user_id_for_sub)
                        )
                    except Exception as rt_err:
                        logger.error(f"Failed to start Outlook realtime channel: {rt_err}")
            except Exception as poller_err:
                logger.error(f"Failed to start Outlook poller after OAuth connect: {poller_err}")

        # Start the hybrid ingestion sync on Zoho connect (Personal Edition /
        # pilot analog of the Outlook poller). Pulls Books invoices, Inventory
        # items + sales orders, CRM leads/deals, Projects tasks into LanceDB
        # (`integration_zoho`) + GraphRAG so the memory assembler's
        # integration-records leg can recall them. Background task — the
        # callback must not block on a full sync; never raises.
        if provider == "zoho":
            try:
                from core.hybrid_data_ingestion import get_hybrid_ingestion_service
                from core.personal_scope import resolve_tenant_id, resolve_workspace_id

                service = get_hybrid_ingestion_service(
                    # Keyword args: passing tenant_id positionally bound it to
                    # the service's workspace_id, so the sync adapter then
                    # looked its token up under a workspace no token row was
                    # stamped with and every post-connect sync ran
                    # unauthenticated.
                    workspace_id=resolve_workspace_id(current_user),
                    tenant_id=resolve_tenant_id(current_user),
                )
                asyncio.create_task(service.sync_integration_data("zoho"))
                logger.info("Zoho background sync scheduled after OAuth connect")
            except Exception as sync_err:
                logger.error(f"Failed to schedule Zoho sync after OAuth connect: {sync_err}")

        return token_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback failed for {provider}: {e}", exc_info=True)
        # R88: keep str(e) server-side — provider/client errors previously
        # flowed to the client in the detail field.
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete {provider} OAuth flow",
        )

# ============================================================================
# Generic OAuth Endpoints
# ============================================================================

@router.get("/{provider}/authorize")
@router.get("/{provider}/initiate")
async def oauth_initiate(
    provider: str,
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Initiate OAuth flow for a specific provider.

    Round 86: browser navigations cannot send an Authorization header, so the
    frontend passes ``?token=<JWT>``. get_current_user reads it from query
    params — but only resolves the user when given a db session, which this
    route previously never passed (silent demo-user fallback mis-bound the
    consent state and stored tokens under the wrong user).

    R88 (fail-closed identity): a valid JWT — Authorization header, NextAuth
    cookie, or ``?token=`` — is REQUIRED before any consent state is minted.
    The previous "demo-user" fallback plus a client-supplied ``?user_id=``
    override let an unauthenticated caller mint a validly-signed state bound
    to ANY user id; combined with the callback's unknown-user fallback that
    planted the attacker's provider tokens on the first DB row (bootstrap
    admin).
    """
    uid = None
    if request:
        try:
            from core.auth import get_current_user
            # Round 86: pass the query-param token explicitly. Called
            # manually, get_current_user's token default is the Depends
            # sentinel (truthy), so its own query/cookie fallback never ran
            # and every ?token= navigation silently degraded to demo-user.
            #
            # API clients and the journey suite authenticate with an
            # Authorization header instead — get_current_user reads that
            # header only through FastAPI dependency injection, never on a
            # manual call, so it must be extracted here too (same fix as the
            # module-level get_current_user wrapper above).
            browser_token = None
            auth_header = (
                request.headers.get("Authorization")
                or request.headers.get("authorization")
            )
            if auth_header and auth_header.lower().startswith("bearer "):
                browser_token = auth_header[7:].strip()
            if not browser_token:
                browser_token = request.query_params.get("token")
            u = await get_current_user(request=request, token=browser_token, db=db)
            if u and u.id:
                uid = u.id
        except HTTPException:
            raise
        except Exception:
            # Silent uid=None here turned every resolver crash (e.g. a
            # transient SQLite OperationalError under write bursts) into an
            # undocumented 401. Log it; the 401 to the client stays generic.
            logger.warning(
                "OAuth initiate user resolution failed for provider=%s",
                provider,
                exc_info=True,
            )
            uid = None
    if not uid:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to initiate an OAuth flow",
        )

    configs = {
        "google": GOOGLE_OAUTH_CONFIG,
        "linkedin": LINKEDIN_OAUTH_CONFIG,
        "microsoft": MICROSOFT_OAUTH_CONFIG,
        "salesforce": SALESFORCE_OAUTH_CONFIG,
        "slack": SLACK_OAUTH_CONFIG,
        "github": GITHUB_OAUTH_CONFIG,
        "asana": ASANA_OAUTH_CONFIG,
        "notion": NOTION_OAUTH_CONFIG,
        "trello": TRELLO_OAUTH_CONFIG,
        "dropbox": DROPBOX_OAUTH_CONFIG,
        "whatsapp": WHATSAPP_OAUTH_CONFIG,
        "zoho": ZOHO_OAUTH_CONFIG,
        "box": BOX_OAUTH_CONFIG,
    }

    if provider not in configs:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    handler = OAuthHandler(configs[provider])
    auth_url = handler.get_authorization_url(state=_build_state(provider, uid))
    # Round 80o: JSON variant for mobile clients — they cannot follow a 302
    # into the provider consent page; hand them the URL as data instead.
    from fastapi import Query
    if request is not None and "json" == request.query_params.get("format"):
        return {"url": auth_url}
    return RedirectResponse(url=auth_url)

@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
    _rl: None = Depends(oauth_rate_limit),
):
    """Handle OAuth callback for all providers."""
    configs = {
        "google": GOOGLE_OAUTH_CONFIG,
        "linkedin": LINKEDIN_OAUTH_CONFIG,
        "microsoft": MICROSOFT_OAUTH_CONFIG,
        "salesforce": SALESFORCE_OAUTH_CONFIG,
        "slack": SLACK_OAUTH_CONFIG,
        "github": GITHUB_OAUTH_CONFIG,
        "asana": ASANA_OAUTH_CONFIG,
        "notion": NOTION_OAUTH_CONFIG,
        "trello": TRELLO_OAUTH_CONFIG,
        "dropbox": DROPBOX_OAUTH_CONFIG,
        "whatsapp": WHATSAPP_OAUTH_CONFIG,
        "zoho": ZOHO_OAUTH_CONFIG,
        "box": BOX_OAUTH_CONFIG,
    }

    if provider not in configs:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state parameter")

    # Validate state and extract bound user_id from HMAC signature
    user_id = _get_user_id_from_state(state, provider)
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # R88: fail closed. The previous fallback bound tokens to the FIRST
        # database row (the bootstrap admin) whenever the signed state
        # referenced a user id absent from the DB — exactly how an attacker
        # who initiated a flow for a fabricated/victim id planted their own
        # provider credentials on the admin account.
        raise HTTPException(
            status_code=401,
            detail="OAuth state references an unknown user",
        )

    # CSRF / token-binding check: if this request carries an authenticated
    # session, the user it belongs to MUST be the user the state was minted
    # for. A validly-signed state for user-a presented in user-b's session
    # means the state was hijacked mid-flow — bind the attacker's tokens to
    # user-a's account. (Public callback keeps working for provider redirects:
    # the session check is additive; a missing/invalid session falls through
    # to the signed state as the sole credential.)
    session_user = None
    try:
        session_user = await get_current_user(request, db)
    except HTTPException:
        pass

    if session_user is not None and str(session_user.id) != user_id:
        raise HTTPException(
            status_code=403,
            detail="OAuth state was issued for a different user",
        )

    result = await _handle_callback_logic(provider, code, configs[provider], request, db, user=user)

    # Redirect to frontend. None means the exchange produced no token and
    # none was previously stored — send the user to the failure page rather
    # than a success page for a connect that never happened.
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    if result is None:
        return RedirectResponse(
            url=f"{frontend_url}/oauth/error?provider={provider}&reason=token_exchange_failed"
        )
    return RedirectResponse(url=f"{frontend_url}/oauth/success?provider={provider}")

# ============================================================================
# Management Endpoints
# ============================================================================

@router.get("/tokens")
async def list_oauth_tokens(
    request: Request,
    provider: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all connected OAuth integrations for the current user.

    B15: OAuthToken has no provider/status/expires_at/last_used columns. The
    integration name is stored on client_id as ``{provider}_client`` (see
    _handle_callback_logic); liveness is is_active; expiry is
    access_token_expires_at; last-use is last_used_at."""
    current_user = await get_current_user(request, db)
    query = db.query(OAuthToken).filter(OAuthToken.user_id == current_user.id)

    if provider:
        query = query.filter(OAuthToken.client_id == f"{provider}_client")

    tokens = query.all()
    return {
        "integrations": [
            {
                # client_id is stored as "{provider}_client" at callback time.
                "provider": t.client_id[:-len("_client")] if t.client_id and t.client_id.endswith("_client") else t.client_id,
                "status": "active" if t.is_active else "revoked",
                "expires_at": t.access_token_expires_at.isoformat() if t.access_token_expires_at else None,
                "last_used": t.last_used_at.isoformat() if t.last_used_at else None,
                # Consent grant scope — lets the UI detect missing permissions
                # (e.g. Mail.Send added to the request after the token was
                # minted; refreshes never expand scopes).
                "scope": getattr(t, "scope", "") or "",
            } for t in tokens
        ]
    }

@router.delete("/tokens/{provider}")
async def revoke_oauth_token(
    provider: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an OAuth integration.

    B15: OAuthToken has no provider/status columns. Filter on client_id
    (stored as ``{provider}_client``); revocation sets is_active=False."""
    current_user = await get_current_user(request, db)
    token = db.query(OAuthToken).filter(
        OAuthToken.user_id == current_user.id,
        OAuthToken.client_id == f"{provider}_client"
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail=f"No integration found for {provider}")

    token.is_active = False

    # Propagate to the IntegrationToken rows the services actually read:
    # /api/integrations/connection-status and every data route resolve
    # credentials from these, not from the legacy OAuthToken page above.
    # Skipping this left the hub showing "connected" — and every data route
    # working — after the user disconnected the integration.
    if provider in _TOKEN_FANOUT:
        provider_keys = _TOKEN_FANOUT[provider]
    else:
        provider_keys = [provider]
    db.query(IntegrationToken).filter(
        IntegrationToken.user_id == current_user.id,
        IntegrationToken.provider.in_(provider_keys),
    ).update({IntegrationToken.status: "revoked"}, synchronize_session=False)

    db.commit()
    return {"status": "success", "message": f"Revoked {provider} integration"}

@router.get("/config-status")
async def oauth_config_status(current_user: User = Depends(get_current_user)):
    """Check configuration status of all OAuth providers."""
    configs = {
        "google": GOOGLE_OAUTH_CONFIG,
        "linkedin": LINKEDIN_OAUTH_CONFIG,
        "microsoft": MICROSOFT_OAUTH_CONFIG,
        "salesforce": SALESFORCE_OAUTH_CONFIG,
        "slack": SLACK_OAUTH_CONFIG,
        "github": GITHUB_OAUTH_CONFIG,
        "asana": ASANA_OAUTH_CONFIG,
        "notion": NOTION_OAUTH_CONFIG,
        "trello": TRELLO_OAUTH_CONFIG,
        "dropbox": DROPBOX_OAUTH_CONFIG,
        "whatsapp": WHATSAPP_OAUTH_CONFIG,
        "zoho": ZOHO_OAUTH_CONFIG,
    }
    
    return {
        provider: config.is_configured() for provider, config in configs.items()
    }
