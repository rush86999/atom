"""Tests for integration token reconciliation (all providers).

Incident (2026-09-04/05): the world DB was wiped and re-seeded while
file-backed state survived. Tokens referencing users that no longer exist
must be deactivated (pollers filter status='active'), and long-expired
active tokens must be reported for reconnect — never auto-deactivated
(the auto-refresh flow may still recover them).
"""

import pytest

from core.integration_startup_reconciliation import reconcile_integration_tokens


@pytest.fixture
def token_env(monkeypatch):
    """Scratch in-memory DB with the token/user tables and a patched
    SessionLocal (the reconciliation imports it from core.database)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    from core.models import IntegrationToken, User  # noqa: F401 — register tables

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    import core.database as db_mod

    monkeypatch.setattr(db_mod, "SessionLocal", Session, raising=False)
    return Session


def _mk_user(session, user_id="u-1"):
    from core.models import User

    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        hashed_password="x",
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
    )
    session.add(user)
    session.commit()
    return user


def _mk_token(session, user_id, provider="slack", status="active", expires_at=None):
    from core.models import IntegrationToken

    token = IntegrationToken(
        id=f"tok-{provider}-{user_id}",
        tenant_id="t-1",
        user_id=user_id,
        provider=provider,
        access_token="secret",
        status=status,
        expires_at=expires_at,
    )
    session.add(token)
    session.commit()
    return token


def test_orphaned_token_is_deactivated(token_env):
    from datetime import datetime, timezone

    session = token_env()
    _mk_user(session, "u-1")
    _mk_token(session, "u-1")                       # live owner — untouched
    _mk_token(session, "ghost", provider="outlook")  # dead owner

    summary = reconcile_integration_tokens()

    assert summary["orphaned"] == 1
    row = session.query(
        __import__("core.models", fromlist=["IntegrationToken"]).IntegrationToken
    ).filter_by(provider="outlook").first()
    assert row.status == "orphaned", "dead-owner token must stop being polled"
    live = session.query(
        __import__("core.models", fromlist=["IntegrationToken"]).IntegrationToken
    ).filter_by(provider="slack").first()
    assert live.status == "active"


def test_stale_expired_token_reported_not_deactivated(token_env):
    from datetime import datetime, timedelta, timezone

    session = token_env()
    _mk_user(session, "u-1")
    old = datetime.now(timezone.utc) - timedelta(hours=72)
    _mk_token(session, "u-1", provider="gmail", expires_at=old)

    summary = reconcile_integration_tokens()

    assert summary["orphaned"] == 0
    assert "gmail" in summary["stale_expired"], "must be reported for reconnect"
    row = session.query(
        __import__("core.models", fromlist=["IntegrationToken"]).IntegrationToken
    ).filter_by(provider="gmail").first()
    assert row.status == "active", "auto-refresh may still recover it"


def test_fresh_install_is_a_clean_noop(token_env):
    session = token_env()
    _mk_user(session, "u-1")
    from datetime import datetime, timedelta, timezone

    fresh = datetime.now(timezone.utc) + timedelta(hours=1)
    _mk_token(session, "u-1", provider="microsoft", expires_at=fresh)

    summary = reconcile_integration_tokens()

    assert summary["orphaned"] == 0
    assert summary["stale_expired"] == []
    assert summary["active_by_provider"] == {"microsoft": 1}
