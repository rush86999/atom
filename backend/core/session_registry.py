"""Durable device-session inventory for the Active Sessions surface (WA-075).

Two stores, two jobs — and they are deliberately not interchangeable:

* ``RevokedToken`` is the *enforcement* ledger. ``core.auth`` consults it on
  every authenticated HTTP, WebSocket, mobile and enterprise read through
  ``credential_session_matches``/``is_token_revoked``.
* ``UserSession`` is the *inventory* shown in Settings → Active Sessions. It is
  descriptive only: nothing authorizes on it.

Before this module the settings page wrote inventory rows from a client
supplied token and "revocation" flipped ``is_active``, which no auth path ever
read — so revoking a device changed a label and nothing else. This module keeps
the inventory honest and drives the existing enforcement ledger.

Invariants:

* The raw bearer token is never persisted. ``session_token`` holds
  ``"sha256:<hex>"`` for rows this module writes; ``token_jti`` carries the
  JWT id used for revocation and ``is_current`` matching.
* Rows written before WA-075 hold the raw token. They are upgraded lazily when
  the presented bearer matches, or when they are revoked. Unverifiable rows
  (opaque value, or a token whose ``sub`` is not the row owner) are reported as
  skipped — never silently "revoked".
* Inventory writes are best-effort and must never fail a login. Enforcement
  writes are confirmed by a fresh-database read and reported truthfully.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from jose import JWTError, jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.auth import ALGORITHM, SECRET_KEY
from core.auth import revoke_token as remember_revocation
from core.models import RevokedToken, User, UserSession

logger = logging.getLogger(__name__)

FINGERPRINT_PREFIX = "sha256:"
ACCESS_TOKEN_SECONDS = 60 * 60 * 24

#: Inventory row has a token identity that can be revoked.
SOURCE_TRACKED = "tracked"
#: Row pre-dates WA-075 but its stored raw token decodes to the row owner.
SOURCE_LEGACY_VERIFIED = "legacy_verified"
#: Row carries no token identity we can prove; it must not be reported revoked.
UNVERIFIABLE = "unverifiable"


def token_fingerprint(token: str) -> str:
    """Stable, non-reversible inventory key for a bearer token."""
    return FINGERPRINT_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_session_claims(token: Optional[str], *, verify_exp: bool = True) -> Optional[Dict[str, Any]]:
    """Decode a backend-issued JWT for inventory purposes, never to authorize."""
    if not isinstance(token, str) or token.count(".") != 2:
        return None
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": verify_exp},
        )
    except JWTError:
        return None


def _claim_subject(payload: Dict[str, Any]) -> Optional[str]:
    subject = payload.get("sub") or payload.get("id") or payload.get("user_id")
    return subject if isinstance(subject, str) and subject else None


def _claim_expiry(payload: Dict[str, Any]) -> Optional[datetime]:
    exp = payload.get("exp")
    if type(exp) not in (int, float):
        return None
    return datetime.fromtimestamp(exp, timezone.utc)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# --- best-effort display metadata (never used for authorization) ------------
_BROWSERS = (
    ("Edg", "Edge"),
    ("OPR", "Opera"),
    ("Chrome", "Chrome"),
    ("Firefox", "Firefox"),
    ("Safari", "Safari"),
)
_OSES = (
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Linux", "Linux"),
)


def describe_user_agent(user_agent: Optional[str]) -> Tuple[Optional[str], Optional[str], str]:
    """Return (browser, os, device_type) for display only.

    No dependency is added for this: the previous producer was the Next.js
    proxy (ua-parser-js). A compact heuristic keeps the table populated after
    issuance moved server-side.
    """
    if not isinstance(user_agent, str) or not user_agent:
        return None, None, "desktop"
    browser = next((name for needle, name in _BROWSERS if needle in user_agent), None)
    system = next((name for needle, name in _OSES if needle in user_agent), None)
    if re.search(r"iPad|Tablet", user_agent):
        device = "tablet"
    elif re.search(r"iPhone|Android|Mobile", user_agent):
        device = "mobile"
    else:
        device = "desktop"
    return browser, system, device


def _request_metadata(request: Any) -> Dict[str, Optional[str]]:
    if request is None:
        return {"user_agent": None, "ip_address": None, "browser": None, "os": None, "device_type": "desktop"}
    user_agent = request.headers.get("user-agent") if hasattr(request, "headers") else None
    forwarded = request.headers.get("x-forwarded-for") if hasattr(request, "headers") else None
    if isinstance(forwarded, str) and forwarded.strip():
        # Display only; the first hop is not trusted for authorization.
        ip_address = forwarded.split(",")[0].strip()
    else:
        client = getattr(request, "client", None)
        ip_address = getattr(client, "host", None)
    browser, os_name, device_type = describe_user_agent(user_agent)
    return {
        "user_agent": user_agent,
        "ip_address": ip_address,
        "browser": browser,
        "os": os_name,
        "device_type": device_type,
    }


# --- inventory writes -------------------------------------------------------
def _find_row(
    db: Session,
    *,
    jti: Optional[str],
    fingerprint: Optional[str],
    raw_token: Optional[str],
) -> Optional[UserSession]:
    clauses = []
    if jti:
        clauses.append(UserSession.token_jti == jti)
    if fingerprint:
        clauses.append(UserSession.session_token == fingerprint)
    if raw_token:
        clauses.append(UserSession.session_token == raw_token)
    if not clauses:
        return None
    with db.no_autoflush:
        return db.query(UserSession).filter(or_(*clauses)).first()


def register_session(
    db: Session,
    user: User,
    token: str,
    *,
    request: Any = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[UserSession]:
    """Record a server-issued session in the inventory. Never raises.

    The caller must have authenticated ``token`` already; the subject check
    here is a second guard so a logged-in user can never own another user's
    session row.
    """
    claims = payload or decode_session_claims(token)
    if claims is None:
        return None
    subject = _claim_subject(claims)
    jti = claims.get("jti")
    expires_at = _claim_expiry(claims)
    if subject != user.id or not isinstance(jti, str) or not jti or expires_at is None:
        logger.warning("Session inventory skipped: unusable claims for user %s", getattr(user, "id", None))
        return None

    fingerprint = token_fingerprint(token)
    metadata = _request_metadata(request)
    try:
        row = _find_row(db, jti=jti, fingerprint=fingerprint, raw_token=token)
        if row is not None and row.user_id != user.id:
            logger.warning("Session inventory refused a foreign row for user %s", user.id)
            return None
        now = datetime.now(timezone.utc)
        if row is None:
            row = UserSession(user_id=user.id, session_token=fingerprint, token_jti=jti)
            db.add(row)
        row.session_token = fingerprint
        row.token_jti = jti
        row.tenant_id = getattr(user, "tenant_id", None)
        row.user_agent = metadata["user_agent"]
        row.ip_address = metadata["ip_address"]
        row.browser = metadata["browser"]
        row.os = metadata["os"]
        row.device_type = metadata["device_type"]
        row.expires_at = expires_at
        row.is_active = True
        row.last_active_at = now
        if row.created_at is None:
            row.created_at = now
        db.commit()
        db.refresh(row)
        return row
    except Exception as error:  # inventory must never break sign-in
        db.rollback()
        logger.warning("Session inventory write failed error_class=%s", type(error).__name__)
        return None


def touch_session(
    db: Session,
    user: User,
    token: str,
    *,
    request: Any = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[UserSession], bool]:
    """Refresh activity for the presented session, registering it if unknown.

    Returns ``(row, registered)``. ``registered`` is True when this call had to
    create the inventory row, which tells the UI the device was previously
    untracked (pre-WA-075 issuance or an uninstrumented path).
    """
    claims = payload or decode_session_claims(token)
    if claims is None:
        return None, False
    jti = claims.get("jti")
    fingerprint = token_fingerprint(token)
    try:
        row = _find_row(db, jti=jti if isinstance(jti, str) else None,
                        fingerprint=fingerprint, raw_token=token)
        if row is not None and row.user_id != user.id:
            return None, False
        if row is None:
            row = register_session(db, user, token, request=request, payload=claims)
            return row, row is not None
        row.last_active_at = datetime.now(timezone.utc)
        if isinstance(jti, str) and jti:
            row.token_jti = jti
        if row.session_token != fingerprint:
            row.session_token = fingerprint  # lazy upgrade: drop the raw bearer
        db.commit()
        db.refresh(row)
        return row, False
    except Exception as error:
        db.rollback()
        logger.warning("Session inventory touch failed error_class=%s", type(error).__name__)
        return None, False


def is_current_row(row: UserSession, *, jti: Optional[str], token: Optional[str]) -> bool:
    """Match the presented credential without ever exposing stored material."""
    if jti and row.token_jti:
        return row.token_jti == jti
    if not token:
        return False
    stored = row.session_token
    if not isinstance(stored, str):
        return False
    # New rows store a fingerprint; pre-WA-075 rows stored the raw token.
    return stored == token_fingerprint(token) or stored == token


def resolve_row_identity(row: UserSession) -> Tuple[Optional[str], Optional[datetime], str]:
    """Resolve the revocable identity of an inventory row.

    Returns ``(jti, expires_at, source)``. A ``jti`` is only returned when the
    token identity belongs to the row owner; anything else is unverifiable and
    must be reported as skipped rather than "revoked".
    """
    if isinstance(row.token_jti, str) and row.token_jti:
        return row.token_jti, _as_utc(row.expires_at), SOURCE_TRACKED
    stored = row.session_token
    claims = decode_session_claims(stored, verify_exp=False)
    if claims is None:
        return None, None, UNVERIFIABLE
    if _claim_subject(claims) != row.user_id:
        # A row that carries another user's token must never revoke that token.
        return None, None, UNVERIFIABLE
    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti:
        return None, None, UNVERIFIABLE
    return jti, _claim_expiry(claims) or _as_utc(row.expires_at), SOURCE_LEGACY_VERIFIED


def is_revocable(row: UserSession) -> bool:
    return resolve_row_identity(row)[0] is not None


def deactivate_session_by_jti(db: Session, user_id: str, jti: Optional[str]) -> int:
    """Mark the matching inventory row inactive after logout. Never raises."""
    if not isinstance(jti, str) or not jti:
        return 0
    try:
        updated = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.token_jti == jti,
        ).update({"is_active": False}, synchronize_session=False)
        # Pre-WA-075 rows have no jti yet; they were upgraded at login/touch.
        db.commit()
        return int(updated or 0)
    except Exception as error:
        db.rollback()
        logger.warning("Session inventory logout deactivation failed error_class=%s", type(error).__name__)
        return 0


def deactivate_user_sessions(db: Session, user_id: str) -> int:
    """Mark every inventory row for a user inactive (password change/reset)."""
    try:
        updated = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,  # noqa: E712 - SQL boolean predicate
        ).update({"is_active": False}, synchronize_session=False)
        db.commit()
        return int(updated or 0)
    except Exception as error:
        db.rollback()
        logger.warning("Session inventory bulk deactivation failed error_class=%s", type(error).__name__)
        return 0


def _readback(
    db: Session,
    *,
    user_id: str,
    revoked: Iterable[str],
    row_ids: Iterable[str],
) -> bool:
    """Confirm the enforcement ledger and inventory commit from a fresh read."""
    from sqlalchemy.orm import Session as SyncSession

    revoked = list(revoked)
    row_ids = list(row_ids)
    try:
        with SyncSession(bind=db.get_bind()) as fresh:
            for jti in revoked:
                receipt = fresh.get(RevokedToken, jti)
                if receipt is None or receipt.user_id != user_id:
                    return False
            for row_id in row_ids:
                row = fresh.get(UserSession, row_id)
                if row is None or row.is_active:
                    return False
        return True
    except Exception as error:
        logger.warning("Session revocation readback failed error_class=%s", type(error).__name__)
        return False


def revoke_rows(
    db: Session,
    user: User,
    rows: List[UserSession],
    *,
    reason: str,
    request: Any = None,
    event_type: str = "update",
    action: str = "sessions_revoked",
) -> Dict[str, Any]:
    """Revoke inventory rows through the durable ledger in one transaction.

    ``rows`` must already be owner-scoped by the caller. Returns a structured,
    truthful outcome:

    ``{"revoked": n, "skipped": n, "already_revoked": n,
       "skip_reasons": [...], "verification": {...}, "audit_id": str|None}``

    No raw token or jti is ever included in the audit payload or this result.
    """
    now = datetime.now(timezone.utc)
    revoked: List[str] = []
    already: List[str] = []
    skipped: List[Dict[str, str]] = []
    row_ids: List[str] = []

    try:
        seen = set()
        for row in rows:
            jti, expires_at, _source = resolve_row_identity(row)
            row_ids.append(row.id)
            if jti is None:
                skipped.append({"id": row.id, "reason": "unverifiable_session_token"})
                row.is_active = False  # the entry is not a usable session any more
                continue
            if expires_at is not None and expires_at <= now:
                skipped.append({"id": row.id, "reason": "expired"})
                row.is_active = False
                continue
            # Lazily upgrade a legacy raw-token row so the bearer is dropped.
            row.token_jti = jti
            if row.session_token and decode_session_claims(row.session_token, verify_exp=False):
                row.session_token = token_fingerprint(row.session_token)
            row.is_active = False
            if jti in seen:
                continue
            seen.add(jti)
            existing = db.query(RevokedToken).filter_by(jti=jti).first()
            if existing is not None:
                already.append(jti)
            else:
                db.add(RevokedToken(
                    jti=jti,
                    user_id=user.id,
                    expires_at=expires_at or (now + _default_window()),
                    reason=reason,
                    token_type="access",
                ))
                revoked.append(jti)
        db.commit()
    except Exception as error:
        db.rollback()
        logger.warning("Session revocation failed error_class=%s", type(error).__name__)
        return {
            "revoked": 0,
            "skipped": len(skipped),
            "already_revoked": 0,
            "skip_reasons": skipped,
            "verification": {"status": "unavailable", "effect": "unknown"},
            "audit_id": None,
        }

    # Memory denylist is only a fast path; the durable read below is authority.
    for row in rows:
        jti, expires_at, _source = resolve_row_identity(row)
        if jti:
            remember_revocation(jti, int((expires_at or now).timestamp()))

    verified = _readback(db, user_id=user.id, revoked=revoked, row_ids=row_ids)
    audit_id: Optional[str] = None
    try:
        from core.audit_service import audit_service
        audit_id = audit_service.log_event(
            db,
            event_type=event_type,
            action=action,
            description="User session revoked from the Active Sessions surface",
            user_id=user.id,
            user_email=getattr(user, "email", None),
            workspace_id=getattr(user, "workspace_id", None),
            tenant_id=getattr(user, "tenant_id", None),
            resource="user_sessions",
            security_level="medium",
            metadata={
                "revoked_count": len(revoked),
                "already_revoked_count": len(already),
                "skipped_count": len(skipped),
                "skip_reasons": [item["reason"] for item in skipped],
            },
            request=request,
        )
    except Exception as error:
        logger.warning("Session revocation audit unavailable error_class=%s", type(error).__name__)

    return {
        "revoked": len(revoked),
        "skipped": len(skipped),
        "already_revoked": len(already),
        "skip_reasons": skipped,
        "verification": {
            "status": "verified" if verified else "unavailable",
            "effect": "committed" if verified else "unknown",
        },
        "audit_id": audit_id,
    }


def _default_window():
    from datetime import timedelta
    return timedelta(seconds=ACCESS_TOKEN_SECONDS)
