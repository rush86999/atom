"""
Regression test: POST /api/auth/change-password must exist on the running app
(core.auth_endpoints router — the one mounted by main_api_app via the lazy
integration registry) and work end-to-end with the frontend's payload shape
{current_password, new_password}.

Pilot bug: the frontend settings/account page called /api/auth/change-password
and got 404 — the route only existed in api.enterprise_auth_endpoints.py
(an unrelated router with an old_password field name, mounted only in
minimal_app.py). TDD: this test failed with 404 before the fix.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from core.auth_endpoints import router as auth_router
from core.models import Base, User
from core.database import get_db


@pytest.fixture(scope="function")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db: Session = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = override_get_db

    # Register + login a real user through the app so hashing/verification
    # match production paths.
    c = TestClient(app)
    email = f"pilot_{uuid.uuid4().hex[:8]}@example.com"
    reg = c.post(
        "/api/auth/register",
        json={"email": email, "password": "OldPassw0rd!", "first_name": "Pilot", "last_name": "User"},
    )
    assert reg.status_code in (200, 201), reg.text
    login = c.post("/api/auth/login", json={"username": email, "password": "OldPassw0rd!"})
    assert login.status_code == 200, login.text
    c.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    c._pilot_email = email
    yield c
    c.close()


def test_change_password_route_exists_and_accepts_frontend_payload(client: TestClient):
    """Frontend sends {current_password, new_password} — must not 404/422."""
    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "OldPassw0rd!", "new_password": "NewPassw0rd!"},
    )
    assert res.status_code == 200, res.text
    assert res.json().get("success") is True


def test_change_password_rejects_wrong_current_password(client: TestClient):
    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongPassw0rd!", "new_password": "NewPassw0rd!"},
    )
    assert res.status_code == 400, res.text


def test_change_password_logs_in_with_new_password(client: TestClient):
    client.post(
        "/api/auth/change-password",
        json={"current_password": "OldPassw0rd!", "new_password": "NewPassw0rd!"},
    )
    res = client.post(
        "/api/auth/login",
        json={"username": client._pilot_email, "password": "NewPassw0rd!"},
    )
    assert res.status_code == 200, res.text