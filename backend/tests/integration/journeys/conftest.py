"""
Test infrastructure for real-world user journey tests.

These tests walk through what a real user does end-to-end (signup → login →
chat → feedback → rate limiting). They use a real auth flow (NOT mocked) so
they surface bugs in the actual auth/chat/feedback pipeline.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

# Ensure backend is on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-journey-tests")
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture(scope="function")
def real_auth_client():
    """A TestClient that overrides the DB but runs REAL auth.

    Unlike conftest_coverage's `client`, this does NOT override
    `get_current_user` — so register/login must succeed for real, surfacing
    auth pipeline bugs. The DB is in-memory SQLite (isolated per test).
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.database import get_db
    from core.models import Base
    import main as main_module

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = main_module.app
    app.dependency_overrides[get_db] = override_get_db

    # The enterprise auth service opens its OWN session via next(get_db())
    # instead of using the injected dependency. Patch it to use the test
    # session so the register/login round-trip works in-memory.
    import core.database as db_module
    original_get_db = db_module.get_db
    db_module.get_db = override_get_db

    # Also patch any module that imports get_db directly (not via dependency).
    import api.enterprise_auth_endpoints as ent_auth
    if hasattr(ent_auth, 'get_db'):
        ent_auth.get_db = override_get_db

    # Patch trusted hosts to allow testserver.
    original_allowed = getattr(app, "allowed_hosts", None)

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    db_module.get_db = original_get_db
    if hasattr(ent_auth, 'get_db'):
        ent_auth.get_db = original_get_db
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset the in-memory rate limiters before each test for isolation."""
    try:
        from core.security.auth_rate_limit import (
            _login_limiter, _register_limiter, _refresh_limiter,
        )
        _login_limiter._hits.clear()
        _register_limiter._hits.clear()
        _refresh_limiter._hits.clear()
    except Exception:
        pass
    yield


@pytest.fixture
def unique_email():
    """Generate a unique email for each test."""
    return f"journey_{uuid.uuid4().hex[:8]}@test.example.com"


@pytest.fixture
def registered_user(real_auth_client, unique_email):
    """Register a user and return (client, email, password, token).

    The enterprise auth register endpoint returns 201 with {success, data: {user_id}}
    (no token). The user must then login to get an access_token.
    """
    client = real_auth_client
    password = "TestPass123!"
    resp = client.post("/api/auth/register", json={
        "email": unique_email,
        "password": password,
        "first_name": "Journey",
        "last_name": "Tester",
    })
    assert resp.status_code in (200, 201), f"Register failed: {resp.status_code} {resp.text}"

    # The enterprise register doesn't return a token — login to get one.
    login_resp = client.post("/api/auth/login", json={
        "username": unique_email,
        "password": password,
    })
    assert login_resp.status_code == 200, f"Login after register failed: {login_resp.status_code} {login_resp.text}"
    token = login_resp.json().get("access_token")
    assert token, "No access_token from login"
    return client, unique_email, password, token
