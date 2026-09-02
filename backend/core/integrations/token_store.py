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


async def resolve_integration_token(
    user_id: str,
    providers: Sequence[str],
    refresh: Callable[[Optional[str]], Awaitable[Optional[Dict[str, Any]]]],
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
    the decrypted refresh token and returns the token response dict (or None).

    Returns None when no active row exists so callers fall through to legacy
    connection stores; DB/crypto errors are logged and degrade to None.
    """
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
            if not token_record or not token_record.access_token:
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
                new_tokens = await refresh(refresh_plain)
                if new_tokens and new_tokens.get("access_token"):
                    token_record.access_token = encrypt_token(new_tokens["access_token"])
                    token_record.expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=int(new_tokens.get("expires_in", 3600))
                    )
                    db.commit()
                    return new_tokens["access_token"]
                return None

            return decrypt_token(token_record.access_token, allow_plaintext=True)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error resolving IntegrationToken {list(providers)} for user: {e}")
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
