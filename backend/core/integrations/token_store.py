"""Shared IntegrationToken store access for journey/integration services.

The unified OAuth connect flow (``/api/v1/auth/oauth/{provider}/callback``)
writes encrypted IntegrationToken rows — one per provider alias of a single
umbrella grant (see ``_TOKEN_FANOUT`` in ``api/oauth_routes.py``). Journey
services (Box, Google Drive, OneDrive, …) resolve their access token from
those rows and must revoke them on disconnect.

This module holds the DB plumbing that every service had copy-pasted
(box_service, google_drive_service, onedrive_service): decrypt, refresh when
near expiry and persist, revoke a grant family. Only the provider alias list
and the provider-specific refresh HTTP call differ per service. Zoho
WorkDrive is the next candidate but is NOT a mechanical swap: it prefers
legacy ConnectionService rows and refreshes when ``expires_at`` is missing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence

logger = logging.getLogger(__name__)

# Refresh when the access token expires within this window.
_EXPIRY_MARGIN = timedelta(minutes=2)


class TokenRefreshError(Exception):
    """Provider refresh rejection with a stable, non-secret classification.

    ``kind`` is one of ``invalid_grant`` (user consent expired/revoked),
    ``invalid_client`` (client configuration rejected), ``refresh_rejected``
    (another provider rejection), ``refresh_unavailable`` (no refresh token),
    or ``transient`` (network/5xx/429). Callers must not collapse these into
    "revoked permission".
    """

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(detail or kind)
        self.kind = kind
        self.detail = detail

# One umbrella OAuth grant writes one IntegrationToken row per provider alias
# (see _TOKEN_FANOUT in api/oauth_routes.py). A catalog source must ask the
# whole family before deciding a grant is gone.
SOURCE_PROVIDER_ALIASES = {
    "onedrive": ("onedrive", "microsoft", "outlook", "microsoft365"),
    "microsoft": ("microsoft", "onedrive", "outlook", "microsoft365"),
    "microsoft365": ("microsoft365", "microsoft", "onedrive", "outlook"),
    "outlook": ("outlook", "microsoft", "onedrive", "microsoft365"),
    "google_drive": ("google_drive", "google", "gmail"),
    "google": ("google", "google_drive", "gmail"),
    "gmail": ("gmail", "google", "google_drive"),
    "zoho_workdrive": ("zoho_workdrive", "zoho"),
    "zoho": ("zoho", "zoho_workdrive"),
}


def connected_source_grant_state(
    source: str, user_id: Optional[str],
) -> str:
    """Return ``active`` / ``revoked`` / ``disconnected`` / ``unknown``.

    Read-only state check over the existing token store. It does NOT refresh;
    a caller that needs live access still resolves the token through the
    provider service. ``unknown`` means this is not a connected-source family
    or the caller did not supply an authenticated user, so legacy/local reads
    keep working.
    """
    aliases = SOURCE_PROVIDER_ALIASES.get(str(source or "").strip().lower())
    uid = str(user_id or "").strip()
    if not aliases or not uid:
        return "unknown"
    from core.database import SessionLocal
    from core.models import IntegrationToken

    db = SessionLocal()
    try:
        rows = (
            db.query(IntegrationToken)
            .filter(
                IntegrationToken.user_id == uid,
                IntegrationToken.provider.in_(list(aliases)),
            )
            .all()
        )
        if any(
            str(row.status or "").lower() == "active" and row.access_token
            for row in rows
        ):
            return "active"
        return "revoked" if rows else "disconnected"
    except Exception as e:  # noqa: BLE001 — state check must not crash a read
        logger.error(f"Error checking connected grant {source} for {uid}: {e}")
        return "unknown"
    finally:
        db.close()


def _publish_resolution(
    status_out: Optional[Dict[str, Any]], **values: Any,
) -> None:
    if status_out is None:
        return
    status_out.clear()
    status_out.update(values)


async def resolve_integration_token(
    user_id: str,
    providers: Sequence[str],
    refresh: Callable[[Optional[str]], Awaitable[Optional[Dict[str, Any]]]],
    *,
    status_out: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Resolve the active IntegrationToken for a user, refreshing if near expiry.

    ``providers`` lists the alias rows of ONE umbrella grant (e.g. onedrive/
    microsoft/outlook/microsoft365). The callback fans the same token and
    scopes out to every alias row, so any active row in the family serves;
    ``updated_at desc`` picks the most recently refreshed grant when a user
    reconnected or holds several grants. If a future flow ever writes family
    rows with DIFFERENT scopes, narrow the alias list per service instead of
    widening this query.

    ``refresh`` is the provider-specific refresh-token exchange: it receives
    the decrypted refresh token and returns the token response dict (or raises
    :class:`TokenRefreshError` with a stable classification). When the
    response carries ``refresh_token`` that replacement is encrypted and
    persisted; when it is omitted the existing refresh token is preserved.

    ``status_out`` receives the non-secret resolution state so callers can
    distinguish ordinary expiry, refresh unavailable, invalid_grant,
    invalid_client and transient failures. The return value remains the
    access token (or None) for backward compatibility.

    Returns None when no active row exists so callers may fall through to a
    legitimate legacy connection store; revoked/invalid/transient states set
    ``status_out["state"]`` so callers do NOT fall through.
    """
    _publish_resolution(
        status_out, state="resolution_error", token_available=False,
        refresh_attempted=False, refresh_succeeded=False,
        refresh_token_replaced=False, requires_reconnect=False,
        retryable=False, detail="",
    )
    try:
        from core.database import SessionLocal
        from core.models import IntegrationToken
        from core.privsec.token_encryption import decrypt_token, encrypt_token

        db = SessionLocal()
        try:
            token_record = (
                db.query(IntegrationToken)
                .filter(
                    IntegrationToken.user_id == user_id,
                    IntegrationToken.provider.in_(list(providers)),
                    IntegrationToken.status == "active",
                )
                .order_by(IntegrationToken.updated_at.desc())
                .first()
            )
            if not token_record:
                _publish_resolution(
                    status_out, state="no_grant", token_available=False,
                    refresh_attempted=False, refresh_succeeded=False,
                    refresh_token_replaced=False, requires_reconnect=False,
                    retryable=False, detail="",
                )
                return None
            if not token_record.access_token:
                _publish_resolution(
                    status_out, state="refresh_unavailable",
                    token_available=False, refresh_attempted=False,
                    refresh_succeeded=False, refresh_token_replaced=False,
                    requires_reconnect=not bool(token_record.refresh_token),
                    retryable=False, detail="stored access token missing",
                )
                return None

            expires_at = token_record.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at and expires_at < (datetime.now(timezone.utc) + _EXPIRY_MARGIN):
                refresh_plain = (
                    decrypt_token(token_record.refresh_token, allow_plaintext=True)
                    if token_record.refresh_token
                    else None
                )
                if not refresh_plain:
                    _publish_resolution(
                        status_out, state="refresh_unavailable",
                        token_available=False, refresh_attempted=False,
                        refresh_succeeded=False, refresh_token_replaced=False,
                        requires_reconnect=True, retryable=False,
                        detail="no refresh token",
                    )
                    return None
                try:
                    new_tokens = await refresh(refresh_plain)
                except TokenRefreshError as exc:
                    _publish_resolution(
                        status_out, state=exc.kind, token_available=False,
                        refresh_attempted=True, refresh_succeeded=False,
                        refresh_token_replaced=False,
                        requires_reconnect=exc.kind in {
                            "invalid_grant", "refresh_unavailable"},
                        retryable=exc.kind == "transient",
                        detail=exc.detail[:240],
                    )
                    return None
                except Exception as exc:  # noqa: BLE001 — classify, never revoke
                    _publish_resolution(
                        status_out, state="transient", token_available=False,
                        refresh_attempted=True, refresh_succeeded=False,
                        refresh_token_replaced=False, requires_reconnect=False,
                        retryable=True, detail=type(exc).__name__,
                    )
                    return None
                if new_tokens and new_tokens.get("access_token"):
                    token_record.access_token = encrypt_token(new_tokens["access_token"])
                    token_record.expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=int(new_tokens.get("expires_in", 3600))
                    )
                    replaced = bool(new_tokens.get("refresh_token"))
                    if replaced:
                        # Providers may rotate refresh tokens on every
                        # exchange. Persist the replacement; when the response
                        # omits it, leave the existing token untouched.
                        token_record.refresh_token = encrypt_token(
                            new_tokens["refresh_token"])
                    token_record.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    _publish_resolution(
                        status_out, state="refreshed", token_available=True,
                        refresh_attempted=True, refresh_succeeded=True,
                        refresh_token_replaced=replaced,
                        requires_reconnect=False, retryable=False, detail="",
                    )
                    return new_tokens["access_token"]
                _publish_resolution(
                    status_out, state="refresh_failed", token_available=False,
                    refresh_attempted=True, refresh_succeeded=False,
                    refresh_token_replaced=False, requires_reconnect=False,
                    retryable=False, detail="refresh returned no access token",
                )
                return None

            token = decrypt_token(token_record.access_token, allow_plaintext=True)
            _publish_resolution(
                status_out, state="valid", token_available=True,
                refresh_attempted=False, refresh_succeeded=False,
                refresh_token_replaced=False, requires_reconnect=False,
                retryable=False, detail="",
            )
            return token
        finally:
            db.close()
    except Exception as e:
        # DB/crypto failures are platform errors, never a revoked consent.
        logger.error(f"Error resolving IntegrationToken {list(providers)} for user: {e}")
        _publish_resolution(
            status_out, state="resolution_error", token_available=False,
            refresh_attempted=False, refresh_succeeded=False,
            refresh_token_replaced=False, requires_reconnect=False,
            retryable=True, detail=type(e).__name__,
        )
        return None


def revoke_integration_tokens(user_id: str, providers: Sequence[str]) -> int:
    """Revoke (``status='revoked'``) every IntegrationToken row in a family.

    Used by journey disconnect endpoints: the resolver above reads these rows,
    so a disconnect that leaves them active leaves the integration usable.
    Raises on DB failure — callers must NOT report success if this fails.
    Returns the number of rows updated.
    """
    from core.database import SessionLocal
    from core.models import IntegrationToken

    db = SessionLocal()
    try:
        updated = (
            db.query(IntegrationToken)
            .filter(
                IntegrationToken.user_id == str(user_id),
                IntegrationToken.provider.in_(list(providers)),
            )
            .update({IntegrationToken.status: "revoked"}, synchronize_session=False)
        )
        db.commit()
        return updated
    finally:
        db.close()
