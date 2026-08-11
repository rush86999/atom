"""Coverage wave 46 — api/gateway_key_routes.py (0% → 90%+).

Key lifecycle: create (plaintext-once), list, revoke (owned-only 404), rotate
(revoke+new key). Auth overridden; DB via in-memory SQLite with real
GatewayApiKey rows.
"""
import os
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.gateway_key_routes import router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import GatewayApiKey, User


@pytest.fixture
def client():
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    app = FastAPI()
    app.include_router(router)

    def _user():
        return User(id="u1", email="u@x.com", first_name="U", last_name="X",
                    role="admin", status="active")

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    session.close()
    engine.dispose()


class TestCreateKey:
    def test_create_returns_plaintext_once(self, client):
        c, session = client
        resp = c.post("/api/gateway/keys", json={"name": "prod"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"].startswith("atom_sk_")
        assert data["key_prefix"].startswith("atom_sk_")
        # stored row holds only the hash — plaintext never persisted
        row = session.query(GatewayApiKey).filter_by(id=data["id"]).first()
        assert row.key_hash != data["key"]
        assert row.key_prefix == data["key_prefix"]

    def test_create_custom_fields(self, client):
        c, session = client
        expires = datetime.now(timezone.utc).isoformat()
        resp = c.post("/api/gateway/keys", json={
            "name": "temp", "rate_limit_per_minute": 5, "expires_at": expires})
        assert resp.status_code == 201
        row = session.query(GatewayApiKey).filter_by(id=resp.json()["id"]).first()
        assert row.rate_limit_per_minute == 5
        assert row.expires_at is not None

    def test_create_validation(self, client):
        c, _ = client
        assert c.post("/api/gateway/keys", json={"rate_limit_per_minute": 0}).status_code == 422
        assert c.post("/api/gateway/keys", json={"name": "x" * 300}).status_code == 422


class TestListKeys:
    def test_list_empty(self, client):
        c, _ = client
        resp = c.get("/api/gateway/keys")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_returns_serialized_rows(self, client):
        c, session = client
        row = GatewayApiKey(
            id=str(uuid.uuid4()), key_hash="h", key_prefix="atom_sk_abcd",
            name="k1", user_id="u1", rate_limit_per_minute=60,
        )
        session.add(row)
        session.commit()
        resp = c.get("/api/gateway/keys")
        assert len(resp.json()["data"]) == 1
        entry = resp.json()["data"][0]
        assert entry["id"] == row.id
        assert entry["expires_at"] is None
        assert entry["last_used"] is None


class TestRevokeKey:
    def test_revoke_owned_key(self, client):
        c, session = client
        created = c.post("/api/gateway/keys", json={}).json()
        resp = c.delete(f"/api/gateway/keys/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        row = session.query(GatewayApiKey).filter_by(id=created["id"]).first()
        assert row.is_active is False
        assert row.revoked_at is not None

    def test_revoke_unknown_or_not_owned_404(self, client):
        c, session = client
        # another user's key
        row = GatewayApiKey(
            id=str(uuid.uuid4()), key_hash="h", key_prefix="atom_sk_zzzz",
            name="other", user_id="other-user", rate_limit_per_minute=60,
        )
        session.add(row)
        session.commit()
        assert c.delete(f"/api/gateway/keys/{row.id}").status_code == 404
        assert c.delete("/api/gateway/keys/nonexistent").status_code == 404


class TestRotateKey:
    def test_rotate_revokes_old_and_creates_new(self, client):
        c, session = client
        created = c.post("/api/gateway/keys", json={"name": "orig", "rate_limit_per_minute": 7}).json()
        resp = c.post(f"/api/gateway/keys/{created['id']}/rotate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] != created["id"]
        assert data["key"].startswith("atom_sk_")
        old = session.query(GatewayApiKey).filter_by(id=created["id"]).first()
        assert old.is_active is False
        assert old.last_rotated is not None
        new = session.query(GatewayApiKey).filter_by(id=data["id"]).first()
        assert new.name == "orig"
        assert new.rate_limit_per_minute == 7

    def test_rotate_unknown_404(self, client):
        c, _ = client
        assert c.post("/api/gateway/keys/nonexistent/rotate").status_code == 404

    def test_all_routes_require_auth(self):
        app = FastAPI()
        app.include_router(router)
        c = TestClient(app)
        assert c.get("/api/gateway/keys").status_code == 401
        assert c.post("/api/gateway/keys", json={}).status_code == 401
