"""Admin runtime-settings API tests (W-pattern: TestClient + overrides).

Covers: admin gate, catalog serialization (secrets locked), PUT
validation + persistence + audit, cache invalidation, DELETE reset.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.runtime_settings as rs
from api.admin_runtime_settings_routes import router as settings_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import RuntimeSetting, SettingChangeAudit, User, UserRole


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[RuntimeSetting.__table__, SettingChangeAudit.__table__],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _clean_cache():
    rs.invalidate_settings_cache()
    yield
    rs.invalidate_settings_cache()


def _user(role: str = UserRole.ADMIN.value):
    u = MagicMock()
    u.id = "admin-1"
    u.email = "admin@test.local"
    u.role = role
    return u


def _client(db, user):
    app = FastAPI()
    app.include_router(settings_router)

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# Auth / roles
# ============================================================================


class TestAuth:
    def test_non_admin_gets_403(self, db):
        client = _client(db, _user(UserRole.MEMBER.value))
        assert client.get("/api/v1/admin/settings").status_code == 403
        assert (
            client.put("/api/v1/admin/settings/ATOM_TOOL_CACHE_TTL", json={"value": 5}).status_code
            == 403
        )
        assert client.delete("/api/v1/admin/settings/ATOM_TOOL_CACHE_TTL").status_code == 403

    def test_unauthenticated_gets_401(self, db):
        app = FastAPI()
        app.include_router(settings_router)

        def _deny():
            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = _deny
        client = TestClient(app, raise_server_exceptions=False)
        assert client.get("/api/v1/admin/settings").status_code == 401


# ============================================================================
# Catalog listing
# ============================================================================


class TestListing:
    def test_catalog_lists_values_and_sources(self, db):
        client = _client(db, _user())
        resp = client.get("/api/v1/admin/settings")
        assert resp.status_code == 200
        body = resp.json()
        entries = {e["key"]: e for e in body["data"]["settings"]}
        entry = entries["ATOM_SELF_CONSISTENCY_SAMPLES"]
        assert entry["value"] == 3 and entry["source"] == "default"
        assert "Hallucination" in body["data"]["categories"][0] or any(
            "Hallucination" in c for c in body["data"]["categories"]
        )

    def test_secrets_locked_and_valueless(self, db):
        client = _client(db, _user())
        body = client.get("/api/v1/admin/settings").json()
        entries = {e["key"]: e for e in body["data"]["settings"]}
        secret = entries["OPENAI_API_KEY"]
        assert secret["secret"] is True
        assert secret["editable"] is False
        assert "value" not in secret

    def test_categories_endpoint(self, db):
        client = _client(db, _user())
        body = client.get("/api/v1/admin/settings/categories").json()
        assert body["success"] is True
        assert body["data"]["count"] > 100


# ============================================================================
# Mutations
# ============================================================================


class TestMutations:
    def test_put_persists_and_invalidates_cache(self, db):
        client = _client(db, _user())
        # Warm the resolver cache first.
        assert rs.resolve_setting("ATOM_SELF_CONSISTENCY").value is False
        resp = client.put(
            "/api/v1/admin/settings/ATOM_SELF_CONSISTENCY", json={"value": True}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["value"] is True and body["data"]["source"] == "db"

        row = db.get(RuntimeSetting, "ATOM_SELF_CONSISTENCY")
        assert row is not None and row.value_json is True
        assert row.updated_by == "admin@test.local"

    def test_put_writes_audit_row(self, db):
        client = _client(db, _user())
        client.put("/api/v1/admin/settings/ATOM_MOA_SAMPLES", json={"value": 5})
        audits = db.query(SettingChangeAudit).all()
        assert len(audits) == 1
        assert audits[0].setting_key == "ATOM_MOA_SAMPLES"
        assert audits[0].new_value_json == 5
        assert audits[0].changed_by == "admin@test.local"

    def test_put_unknown_key_404(self, db):
        client = _client(db, _user())
        resp = client.put("/api/v1/admin/settings/NOT_REAL_XYZ", json={"value": 1})
        assert resp.status_code == 404

    def test_put_secret_key_403(self, db):
        client = _client(db, _user())
        resp = client.put(
            "/api/v1/admin/settings/OPENAI_API_KEY", json={"value": "sk-evil"}
        )
        assert resp.status_code == 403
        assert db.get(RuntimeSetting, "OPENAI_API_KEY") is None

    def test_put_type_mismatch_400(self, db):
        client = _client(db, _user())
        resp = client.put(
            "/api/v1/admin/settings/ATOM_MOA_SAMPLES", json={"value": "not-a-number"}
        )
        assert resp.status_code == 400

    def test_put_then_resolver_sees_new_value(self, db):
        client = _client(db, _user())
        client.put(
            "/api/v1/admin/settings/ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD",
            json={"value": 0.6},
        )
        res = rs.resolve_setting("ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD", db=db)
        assert res.source == "db" and abs(res.value - 0.6) < 1e-9

    def test_delete_removes_override(self, db):
        client = _client(db, _user())
        client.put("/api/v1/admin/settings/ATOM_MOA_SAMPLES", json={"value": 5})
        resp = client.delete("/api/v1/admin/settings/ATOM_MOA_SAMPLES")
        assert resp.status_code == 200
        assert db.get(RuntimeSetting, "ATOM_MOA_SAMPLES") is None
        # Falls back to default.
        res = rs.resolve_setting("ATOM_MOA_SAMPLES", db=db)
        assert res.value == 3 and res.source == "default"

    def test_delete_without_override_is_idempotent(self, db):
        client = _client(db, _user())
        resp = client.delete("/api/v1/admin/settings/ATOM_MOA_SAMPLES")
        assert resp.status_code == 200

    def test_env_still_wins_after_ui_edit(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_MOA_SAMPLES", "7")
        client = _client(db, _user())
        client.put("/api/v1/admin/settings/ATOM_MOA_SAMPLES", json={"value": 5})
        res = rs.resolve_setting("ATOM_MOA_SAMPLES", db=db)
        assert res.source == "env" and res.value == 7


# ============================================================================
# Audit endpoint
# ============================================================================


class TestAuditEndpoint:
    def test_audit_listing(self, db):
        client = _client(db, _user())
        client.put("/api/v1/admin/settings/ATOM_TOOL_CACHE_TTL", json={"value": 45})
        body = client.get("/api/v1/admin/settings/audit").json()
        changes = body["data"]["changes"]
        assert len(changes) == 1
        assert changes[0]["setting_key"] == "ATOM_TOOL_CACHE_TTL"
        assert changes[0]["new_value_json"] == 45


# ============================================================================
# Learning & Verification status (guidance page feed)
# ============================================================================


class TestLearningStatus:
    def _patch_stats(self, monkeypatch, counts=None, panel=None):
        monkeypatch.setattr(
            "core.exchange_example_service.get_corpus_counts",
            lambda db: counts or {"positive": 4, "negative": 2, "total": 6},
        )
        monkeypatch.setattr(
            "core.verify_panel.get_panel_run_stats",
            lambda db: panel or {"total": 25, "ran": 24, "ran_rate": 0.96,
                                 "mean_agreement": 0.85},
        )

    def test_non_admin_gets_403(self, db, monkeypatch):
        self._patch_stats(monkeypatch)
        client = _client(db, _user(UserRole.MEMBER.value))
        resp = client.get("/api/v1/admin/settings/learning-status")
        assert resp.status_code == 403

    def test_admin_payload_shape(self, db, monkeypatch):
        monkeypatch.delenv("ATOM_EXCHANGE_MEMORY", raising=False)
        monkeypatch.delenv("ATOM_VERIFY_PANEL", raising=False)
        self._patch_stats(monkeypatch)
        client = _client(db, _user())
        resp = client.get("/api/v1/admin/settings/learning-status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["exchange"]["mode"] == "shadow"
        assert data["exchange"]["source"] == "default"
        assert data["exchange"]["env_locked"] is False
        assert data["exchange"]["counts"]["total"] == 6
        assert data["exchange"]["auto_promote"] is False
        assert data["panel"]["mode"] == "off"
        assert data["panel"]["stats"]["ran_rate"] == 0.96
        assert data["panel"]["auto_promote"] is False

    def test_env_override_reported_as_locked(self, db, monkeypatch):
        monkeypatch.setenv("ATOM_VERIFY_PANEL", "shadow")
        self._patch_stats(monkeypatch)
        client = _client(db, _user())
        data = client.get("/api/v1/admin/settings/learning-status").json()["data"]
        assert data["panel"]["mode"] == "shadow"
        assert data["panel"]["source"] == "env"
        assert data["panel"]["env_locked"] is True
