"""
Tests for WebSocket auth token revocation (core/auth.py::get_current_user_ws).

The HTTP path (get_current_user) rejects revoked tokens via is_token_revoked,
but the WS path previously omitted that check — so a logged-out / revoked JWT
stayed valid for every WebSocket endpoint (notifications, canvas live updates,
workspace channel) until the 24h JWT expiry.
"""

import pytest
from datetime import datetime, timedelta, timezone

from core.auth import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_current_user_ws,
    is_token_revoked,
    revoke_token,
)
from core.models import User, UserStatus, UserRole, Tenant

from jose import jwt


@pytest.fixture
def db(worker_database, monkeypatch):
    import core.database as db_mod
    monkeypatch.setattr(db_mod, "SessionLocal", worker_database)
    session = worker_database()
    yield session
    session.rollback()
    session.close()


def _make_user(db, user_id="ws-user-1", tenant_id="t-ws", email="ws@test.local"):
    if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
        db.add(Tenant(id=tenant_id, name="T", subdomain=f"t-{tenant_id}"))
        db.flush()
    u = User(
        id=user_id,
        email=email,
        tenant_id=tenant_id,
        first_name="WS",
        last_name="Test",
        role=UserRole.MEMBER.value,
        status=UserStatus.ACTIVE,
    )
    db.add(u)
    db.commit()
    return u


@pytest.mark.asyncio
async def test_revoked_token_rejected_on_websocket(db):
    """A revoked JWT must NOT authenticate a WebSocket connection."""
    user = _make_user(db)
    token = create_access_token(data={"sub": user.id})

    # The token works before revocation.
    authed = await get_current_user_ws(token, db)
    assert authed is not None, "Pre-revoke: token should authenticate"

    # Revoke it (simulating logout).
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    revoke_token(payload["jti"], payload["exp"])

    # Now it MUST be rejected on the WS path (mirrors the HTTP path).
    rejected = await get_current_user_ws(token, db)
    assert rejected is None, (
        "Revoked token was accepted on the WebSocket path — get_current_user_ws "
        "must check is_token_revoked, mirroring get_current_user."
    )


@pytest.mark.asyncio
async def test_non_revoked_token_still_works_on_websocket(db):
    """Sanity: a valid, non-revoked token still authenticates."""
    user = _make_user(db, user_id="ws-user-2", tenant_id="t-ws2", email="ws2@test.local")
    token = create_access_token(data={"sub": user.id})

    authed = await get_current_user_ws(token, db)
    assert authed is not None
    assert authed.id == user.id
