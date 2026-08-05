"""
Tests for decode_token revocation check (core/auth.py::decode_token).

decode_token is the synchronous token-decode helper used by non-async callers
(security_dependencies, auth_helpers, device_websocket). Unlike get_current_user
and get_current_user_ws, it previously omitted the is_token_revoked check — so a
revoked (logged-out) JWT stayed "valid" for any code path using decode_token.
"""

import pytest
from datetime import datetime, timedelta, timezone

from core.auth import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    decode_token,
    revoke_token,
    is_token_revoked,
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


def test_revoked_token_rejected_by_decode_token(db):
    """A revoked JWT MUST return None from decode_token, not the payload.

    decode_token is used by security_dependencies / auth_helpers / device_websocket;
    skipping the revocation check (as get_current_user does not) means a logged-out
    token stays valid on those paths.
    """
    # Build a token with a known jti.
    import time
    expire = int(time.time()) + 3600
    payload = {
        "sub": "user-decode-1",
        "exp": expire,
        "jti": "jti-decode-revoke-1",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    # Pre-revoke: valid.
    assert decode_token(token) is not None

    # Revoke it (simulate logout).
    revoke_token("jti-decode-revoke-1", expire)

    # Must now be rejected.
    assert decode_token(token) is None, (
        "decode_token returned a payload for a REVOKED token — it must check "
        "is_token_revoked, mirroring get_current_user / get_current_user_ws."
    )


def test_non_revoked_token_still_decodes(db):
    """Sanity: a valid, non-revoked token still decodes."""
    token = create_access_token(data={"sub": "user-decode-2"})
    payload = decode_token(token)
    assert payload is not None
