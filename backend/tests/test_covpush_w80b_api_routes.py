"""Coverage wave W80B — 8 API modules to >=95% statement coverage standalone.

Targets (before -> after, measured against existing suites):
1. api/auth_2fa_routes.py                      40% -> 100%
2. api/document_ingestion_routes.py            33% -> 100%
3. api/episode_routes.py                       58% -> 100%
4. api/stage_router_routes.py                  30% -> 100%
5. api/deeplinks.py                            48% -> 100%
6. api/workflow_debugging.py                   32% -> 100%
7. api/browser_routes.py                       33% -> 100%
8. api/integrations/memory_backfill_routes.py   0% -> 100%

Conventions (W79C/W78B): FastAPI TestClient + dependency_overrides, patches on
real module names (no `backend.` prefix), zero network / LLM spend (playwright
mocked), no real DB (in-memory SQLite only for 2FA + deeplinks audit/stats,
MagicMock sessions elsewhere).

Bugs found (TDD red first):
- memory_backfill_routes.trigger_backfill / trigger_all_backfills: HTTPException
  (400 start_date>end_date) swallowed by bare `except Exception` -> 500.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth_2fa_routes import router as auth_2fa_router
from api.browser_routes import router as browser_router
from api.deeplinks import router as deeplink_router
from api.document_ingestion_routes import router as doc_ingest_router
from api.episode_routes import router as episode_router
from api.integrations.memory_backfill_routes import router as backfill_router
from api.stage_router_routes import router as stage_router_router
from api.workflow_debugging import router as wf_debug_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import DeepLinkAudit, User, UserRole


# ============================================================================
# Shared helpers
# ============================================================================
def _app(router, user=None, db=None):
    app = FastAPI()
    app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    if db is not None:
        def _get_db():
            yield db
        app.dependency_overrides[get_db] = _get_db
        app.db = db
    return app


def _client(router, user=None, db=None):
    app = _app(router, user=user, db=db)
    client = TestClient(app, raise_server_exceptions=False)
    client.app = app
    return client


def _chain(db):
    """Configure a MagicMock db.query() chain so all filters return the same
    mock (last-call wins configuration pattern)."""
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    return q


@pytest.fixture
def user():
    u = MagicMock()
    u.id = "user-w80b"
    u.email = "user@test.local"
    u.role = UserRole.MEMBER.value
    u.status = "active"
    return u


# ============================================================================
# 1. api/auth_2fa_routes.py — real pyotp + in-memory SQLite (W89 pattern)
# ============================================================================
TEST_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture(autouse=True)
def bypass_2fa_rate_limit():
    with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(True, 5)):
        yield


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_2fa_user(db, user_id="u2fa", *, enabled=False, secret=None, codes=None):
    existing = db.query(User).filter(User.id == user_id).first()
    if existing:
        return existing
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        first_name="T",
        last_name="U",
        role="admin",
        status="active",
        tenant_id="t1",
        two_factor_enabled=enabled,
        two_factor_secret=secret,
        two_factor_backup_codes=codes,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def client_factory(db):
    def _build(user_id="u2fa"):
        user = _make_2fa_user(db, user_id)
        app = FastAPI()
        app.include_router(auth_2fa_router)

        def _override_db():
            yield db

        def _override_user():
            return user

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = _override_user
        return TestClient(app, raise_server_exceptions=False)
    return _build


class Test2FAStatus:
    def test_status_disabled(self, client_factory):
        resp = client_factory().get("/api/auth/2fa/status")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False}

    def test_status_enabled(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)
        resp = client_factory().get("/api/auth/2fa/status")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True}

    def test_status_unauthenticated(self, db):
        resp = _client(auth_2fa_router, db=db).get("/api/auth/2fa/status")
        assert resp.status_code == 401


class Test2FASetup:
    def test_setup_success(self, client_factory):
        resp = client_factory().post("/api/auth/2fa/setup")
        assert resp.status_code == 200
        body = resp.json()
        assert body["secret"]
        assert "otpauth://totp/" in body["otpauth_url"]

    def test_setup_saves_secret(self, db, client_factory):
        client_factory().post("/api/auth/2fa/setup")
        u = db.query(User).filter(User.id == "u2fa").first()
        assert u.two_factor_secret

    def test_setup_already_enabled_409(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)
        resp = client_factory().post("/api/auth/2fa/setup")
        assert resp.status_code == 409

    def test_setup_unauthenticated(self, db):
        resp = _client(auth_2fa_router, db=db).post("/api/auth/2fa/setup")
        assert resp.status_code == 401


class Test2FAEnable:
    def test_enable_success_with_backup_codes(self, db, client_factory):
        u = _make_2fa_user(db, "u2fa", secret=TEST_SECRET)
        code = pyotp.TOTP(TEST_SECRET).now()
        with patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client_factory().post("/api/auth/2fa/enable", json={"code": code})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        codes = body["data"]["backup_codes"]
        assert len(codes) == 5
        assert all("-" in c and len(c) == 19 for c in codes)
        assert u.two_factor_enabled is True
        assert len(u.two_factor_backup_codes) == 5
        audit.log_event.assert_called_once()

    def test_enable_invalid_code(self, db, client_factory):
        _make_2fa_user(db, "u2fa", secret=TEST_SECRET)
        resp = client_factory().post("/api/auth/2fa/enable", json={"code": "000000"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_enable_not_initiated(self, client_factory):
        resp = client_factory().post("/api/auth/2fa/enable", json={"code": "000000"})
        assert resp.status_code == 422
        assert "2FA setup not initiated" in resp.json()["detail"]["error"]["message"]

    def test_enable_already_enabled(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)
        resp = client_factory().post("/api/auth/2fa/enable", json={"code": "000000"})
        assert resp.status_code == 409

    def test_enable_missing_code_422(self, client_factory):
        resp = client_factory().post("/api/auth/2fa/enable", json={})
        assert resp.status_code == 422

    def test_enable_rate_limited_429(self, client_factory):
        with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(False, 0)):
            resp = client_factory().post("/api/auth/2fa/enable", json={"code": "000000"})
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Too many 2FA attempts. Try again in a minute."

    def test_enable_unauthenticated(self, db):
        resp = _client(auth_2fa_router, db=db).post(
            "/api/auth/2fa/enable", json={"code": "000000"})
        assert resp.status_code == 401


class Test2FADisable:
    def test_disable_success(self, db, client_factory):
        u = _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET,
                           codes=["A1B2-C3D4-E5F6-G7H8"])
        code = pyotp.TOTP(TEST_SECRET).now()
        with patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client_factory().post("/api/auth/2fa/disable", json={"code": code})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert u.two_factor_enabled is False
        assert u.two_factor_secret is None
        assert u.two_factor_backup_codes is None
        audit.log_event.assert_called_once()

    def test_disable_not_enabled(self, client_factory):
        resp = client_factory().post("/api/auth/2fa/disable", json={"code": "000000"})
        assert resp.status_code == 422
        assert "2FA is not enabled" in resp.json()["detail"]["error"]["message"]

    def test_disable_invalid_code(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)
        resp = client_factory().post("/api/auth/2fa/disable", json={"code": "000000"})
        assert resp.status_code == 422

    def test_disable_rate_limited_429(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)
        with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(False, 0)):
            resp = client_factory().post("/api/auth/2fa/disable", json={"code": "000000"})
        assert resp.status_code == 429

    def test_disable_unauthenticated(self, db):
        resp = _client(auth_2fa_router, db=db).post(
            "/api/auth/2fa/disable", json={"code": "000000"})
        assert resp.status_code == 401


class Test2FABackupVerify:
    def test_backup_verify_success_consumes_code(self, db, client_factory):
        u = _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET,
                           codes=["AAAA-BBBB-CCCC-DDDD", "1111-2222-3333-4444"])
        with patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client_factory().post(
                "/api/auth/2fa/backup/verify", json={"code": "AAAA-BBBB-CCCC-DDDD"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["remaining_codes"] == 1
        assert u.two_factor_backup_codes == ["1111-2222-3333-4444"]
        audit.log_event.assert_called_once()

    def test_backup_verify_not_enabled(self, client_factory):
        resp = client_factory().post("/api/auth/2fa/backup/verify", json={"code": "X"})
        assert resp.status_code == 422

    def test_backup_verify_invalid_code(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET,
                       codes=["AAAA-BBBB-CCCC-DDDD"])
        resp = client_factory().post("/api/auth/2fa/backup/verify", json={"code": "NOPE"})
        assert resp.status_code == 422

    def test_backup_verify_no_codes_stored(self, db, client_factory):
        _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)
        resp = client_factory().post("/api/auth/2fa/backup/verify", json={"code": "X"})
        assert resp.status_code == 422

    def test_backup_verify_unauthenticated(self, db):
        resp = _client(auth_2fa_router, db=db).post(
            "/api/auth/2fa/backup/verify", json={"code": "X"})
        assert resp.status_code == 401


class Test2FAVerifyAction:
    def _action_user(self, db):
        return _make_2fa_user(db, "u2fa", enabled=True, secret=TEST_SECRET)

    def test_verify_action_success(self, db, client_factory):
        self._action_user(db)
        code = pyotp.TOTP(TEST_SECRET).now()
        fake_hitl = AsyncMock()
        fake_hitl.resolve_action.return_value = {"action_id": "a1", "status": "approved"}
        with patch("core.hitl_service.hitl_service", fake_hitl), \
                patch("api.auth_2fa_routes.audit_service") as audit:
            resp = client_factory().post(
                "/api/auth/2fa/verify-action/act-1", json={"code": code})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["action_id"] == "a1"
        fake_hitl.resolve_action.assert_awaited_once_with(
            action_id="act-1", resolution="approved",
            resolver_id="u2fa", metadata={"verified_2fa": True})
        audit.log_event.assert_called_once()

    def test_verify_action_not_enabled(self, client_factory):
        resp = client_factory().post("/api/auth/2fa/verify-action/act-1", json={"code": "X"})
        assert resp.status_code == 422

    def test_verify_action_invalid_code(self, db, client_factory):
        self._action_user(db)
        resp = client_factory().post("/api/auth/2fa/verify-action/act-1", json={"code": "000000"})
        assert resp.status_code == 422

    def test_verify_action_service_failure_500(self, db, client_factory):
        self._action_user(db)
        code = pyotp.TOTP(TEST_SECRET).now()
        fake_hitl = AsyncMock()
        fake_hitl.resolve_action.side_effect = RuntimeError("boom")
        with patch("core.hitl_service.hitl_service", fake_hitl):
            resp = client_factory().post(
                "/api/auth/2fa/verify-action/act-1", json={"code": code})
        assert resp.status_code == 500

    def test_verify_action_rate_limited_429(self, db, client_factory):
        self._action_user(db)
        with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(False, 0)):
            resp = client_factory().post(
                "/api/auth/2fa/verify-action/act-1", json={"code": "000000"})
        assert resp.status_code == 429

    def test_verify_action_unauthenticated(self, db):
        resp = _client(auth_2fa_router, db=db).post(
            "/api/auth/2fa/verify-action/act-1", json={"code": "X"})
        assert resp.status_code == 401


class Test2FABackupCodeGeneration:
    def test_generate_backup_codes_format_and_length(self):
        from api.auth_2fa_routes import _generate_backup_codes

        codes = _generate_backup_codes(n=8)
        assert len(codes) == 8
        assert len(set(codes)) == 8
        for c in codes:
            parts = c.split("-")
            assert len(parts) == 4
            assert all(len(p) == 4 for p in parts)
            assert all(ch in "0123456789ABCDEF" for ch in c if ch != "-")

    def test_generate_backup_codes_default(self):
        from api.auth_2fa_routes import _generate_backup_codes

        assert len(_generate_backup_codes()) == 5

    def test_totp_rate_limit_function_direct(self):
        from api.auth_2fa_routes import totp_rate_limit
        from fastapi import Request

        req = MagicMock(spec=Request)
        with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(True, 4)):
            assert totp_rate_limit(req) is None
        with patch("api.auth_2fa_routes._2fa_limiter.check", return_value=(False, 0)):
            with pytest.raises(HTTPException) as ei:
                totp_rate_limit(req)
            assert ei.value.status_code == 429


# ============================================================================
# 2. api/document_ingestion_routes.py
# ============================================================================
@pytest.fixture
def di_client(user):
    return _client(doc_ingest_router, user=user)


def _mock_di_service():
    from core.auto_document_ingestion import get_document_ingestion_service
    svc = MagicMock()
    return svc, patch("core.auto_document_ingestion.get_document_ingestion_service",
                      return_value=svc)


class TestDocIngestionSettings:
    def test_get_all_success(self, di_client):
        svc, p = _mock_di_service()
        settings = {
            "integration_id": "gdrive", "enabled": True, "auto_sync_new_files": True,
            "file_types": ["pdf"], "sync_folders": [], "max_file_size_mb": 50,
            "sync_frequency_minutes": 60, "last_sync": "2026-01-01T00:00:00",
        }
        svc.get_all_settings.return_value = [settings]
        with p:
            resp = di_client.get("/api/document-ingestion/settings")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["integration_id"] == "gdrive"
        assert body[0]["last_sync"] is not None

    def test_get_all_service_failure_500(self, di_client):
        svc, p = _mock_di_service()
        svc.get_all_settings.side_effect = RuntimeError("boom")
        with p:
            resp = di_client.get("/api/document-ingestion/settings")
        assert resp.status_code == 500

    def test_get_all_unauthenticated(self):
        assert _client(doc_ingest_router).get(
            "/api/document-ingestion/settings").status_code == 401

    def test_get_one_success(self, di_client):
        svc, p = _mock_di_service()
        settings = SimpleNamespace(
            integration_id="dropbox", enabled=False, auto_sync_new_files=False,
            file_types=[], sync_folders=[], max_file_size_mb=25,
            sync_frequency_minutes=0, last_sync=None)
        svc.get_settings.return_value = settings
        with p:
            resp = di_client.get("/api/document-ingestion/settings/dropbox")
        assert resp.status_code == 200
        body = resp.json()
        assert body["integration_id"] == "dropbox"
        assert body["last_sync"] is None
        assert body["enabled"] is False

    def test_get_one_service_failure_500(self, di_client):
        svc, p = _mock_di_service()
        svc.get_settings.side_effect = RuntimeError("boom")
        with p:
            resp = di_client.get("/api/document-ingestion/settings/dropbox")
        assert resp.status_code == 500

    def test_get_one_unauthenticated(self):
        assert _client(doc_ingest_router).get(
            "/api/document-ingestion/settings/x").status_code == 401

    def test_update_success(self, di_client):
        svc, p = _mock_di_service()
        updated = SimpleNamespace(enabled=True, file_types=["pdf", "docx"])
        svc.update_settings.return_value = updated
        payload = {
            "integration_id": "gdrive", "enabled": True,
            "auto_sync_new_files": True, "file_types": ["pdf"],
            "sync_folders": ["/a"], "exclude_folders": ["/b"],
            "max_file_size_mb": 50, "sync_frequency_minutes": 30,
        }
        with p:
            resp = di_client.put("/api/document-ingestion/settings", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["enabled"] is True
        assert body["data"]["file_types"] == ["pdf", "docx"]
        svc.update_settings.assert_called_once()
        call_kw = svc.update_settings.call_args.kwargs
        assert call_kw["integration_id"] == "gdrive"
        assert call_kw["exclude_folders"] == ["/b"]

    def test_update_all_none_optional(self, di_client):
        svc, p = _mock_di_service()
        svc.update_settings.return_value = SimpleNamespace(
            enabled=False, file_types=[])
        with p:
            resp = di_client.put("/api/document-ingestion/settings",
                                 json={"integration_id": "gdrive"})
        assert resp.status_code == 200
        call_kw = svc.update_settings.call_args.kwargs
        assert call_kw["enabled"] is None and call_kw["file_types"] is None

    def test_update_service_failure_500(self, di_client):
        svc, p = _mock_di_service()
        svc.update_settings.side_effect = RuntimeError("boom")
        with p:
            resp = di_client.put("/api/document-ingestion/settings",
                                 json={"integration_id": "gdrive"})
        assert resp.status_code == 500

    def test_update_missing_integration_422(self, di_client):
        resp = di_client.put("/api/document-ingestion/settings", json={})
        assert resp.status_code == 422

    def test_update_unauthenticated(self):
        assert _client(doc_ingest_router).put(
            "/api/document-ingestion/settings", json={"integration_id": "x"}).status_code == 401


class TestDocIngestionSync:
    def test_sync_success(self, di_client):
        svc, p = _mock_di_service()
        svc.sync_integration = AsyncMock(return_value={
            "success": True, "files_found": 3, "files_ingested": 2,
            "files_skipped": 1, "errors": []})
        with p:
            resp = di_client.post("/api/document-ingestion/sync/gdrive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["files_ingested"] == 2
        assert body["message"] == "Sync completed"
        svc.sync_integration.assert_awaited_once_with("gdrive", force=False)

    def test_sync_force_flag(self, di_client):
        svc, p = _mock_di_service()
        svc.sync_integration = AsyncMock(return_value={"success": False, "error": "recent"})
        with p:
            resp = di_client.post("/api/document-ingestion/sync/gdrive?force=true")
        assert resp.status_code == 200
        assert resp.json()["message"] == "recent"
        svc.sync_integration.assert_awaited_once_with("gdrive", force=True)

    def test_sync_service_failure_500(self, di_client):
        svc, p = _mock_di_service()
        svc.sync_integration = AsyncMock(side_effect=RuntimeError("boom"))
        with p:
            resp = di_client.post("/api/document-ingestion/sync/gdrive")
        assert resp.status_code == 500

    def test_sync_unauthenticated(self):
        assert _client(doc_ingest_router).post(
            "/api/document-ingestion/sync/gdrive").status_code == 401

    def test_remove_memory_success(self, di_client):
        svc, p = _mock_di_service()
        svc.remove_integration_documents = AsyncMock(
            return_value={"success": True, "documents_removed": 12})
        with p:
            resp = di_client.delete("/api/document-ingestion/memory/gdrive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["documents_removed"] == 12
        assert "12 documents" in body["message"]

    def test_remove_memory_service_failure_500(self, di_client):
        svc, p = _mock_di_service()
        svc.remove_integration_documents = AsyncMock(side_effect=RuntimeError("boom"))
        with p:
            resp = di_client.delete("/api/document-ingestion/memory/gdrive")
        assert resp.status_code == 500

    def test_remove_memory_unauthenticated(self):
        assert _client(doc_ingest_router).delete(
            "/api/document-ingestion/memory/gdrive").status_code == 401

    def test_list_documents_success(self, di_client):
        svc, p = _mock_di_service()
        doc = SimpleNamespace(
            id="d1", file_name="report.pdf", file_path="/x/report.pdf",
            file_type="pdf", integration_id="gdrive", file_size_bytes=100,
            ingested_at=datetime(2026, 1, 1),
            content_preview="short")
        svc.get_ingested_documents.return_value = [doc]
        with p:
            resp = di_client.get("/api/document-ingestion/documents?integration_id=gdrive&file_type=pdf")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["metadata"]["count"] == 1
        assert body["data"][0]["content_preview"] == "short"
        svc.get_ingested_documents.assert_called_once_with("gdrive", "pdf")

    def test_list_documents_truncates_preview(self, di_client):
        svc, p = _mock_di_service()
        svc.get_ingested_documents.return_value = [SimpleNamespace(
            id="d2", file_name="f.txt", file_path="p", file_type="txt",
            integration_id="box", file_size_bytes=1,
            ingested_at=datetime(2026, 1, 1),
            content_preview="x" * 250)]
        with p:
            resp = di_client.get("/api/document-ingestion/documents")
        assert resp.status_code == 200
        assert resp.json()["data"][0]["content_preview"] == "x" * 200 + "..."

    def test_list_documents_service_failure_500(self, di_client):
        svc, p = _mock_di_service()
        svc.get_ingested_documents.side_effect = RuntimeError("boom")
        with p:
            resp = di_client.get("/api/document-ingestion/documents")
        assert resp.status_code == 500

    def test_list_documents_unauthenticated(self):
        assert _client(doc_ingest_router).get(
            "/api/document-ingestion/documents").status_code == 401


class TestDocIngestionSupported:
    def test_supported_integrations(self, di_client):
        resp = di_client.get("/api/document-ingestion/supported-integrations")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 6
        assert data[0]["id"] == "google_drive"
        assert data[-1]["id"] == "notion"
        assert data[-1]["supported_types"] == ["md", "txt"]

    def test_supported_integrations_anonymous_public(self):
        # NOTE: no auth dependency on this endpoint (static data, tracker-flagged)
        assert _client(doc_ingest_router).get(
            "/api/document-ingestion/supported-integrations").status_code == 200

    def test_supported_file_types_docling(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=True) as avail, \
                patch("core.docling_processor.get_docling_processor") as gp:
            proc = MagicMock()
            proc.get_supported_formats.return_value = ["pdf", "docx"]
            gp.return_value = proc
            resp = di_client.get("/api/document-ingestion/supported-file-types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["parser"] == "docling (OCR)"
        assert body["metadata"]["docling_available"] is True
        assert body["metadata"]["docling_formats"] == ["pdf", "docx"]

    def test_supported_file_types_no_docling(self, di_client):
        with patch("core.docling_processor.is_docling_available", return_value=False):
            resp = di_client.get("/api/document-ingestion/supported-file-types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["parser"] == "pypdf (PyPDF2)"
        assert body["metadata"]["docling_available"] is False
        assert body["metadata"]["docling_formats"] == []

    def test_supported_file_types_import_error(self, di_client):
        with patch.dict("sys.modules", {"core.docling_processor": None}):
            pass  # patch target exists below; real path: ImportError raised by import
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "core.docling_processor":
                raise ImportError("no docling")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            resp = di_client.get("/api/document-ingestion/supported-file-types")
        assert resp.status_code == 200
        assert resp.json()["metadata"]["docling_available"] is False

    def test_supported_file_types_anonymous_public(self):
        # NOTE: no auth dependency on this endpoint (static data, tracker-flagged)
        assert _client(doc_ingest_router).get(
            "/api/document-ingestion/supported-file-types").status_code == 200

    def test_ocr_status_docling(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=True), \
                patch("core.docling_processor.get_docling_processor") as gp:
            proc = MagicMock()
            proc.get_status.return_value = {
                "supported_formats": ["pdf"], "byok_integrated": True}
            gp.return_value = proc
            resp = di_client.get("/api/document-ingestion/ocr-status")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["ocr_engines"] == ["docling"]
        assert body["recommended_engine"] == "docling"
        assert body["docling"]["available"] is True

    def test_ocr_status_docling_import_error(self, di_client):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "core.docling_processor":
                raise ImportError("no docling")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            resp = di_client.get("/api/document-ingestion/ocr-status")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["docling"]["available"] is False
        assert body["ocr_engines"] == []

    def test_ocr_status_other_engines(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False):
            with patch(
                    "integrations.pdf_processing.pdf_ocr_service.TESSERACT_AVAILABLE",
                    True), \
                    patch("integrations.pdf_processing.pdf_ocr_service.EASYOCR_AVAILABLE",
                          True), \
                    patch("integrations.pdf_processing.pdf_ocr_service.DOCLING_AVAILABLE",
                          False):
                resp = di_client.get("/api/document-ingestion/ocr-status")
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["ocr_engines"] == ["tesseract", "easyocr"]
        assert body["recommended_engine"] == "tesseract"

    def test_ocr_status_other_engines_import_error(self, di_client):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "integrations.pdf_processing.pdf_ocr_service":
                raise ImportError("no ocr")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            resp = di_client.get("/api/document-ingestion/ocr-status")
        assert resp.status_code == 200

    def test_ocr_status_anonymous_public(self):
        # NOTE: no auth dependency on this endpoint (static data, tracker-flagged)
        assert _client(doc_ingest_router).get(
            "/api/document-ingestion/ocr-status").status_code == 200


class TestDocIngestionParse:
    def test_parse_docling_success(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=True), \
                patch("core.docling_processor.get_docling_processor") as gp:
            proc = MagicMock()
            proc.process_document = AsyncMock(return_value={
                "success": True, "content": "hello", "metadata": {"m": 1},
                "total_chars": 5, "page_count": 1})
            gp.return_value = proc
            resp = di_client.post(
                "/api/document-ingestion/parse",
                files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
                params={"export_format": "json"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["method"] == "docling"
        assert body["content"] == "hello"
        proc.process_document.assert_awaited_once()

    def test_parse_fallback_no_docling(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False), \
                patch("core.auto_document_ingestion.DocumentParser.parse_document",
                      new=AsyncMock(return_value="fallback text")) as dp:
            resp = di_client.post(
                "/api/document-ingestion/parse",
                files={"file": ("doc.txt", b"plain text", "text/plain")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["method"] == "fallback"
        assert body["content"] == "fallback text"
        assert body["total_chars"] == 13  # "fallback text" is 13 chars
        dp.assert_awaited_once()

    def test_parse_oversize_via_size_attr_422(self, di_client, monkeypatch):
        monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")
        resp = di_client.post(
            "/api/document-ingestion/parse",
            files={"file": ("big.pdf", b"x" * 100, "application/pdf")})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_parse_oversize_via_content_len_422(self, di_client, monkeypatch):
        monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")
        class NoSizeFile:
            def __init__(self):
                self.filename = "big.pdf"
                self.size = None

            async def read(self):
                return b"x" * 100
        resp = di_client.post(
            "/api/document-ingestion/parse",
            files={"file": ("big.pdf", b"x" * 100, "application/pdf")})
        assert resp.status_code == 422

    def test_parse_generic_exception_200_error_body(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=True), \
                patch("core.docling_processor.get_docling_processor") as gp:
            proc = MagicMock()
            proc.process_document = AsyncMock(side_effect=RuntimeError("boom"))
            gp.return_value = proc
            resp = di_client.post(
                "/api/document-ingestion/parse",
                files={"file": ("doc.pdf", b"x", "application/pdf")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["method"] == "error"
        assert body["error"] == "Document parsing failed"

    def test_parse_unauthenticated(self):
        resp = _client(doc_ingest_router).post(
            "/api/document-ingestion/parse",
            files={"file": ("doc.txt", b"x", "text/plain")})
        assert resp.status_code == 401


class TestDocIngestionUpload:
    def test_upload_docling_success(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=True), \
                patch("core.docling_processor.get_docling_processor") as gp, \
                patch("core.lancedb_handler.LanceDBHandler") as lh_cls:
            proc = MagicMock()
            proc.process_document = AsyncMock(return_value={
                "success": True, "content": "uploaded text", "metadata": {"pages": 2}})
            gp.return_value = proc
            handler = MagicMock()
            handler.get_table.return_value = True
            handler.add_document.return_value = True
            lh_cls.return_value = handler
            resp = di_client.post(
                "/api/document-ingestion/upload",
                files={"file": ("doc.md", b"# Hello", "text/markdown")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["file_name"] == "doc.md"
        assert body["data"]["extracted_chars"] == 13
        handler.add_document.assert_called_once()

    def test_upload_docling_failure_falls_back(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=True), \
                patch("core.docling_processor.get_docling_processor") as gp, \
                patch("core.auto_document_ingestion.DocumentParser.parse_document",
                      new=AsyncMock(return_value="parser text")) as dp, \
                patch("core.lancedb_handler.LanceDBHandler") as lh_cls:
            proc = MagicMock()
            proc.process_document = AsyncMock(return_value={"success": False})
            gp.return_value = proc
            handler = MagicMock()
            handler.get_table.return_value = True
            handler.add_document.return_value = True
            lh_cls.return_value = handler
            resp = di_client.post(
                "/api/document-ingestion/upload",
                files={"file": ("doc.txt", b"hi", "text/plain")})
        assert resp.status_code == 200
        assert resp.json()["data"]["extracted_chars"] == 11  # "parser text"
        dp.assert_awaited_once()

    def test_upload_fallback_no_docling(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False), \
                patch("core.auto_document_ingestion.DocumentParser.parse_document",
                      new=AsyncMock(return_value="parser text")), \
                patch("core.lancedb_handler.LanceDBHandler") as lh_cls:
            handler = MagicMock()
            handler.get_table.return_value = False
            handler.add_document.return_value = True
            lh_cls.return_value = handler
            resp = di_client.post(
                "/api/document-ingestion/upload",
                files={"file": ("doc.csv", b"a,b", "text/csv")})
        assert resp.status_code == 200
        handler.create_table.assert_called_once_with("documents")

    def test_upload_oversize_422(self, di_client, monkeypatch):
        monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")
        resp = di_client.post(
            "/api/document-ingestion/upload",
            files={"file": ("big.txt", b"x" * 100, "text/plain")})
        assert resp.status_code == 422

    def test_upload_unsupported_extension_422(self, di_client):
        resp = di_client.post(
            "/api/document-ingestion/upload",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
        assert resp.status_code == 422
        assert "not supported" in resp.json()["detail"]["error"]["message"]

    def test_upload_empty_text_400(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False), \
                patch("core.auto_document_ingestion.DocumentParser.parse_document",
                      new=AsyncMock(return_value="")):
            resp = di_client.post(
                "/api/document-ingestion/upload",
                files={"file": ("empty.txt", b"", "text/plain")})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Could not extract text from document"

    def test_upload_add_document_failure_500(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False), \
                patch("core.auto_document_ingestion.DocumentParser.parse_document",
                      new=AsyncMock(return_value="text")), \
                patch("core.lancedb_handler.LanceDBHandler") as lh_cls:
            handler = MagicMock()
            handler.get_table.return_value = True
            handler.add_document.return_value = False
            lh_cls.return_value = handler
            resp = di_client.post(
                "/api/document-ingestion/upload",
                files={"file": ("doc.txt", b"text", "text/plain")})
        assert resp.status_code == 500
        assert "vector database" in resp.json()["detail"]

    def test_upload_generic_exception_500(self, di_client):
        with patch("core.docling_processor.is_docling_available",
                   return_value=False), \
                patch("core.auto_document_ingestion.DocumentParser.parse_document",
                      new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = di_client.post(
                "/api/document-ingestion/upload",
                files={"file": ("doc.txt", b"text", "text/plain")})
        assert resp.status_code == 500

    def test_upload_unauthenticated(self):
        resp = _client(doc_ingest_router).post(
            "/api/document-ingestion/upload",
            files={"file": ("doc.txt", b"x", "text/plain")})
        assert resp.status_code == 401


class TestDocIngestionDirect:
    """Direct-call coverage for branches unreachable via TestClient."""

    def test_get_workspace_id_helper(self):
        from api.document_ingestion_routes import get_workspace_id

        assert get_workspace_id() == "default"

    def test_parse_oversize_when_size_attr_none(self, monkeypatch, user):
        # TestClient always sets UploadFile.size from the body, so the
        # `len(content) > MAX` branch (post-read) needs a size=None upload.
        from api.document_ingestion_routes import parse_document_file

        monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")

        class NoSizeUpload:
            filename = "big.pdf"
            size = None

            async def read(self):
                return b"x" * 100

        with pytest.raises(HTTPException) as ei:
            asyncio.run(parse_document_file(NoSizeUpload(), "markdown", user))
        assert ei.value.status_code == 422

    def test_upload_oversize_when_size_attr_none(self, monkeypatch, user):
        from api.document_ingestion_routes import upload_document

        monkeypatch.setenv("MAX_UPLOAD_BYTES", "10")

        class NoSizeUpload:
            filename = "big.txt"
            size = None

            async def read(self):
                return b"x" * 100

        with pytest.raises(HTTPException) as ei:
            asyncio.run(upload_document(NoSizeUpload(), user))
        assert ei.value.status_code == 422


# ============================================================================
# 3. api/episode_routes.py — mocked services + MagicMock db
# ============================================================================
def _episode_client(monkeypatch, db, user, **services):
    """Build client with all four episode services replaced by MagicMocks.
    Pass service return values via `services` (async methods become
    AsyncMock(return_value=...))."""
    from api import episode_routes as er

    seg = MagicMock()
    seg.create_episode_from_session = AsyncMock(
        return_value=services.get("episode", None))
    ret = MagicMock()
    for method in ("retrieve_temporal", "retrieve_semantic", "retrieve_sequential",
                   "retrieve_contextual", "retrieve_by_canvas_type",
                   "retrieve_canvas_aware", "retrieve_by_business_data"):
        setattr(ret, method, AsyncMock(return_value=services.get(method, {})))
    life = MagicMock()
    life.update_importance_scores = AsyncMock(
        return_value=services.get("update_importance_scores", True))
    life.decay_old_episodes = AsyncMock(
        return_value=services.get("decay", {}))
    life.consolidate_similar_episodes = AsyncMock(
        return_value=services.get("consolidate", {}))
    grad = MagicMock()
    grad.calculate_readiness_score = AsyncMock(
        return_value=services.get("readiness", {}))
    grad.run_graduation_exam = AsyncMock(
        return_value=services.get("exam", {}))
    grad.promote_agent = AsyncMock(
        return_value=services.get("promote", True))
    grad.get_graduation_audit_trail = AsyncMock(
        return_value=services.get("audit_trail", {}))

    monkeypatch.setattr(er, "EpisodeSegmentationService", MagicMock(return_value=seg))
    monkeypatch.setattr(er, "EpisodeRetrievalService", MagicMock(return_value=ret))
    monkeypatch.setattr(er, "EpisodeLifecycleService", MagicMock(return_value=life))
    monkeypatch.setattr(er, "AgentGraduationService", MagicMock(return_value=grad))
    return _client(episode_router, user=user, db=db), seg, ret, life, grad


def _ep(episode_id="ep-1", **kw):
    return SimpleNamespace(
        id=episode_id,
        task_description=kw.get("task_description", "Task"),
        status=kw.get("status", "completed"),
        started_at=kw.get("started_at", datetime(2026, 1, 1)),
        importance_score=kw.get("importance_score", 0.5),
        maturity_at_time=kw.get("maturity_at_time", "INTERN"),
        human_intervention_count=kw.get("human_intervention_count", 0),
        aggregate_feedback_score=kw.get("aggregate_feedback_score", 0.7),
        canvas_action_count=kw.get("canvas_action_count", 3),
        feedback_ids=kw.get("feedback_ids", []),
        tenant_id=kw.get("tenant_id", "t1"),
        agent_id=kw.get("agent_id", "ag-1"),
    )


class TestEpisodeCreate:
    def test_create_success(self, monkeypatch, user):
        ep = _ep("ep-new")
        client, seg, *_ = _episode_client(monkeypatch, MagicMock(), user, episode=ep)
        resp = client.post("/api/episodes/create", json={
            "session_id": "s1", "agent_id": "ag-1", "title": "T"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["episode_id"] == "ep-new"
        assert body["data"]["title"] == "Task"
        seg.create_episode_from_session.assert_awaited_once_with(
            session_id="s1", agent_id="ag-1", title="T")

    def test_create_failure_400(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user, episode=None)
        resp = client.post("/api/episodes/create", json={
            "session_id": "s1", "agent_id": "ag-1"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "EPISODE_CREATE_FAILED"

    def test_create_missing_fields_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        assert client.post("/api/episodes/create", json={}).status_code == 422

    def test_create_unauthenticated(self):
        assert _client(episode_router).post(
            "/api/episodes/create", json={"session_id": "s", "agent_id": "a"}
        ).status_code == 401


class TestEpisodeRetrieval:
    def test_retrieve_temporal(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_temporal={"episodes": []})
        resp = client.post("/api/episodes/retrieve/temporal", json={
            "agent_id": "ag-1", "time_range": "7d", "limit": 10})
        assert resp.status_code == 200
        assert resp.json() == {"episodes": []}
        ret.retrieve_temporal.assert_awaited_once_with(
            agent_id="ag-1", time_range="7d", user_id="user-w80b", limit=10)

    def test_retrieve_temporal_limit_over_200_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.post("/api/episodes/retrieve/temporal", json={
            "agent_id": "ag-1", "limit": 500})
        assert resp.status_code == 422

    def test_retrieve_semantic(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_semantic={"hits": 1})
        resp = client.post("/api/episodes/retrieve/semantic", json={
            "agent_id": "ag-1", "query": "sales", "limit": 5})
        assert resp.status_code == 200
        ret.retrieve_semantic.assert_awaited_once_with(
            agent_id="ag-1", query="sales", limit=5)

    def test_retrieve_semantic_limit_over_100_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.post("/api/episodes/retrieve/semantic", json={
            "agent_id": "ag-1", "query": "q", "limit": 101})
        assert resp.status_code == 422

    def test_retrieve_sequential(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_sequential={"segments": []})
        resp = client.get("/api/episodes/retrieve/ep-1?agent_id=ag-1")
        assert resp.status_code == 200
        ret.retrieve_sequential.assert_awaited_once_with(
            episode_id="ep-1", agent_id="ag-1",
            include_canvas=True, include_feedback=True)

    def test_retrieve_sequential_no_flags(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.get(
            "/api/episodes/retrieve/ep-1?agent_id=ag-1&include_canvas=false&include_feedback=false")
        assert resp.status_code == 200
        ret.retrieve_sequential.assert_awaited_once_with(
            episode_id="ep-1", agent_id="ag-1",
            include_canvas=False, include_feedback=False)

    def test_retrieve_contextual(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_contextual={"ok": 1})
        resp = client.post("/api/episodes/retrieve/contextual", json={
            "agent_id": "ag-1", "current_task": "invoice", "limit": 3})
        assert resp.status_code == 200
        ret.retrieve_contextual.assert_awaited_once_with(
            agent_id="ag-1", current_task="invoice", limit=3)

    def test_retrieve_by_canvas_type(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_by_canvas_type={"items": []})
        resp = client.post("/api/episodes/retrieve/by-canvas-type", json={
            "agent_id": "ag-1", "canvas_type": "sheets", "action": "present",
            "time_range": "30d", "limit": 5})
        assert resp.status_code == 200
        ret.retrieve_by_canvas_type.assert_awaited_once_with(
            agent_id="ag-1", canvas_type="sheets", action="present",
            time_range="30d", limit=5)

    def test_retrieve_canvas_aware(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_canvas_aware={"episodes": []})
        resp = client.post("/api/episodes/retrieve/canvas-aware", json={
            "agent_id": "ag-1", "query": "approval", "canvas_type": "orchestration",
            "canvas_context_detail": "standard", "limit": 5})
        assert resp.status_code == 200
        ret.retrieve_canvas_aware.assert_awaited_once_with(
            agent_id="ag-1", query="approval", canvas_type="orchestration",
            canvas_context_detail="standard", limit=5)

    def test_retrieve_business_data(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_by_business_data={"rows": 2})
        resp = client.post("/api/episodes/retrieve/business-data", json={
            "agent_id": "ag-1", "filters": {"approval_status": "approved"}, "limit": 4})
        assert resp.status_code == 200
        ret.retrieve_by_business_data.assert_awaited_once_with(
            agent_id="ag-1", business_filters={"approval_status": "approved"}, limit=4)

    def test_retrieve_canvas_type_get_with_query(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_canvas_aware={"episodes": []})
        resp = client.get(
            "/api/episodes/retrieve/canvas-type/orchestration"
            "?agent_id=ag-1&query=approval&limit=5&canvas_context_detail=standard")
        assert resp.status_code == 200
        ret.retrieve_canvas_aware.assert_awaited_once_with(
            agent_id="ag-1", query="approval", canvas_type="orchestration",
            canvas_context_detail="standard", limit=5)

    def test_retrieve_canvas_type_get_without_query(self, monkeypatch, user):
        client, _, ret, *_ = _episode_client(monkeypatch, MagicMock(), user,
                                             retrieve_temporal={"episodes": []})
        resp = client.get("/api/episodes/retrieve/canvas-type/sheets?agent_id=ag-1")
        assert resp.status_code == 200
        ret.retrieve_temporal.assert_awaited_once_with(
            agent_id="ag-1", time_range="90d", limit=10)

    def test_retrieve_canvas_type_get_invalid_detail_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.get(
            "/api/episodes/retrieve/canvas-type/sheets?agent_id=ag-1&canvas_context_detail=bogus")
        assert resp.status_code == 422

    def test_retrieval_unauthenticated(self):
        client = _client(episode_router)
        assert client.post("/api/episodes/retrieve/temporal", json={
            "agent_id": "a", "time_range": "7d"}).status_code == 401
        assert client.get("/api/episodes/retrieve/ep-1?agent_id=a").status_code == 401


class TestEpisodeListAndFeedback:
    def test_list_episodes(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.all.return_value = [_ep("e1", task_description=None, started_at=None)]
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/ag-1/list?skip=0&limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["metadata"]["count"] == 1
        item = body["data"][0]
        assert item["title"] == "Episode"  # task_description None fallback
        assert item["started_at"] is None

    def test_submit_feedback(self, monkeypatch, user):
        client, _, _, life, _ = _episode_client(
            monkeypatch, MagicMock(), user, update_importance_scores=True)
        resp = client.post("/api/episodes/ep-1/feedback", json={
            "feedback_score": 0.8})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["updated"] is True
        life.update_importance_scores.assert_awaited_once_with("ep-1", 0.8)

    def test_submit_feedback_score_out_of_range_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        assert client.post("/api/episodes/ep-1/feedback", json={
            "feedback_score": 5.0}).status_code == 422

    def test_list_canvas_types(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.get("/api/episodes/canvas-types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "sheets" in body["data"]["canvas_types"]
        assert "full" in body["data"]["detail_levels"]


class TestEpisodeFeedbackSubmit:
    def _feedback_client(self, monkeypatch, db, user, episode):
        client, *_ = _episode_client(monkeypatch, db, user)
        q = _chain(db)
        q.first.return_value = episode
        return client

    def test_feedback_thumbs_up(self, monkeypatch, user):
        from api import episode_routes as er

        db = MagicMock()
        ep = _ep("ep-1", feedback_ids=None)
        client = self._feedback_client(monkeypatch, db, user, ep)
        with patch.object(er, "AgentFeedback", MagicMock()) as af:
            fb = MagicMock()
            fb.id = "fb-1"
            fb.feedback_type = "thumbs_up"
            fb.thumbs_up_down = True
            fb.rating = None
            af.return_value = fb
            db.query.return_value.filter.return_value.all.return_value = [fb]
            resp = client.post("/api/episodes/ep-1/feedback/submit", json={
                "feedback_type": "thumbs_up"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["feedback_id"] == "fb-1"
        ctor_kw = af.call_args.kwargs
        assert ctor_kw["thumbs_up_down"] is True
        assert ctor_kw["original_output"] == "Task"
        # aggregate: thumbs_up -> 1.0
        assert body["data"]["aggregate_score"] == 1.0
        assert ep.feedback_ids == ["fb-1"]

    def test_feedback_thumbs_down_rating_and_mixed(self, monkeypatch, user):
        from api import episode_routes as er

        db = MagicMock()
        ep = _ep("ep-2", feedback_ids=["old-1"])
        client = self._feedback_client(monkeypatch, db, user, ep)
        with patch.object(er, "AgentFeedback", MagicMock()) as af:
            fb = MagicMock()
            fb.id = "fb-2"
            fb.feedback_type = "thumbs_down"
            fb.thumbs_up_down = False
            fb.rating = None
            af.return_value = fb
            # pre-existing feedback rows exercise the score mapping branches
            existing = [
                SimpleNamespace(id="f1", feedback_type="thumbs_up", thumbs_up_down=None, rating=None),
                SimpleNamespace(id="f2", feedback_type="thumbs_down", thumbs_up_down=None, rating=None),
                SimpleNamespace(id="f3", feedback_type="rating", thumbs_up_down=None, rating=5),
                SimpleNamespace(id="f4", feedback_type="rating", thumbs_up_down=None, rating=2),
                SimpleNamespace(id="f5", feedback_type="other", thumbs_up_down=None, rating=None),
            ]
            db.query.return_value.filter.return_value.all.return_value = [fb] + existing
            resp = client.post("/api/episodes/ep-2/feedback/submit", json={
                "feedback_type": "thumbs_down"})
        assert resp.status_code == 200
        # -1.0 + 1.0 + -1.0 + 1.0 + -0.5 = -0.5 / 5
        assert resp.json()["data"]["aggregate_score"] == pytest.approx(-0.1)

    def test_feedback_episode_not_found_404(self, monkeypatch, user):
        db = MagicMock()
        _chain(db)
        db.query.return_value.filter.return_value.first.return_value = None
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.post("/api/episodes/nope/feedback/submit", json={
            "feedback_type": "rating", "rating": 5})
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "EPISODE_NOT_FOUND"

    def test_feedback_invalid_type_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.post("/api/episodes/ep-1/feedback/submit", json={})
        assert resp.status_code == 422

    def test_feedback_list(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = _ep("ep-1", feedback_ids=["f1", "f2"])
        q.all.return_value = [
            SimpleNamespace(id="f1", feedback_type="rating", rating=5,
                            user_correction="good", created_at=datetime(2026, 1, 1)),
            SimpleNamespace(id="f2", feedback_type="thumbs_up", rating=None,
                            user_correction=None, created_at=None),
        ]
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/ep-1/feedback/list")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["count"] == 2
        assert body["data"]["feedbacks"][1]["created_at"] is None

    def test_feedback_list_episode_not_found_404(self, monkeypatch, user):
        db = MagicMock()
        _chain(db)
        db.query.return_value.filter.return_value.first.return_value = None
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/nope/feedback/list")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "EPISODE_NOT_FOUND"

    def test_feedback_list_no_linked_feedback(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = _ep("ep-1", feedback_ids=None)
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/ep-1/feedback/list")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"feedbacks": [], "count": 0}


class TestEpisodeAnalyticsAndGraduation:
    def test_feedback_weighted_episodes(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.all.return_value = [_ep("e1"), _ep("e2", started_at=None)]
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get(
            "/api/episodes/analytics/feedback-episodes?agent_id=ag-1&min_feedback_score=0.5&time_range=90d&limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["count"] == 2
        assert body["data"]["episodes"][1]["started_at"] is None

    def test_feedback_weighted_default_time_range(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.all.return_value = []
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/analytics/feedback-episodes?agent_id=ag-1")
        assert resp.status_code == 200
        assert resp.json()["data"]["count"] == 0

    def test_graduation_readiness(self, monkeypatch, user):
        client, _, _, _, grad = _episode_client(
            monkeypatch, MagicMock(), user, readiness={"score": 0.9})
        resp = client.get("/api/episodes/graduation/readiness/ag-1?target_maturity=AUTONOMOUS")
        assert resp.status_code == 200
        grad.calculate_readiness_score.assert_awaited_once_with("ag-1", "AUTONOMOUS")

    def test_graduation_exam(self, monkeypatch, user):
        client, _, _, _, grad = _episode_client(
            monkeypatch, MagicMock(), user, exam={"passed": True})
        # agent_id is a plain str arg -> query; edge_case_episodes (List[str])
        # has no default -> the raw JSON list IS the request body.
        resp = client.post("/api/episodes/graduation/exam?agent_id=ag-1",
                           json=["e1", "e2"])
        assert resp.status_code == 200
        grad.run_graduation_exam.assert_awaited_once_with("ag-1", ["e1", "e2"])

    def test_graduation_exam_missing_fields_422(self, monkeypatch, user):
        client, *_ = _episode_client(monkeypatch, MagicMock(), user)
        resp = client.post("/api/episodes/graduation/exam")
        assert resp.status_code == 422

    def test_graduation_promote_success(self, monkeypatch, user):
        client, _, _, _, grad = _episode_client(
            monkeypatch, MagicMock(), user, promote=True)
        # agent_id + new_maturity are plain args -> QUERY params
        resp = client.post(
            "/api/episodes/graduation/promote?agent_id=ag-1&new_maturity=AUTONOMOUS")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["promoted"] is True
        assert body["message"] == "Agent promoted to AUTONOMOUS"
        grad.promote_agent.assert_awaited_once_with("ag-1", "AUTONOMOUS", "user-w80b")

    def test_graduation_promote_failure(self, monkeypatch, user):
        client, _, _, _, grad = _episode_client(
            monkeypatch, MagicMock(), user, promote=False)
        resp = client.post(
            "/api/episodes/graduation/promote?agent_id=ag-1&new_maturity=INTERN")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Promotion failed"

    def test_graduation_audit_trail(self, monkeypatch, user):
        client, _, _, _, grad = _episode_client(
            monkeypatch, MagicMock(), user, audit_trail={"events": []})
        resp = client.get("/api/episodes/graduation/audit/ag-1")
        assert resp.status_code == 200
        grad.get_graduation_audit_trail.assert_awaited_once_with("ag-1")

    def test_lifecycle_decay(self, monkeypatch, user):
        client, _, _, life, _ = _episode_client(
            monkeypatch, MagicMock(), user, decay={"decayed": 3})
        resp = client.post("/api/episodes/lifecycle/decay?days_threshold=45")
        assert resp.status_code == 200
        life.decay_old_episodes.assert_awaited_once_with(45)

    def test_lifecycle_consolidate(self, monkeypatch, user):
        client, _, _, life, _ = _episode_client(
            monkeypatch, MagicMock(), user, consolidate={"merged": 2})
        resp = client.post("/api/episodes/lifecycle/consolidate?agent_id=ag-1")
        assert resp.status_code == 200
        life.consolidate_similar_episodes.assert_awaited_once_with("ag-1")

    def test_stats(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace(
            total=5, avg_importance=0.6, avg_constitutional=0.7,
            total_interventions=2)
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/stats/ag-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total_episodes"] == 5
        assert body["data"]["avg_importance_score"] == 0.6

    def test_stats_none_values(self, monkeypatch, user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace(
            total=0, avg_importance=None, avg_constitutional=None,
            total_interventions=None)
        client, *_ = _episode_client(monkeypatch, db, user)
        resp = client.get("/api/episodes/stats/ag-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total_episodes"] == 0
        assert body["data"]["avg_importance_score"] == 0.0

    def test_graduation_and_stats_unauthenticated(self):
        client = _client(episode_router)
        assert client.get("/api/episodes/graduation/readiness/a").status_code == 401
        assert client.post("/api/episodes/graduation/promote", json={
            "agent_id": "a", "new_maturity": "INTERN"}).status_code == 401
        assert client.post("/api/episodes/lifecycle/decay").status_code == 401


# ============================================================================
# 4. api/stage_router_routes.py
# ============================================================================
class TestStageRouterStatus:
    def test_status_public_success(self):
        with patch("core.llm.stage_router.stage_router_status",
                   return_value={"phase": "shadow"}):
            resp = _client(stage_router_router).get("/api/v1/llm/stage-router/status")
        assert resp.status_code == 200
        assert resp.json() == {"phase": "shadow"}

    def test_status_error_degraded(self):
        with patch("core.llm.stage_router.stage_router_status",
                   side_effect=RuntimeError("boom")):
            resp = _client(stage_router_router).get("/api/v1/llm/stage-router/status")
        assert resp.status_code == 200
        assert resp.json() == {"phase": "error", "error": "internal"}


def _stage_client(user):
    return _client(stage_router_router, user=user)


class TestStageRouterAutomationRead:
    def test_automation_requires_auth(self):
        assert _client(stage_router_router).get(
            "/api/v1/llm/stage-router/automation").status_code == 401

    def test_automation_requires_admin(self):
        u = MagicMock()
        u.role = UserRole.MEMBER.value
        assert _stage_client(u).get(
            "/api/v1/llm/stage-router/automation").status_code == 403

    def test_automation_success(self, user):
        user.role = UserRole.ADMIN.value
        with patch("core.llm.stage_router_automation.get_automation_status",
                   return_value={"mode": "approve", "pending": []}):
            resp = _stage_client(user).get("/api/v1/llm/stage-router/automation")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "approve"

    def test_automation_service_failure_500(self, user):
        user.role = UserRole.ADMIN.value
        with patch("core.llm.stage_router_automation.get_automation_status",
                   side_effect=RuntimeError("boom")):
            resp = _stage_client(user).get("/api/v1/llm/stage-router/automation")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Automation status unavailable"


class TestStageRouterConfig:
    def test_config_requires_auth(self):
        assert _client(stage_router_router).post(
            "/api/v1/llm/stage-router/automation/config", json={}).status_code == 401

    def test_config_requires_admin(self):
        u = MagicMock()
        u.role = UserRole.MEMBER.value
        assert _stage_client(u).post(
            "/api/v1/llm/stage-router/automation/config", json={}).status_code == 403

    def test_config_success(self, user):
        user.role = UserRole.OWNER.value
        with patch("core.llm.stage_router_automation.set_automation_config",
                   return_value={"mode": "auto"}) as set_cfg:
            resp = _stage_client(user).post(
                "/api/v1/llm/stage-router/automation/config",
                json={"mode": "auto", "interval_min": 30})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "auto"
        set_cfg.assert_called_once_with(mode="auto", interval_min=30)

    def test_config_partial_payload(self, user):
        user.role = UserRole.WORKSPACE_ADMIN.value
        with patch("core.llm.stage_router_automation.set_automation_config",
                   return_value={}) as set_cfg:
            resp = _stage_client(user).post(
                "/api/v1/llm/stage-router/automation/config", json={})
        assert resp.status_code == 200
        set_cfg.assert_called_once_with(mode=None, interval_min=None)

    def test_config_service_failure_500(self, user):
        user.role = UserRole.SUPER_ADMIN.value
        with patch("core.llm.stage_router_automation.set_automation_config",
                   side_effect=RuntimeError("boom")):
            resp = _stage_client(user).post(
                "/api/v1/llm/stage-router/automation/config", json={"mode": "auto"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Automation config update failed"


class TestStageRouterRunNow:
    def test_run_now_requires_auth(self):
        assert _client(stage_router_router).post(
            "/api/v1/llm/stage-router/automation/run-now").status_code == 401

    def test_run_now_requires_admin(self):
        u = MagicMock()
        u.role = UserRole.MEMBER.value
        assert _stage_client(u).post(
            "/api/v1/llm/stage-router/automation/run-now").status_code == 403

    def test_run_now_success(self, user):
        user.role = UserRole.ADMIN.value
        with patch("core.llm.stage_router_automation.run_auto_certification",
                   return_value={"ran": True}):
            resp = _stage_client(user).post("/api/v1/llm/stage-router/automation/run-now")
        assert resp.status_code == 200
        assert resp.json()["ran"] is True

    def test_run_now_service_failure_500(self, user):
        user.role = UserRole.ADMIN.value
        with patch("core.llm.stage_router_automation.run_auto_certification",
                   side_effect=RuntimeError("boom")):
            resp = _stage_client(user).post("/api/v1/llm/stage-router/automation/run-now")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Automation run failed"


class TestStageRouterApprove:
    def test_approve_requires_auth(self):
        assert _client(stage_router_router).post(
            "/api/v1/llm/stage-router/automation/approve",
            json={"agent_id": "a"}).status_code == 401

    def test_approve_requires_admin(self):
        u = MagicMock()
        u.role = UserRole.MEMBER.value
        assert _stage_client(u).post(
            "/api/v1/llm/stage-router/automation/approve",
            json={"agent_id": "a"}).status_code == 403

    def test_approve_missing_agent_id_422(self, user):
        user.role = UserRole.ADMIN.value
        resp = _stage_client(user).post("/api/v1/llm/stage-router/automation/approve", json={})
        assert resp.status_code == 422
        assert resp.json()["detail"] == "agent_id is required"

    def test_approve_success(self, user):
        user.role = UserRole.ADMIN.value
        db = MagicMock()
        with patch("core.llm.stage_router_automation.apply_pending_decision",
                   return_value={"applied": True, "agent_id": "a"}) as apd:
            resp = _stage_client(user, ) if False else _client(
                stage_router_router, user=user, db=db).post(
                "/api/v1/llm/stage-router/automation/approve", json={"agent_id": "a"})
        assert resp.status_code == 200
        assert resp.json()["applied"] is True
        apd.assert_called_once_with(db, "a", approve=True)
        db.commit.assert_called_once()

    def test_approve_not_applied_404(self, user):
        user.role = UserRole.ADMIN.value
        db = MagicMock()
        with patch("core.llm.stage_router_automation.apply_pending_decision",
                   return_value={"applied": False, "reason": "no pending"}):
            resp = _client(stage_router_router, user=user, db=db).post(
                "/api/v1/llm/stage-router/automation/approve", json={"agent_id": "a"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no pending"

    def test_approve_service_failure_500(self, user):
        user.role = UserRole.ADMIN.value
        db = MagicMock()
        with patch("core.llm.stage_router_automation.apply_pending_decision",
                   side_effect=RuntimeError("boom")):
            resp = _client(stage_router_router, user=user, db=db).post(
                "/api/v1/llm/stage-router/automation/approve", json={"agent_id": "a"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Approval failed"


class TestStageRouterReject:
    def test_reject_requires_auth(self):
        assert _client(stage_router_router).post(
            "/api/v1/llm/stage-router/automation/reject",
            json={"agent_id": "a"}).status_code == 401

    def test_reject_requires_admin(self):
        u = MagicMock()
        u.role = UserRole.MEMBER.value
        assert _stage_client(u).post(
            "/api/v1/llm/stage-router/automation/reject",
            json={"agent_id": "a"}).status_code == 403

    def test_reject_missing_agent_id_422(self, user):
        user.role = UserRole.ADMIN.value
        resp = _stage_client(user).post("/api/v1/llm/stage-router/automation/reject", json={})
        assert resp.status_code == 422

    def test_reject_success(self, user):
        user.role = UserRole.ADMIN.value
        db = MagicMock()
        with patch("core.llm.stage_router_automation.apply_pending_decision",
                   return_value={"applied": False, "agent_id": "a"}) as apd:
            resp = _client(stage_router_router, user=user, db=db).post(
                "/api/v1/llm/stage-router/automation/reject", json={"agent_id": "a"})
        assert resp.status_code == 200
        apd.assert_called_once_with(db, "a", approve=False)
        db.commit.assert_called_once()

    def test_reject_already_applied_409(self, user):
        user.role = UserRole.ADMIN.value
        db = MagicMock()
        with patch("core.llm.stage_router_automation.apply_pending_decision",
                   return_value={"applied": True}):
            resp = _client(stage_router_router, user=user, db=db).post(
                "/api/v1/llm/stage-router/automation/reject", json={"agent_id": "a"})
        assert resp.status_code == 409
        assert resp.json()["detail"] == "No pending approval to reject"

    def test_reject_service_failure_500(self, user):
        user.role = UserRole.ADMIN.value
        db = MagicMock()
        with patch("core.llm.stage_router_automation.apply_pending_decision",
                   side_effect=RuntimeError("boom")):
            resp = _client(stage_router_router, user=user, db=db).post(
                "/api/v1/llm/stage-router/automation/reject", json={"agent_id": "a"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Rejection failed"


class TestStageRouterRequireAdmin:
    def test_require_admin_accepts_admin_roles(self):
        from api.stage_router_routes import _require_admin

        for role in ("super_admin", "owner", "admin", "workspace_admin"):
            u = MagicMock()
            u.role = role
            assert _require_admin(u) is u

    def test_require_admin_rejects_member(self):
        from api.stage_router_routes import _require_admin

        u = MagicMock()
        u.role = "member"
        with pytest.raises(HTTPException) as ei:
            _require_admin(u)
        assert ei.value.status_code == 403

    def test_require_admin_missing_role_attr(self):
        from api.stage_router_routes import _require_admin

        u = MagicMock()
        del u.role
        with pytest.raises(HTTPException) as ei:
            _require_admin(u)
        assert ei.value.status_code == 403


# ============================================================================
# 5. api/deeplinks.py — real SQLite for audit/stats; core.deeplinks patched
# ============================================================================
@pytest.fixture
def dl_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _dl_row(db, *, user_id="u1", agent_id=None, resource_type="agent",
            resource_id="r1", action="execute", source="external",
            status="success", created_at=None, **kw):
    row = DeepLinkAudit(
        id=str(uuid.uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        source=source,
        deeplink_url=f"atom://{resource_type}/{resource_id}",
        status=status,
        parameters={"p": 1},
        **kw,
    )
    if created_at is not None:
        row.created_at = created_at
    db.add(row)
    db.commit()
    return row


def _dl_agent(db, agent_id="a1", name="Agent One"):
    from core.models import AgentRegistry

    agent = AgentRegistry(
        id=agent_id, name=name, category="Ops", module_path="ops.x",
        class_name="Y", user_id="u1", tenant_id=None)
    db.add(agent)
    db.commit()
    return agent


class TestDeeplinkExecute:
    def test_execute_success(self, dl_db, user):
        with patch("api.deeplinks.execute_deep_link",
                   new=AsyncMock(return_value={
                       "success": True, "agent_id": "a1", "agent_name": "A",
                       "execution_id": "ex1", "resource_type": "agent",
                       "resource_id": "r1", "action": "run", "source": "mobile"})):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute",
                json={"deeplink_url": "atom://agent/a1", "source": "mobile"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["agent_id"] == "a1"
        assert body["source"] == "mobile"

    def test_execute_disabled_503(self, dl_db, user):
        with patch("api.deeplinks.DEEPLINK_ENABLED", False):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 503
        assert resp.json()["detail"]["error"]["code"] == "SERVICE_UNAVAILABLE"

    def test_execute_result_failure_validation(self, dl_db, user):
        with patch("api.deeplinks.execute_deep_link",
                   new=AsyncMock(return_value={"success": False, "error": "unknown"})):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_execute_parse_exception(self, dl_db, user):
        from core.deeplinks import DeepLinkParseException

        with patch("api.deeplinks.execute_deep_link",
                   new=AsyncMock(side_effect=DeepLinkParseException("bad"))):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 422

    def test_execute_security_exception(self, dl_db, user):
        from core.deeplinks import DeepLinkSecurityException

        with patch("api.deeplinks.execute_deep_link",
                   new=AsyncMock(side_effect=DeepLinkSecurityException("bad"))):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 422

    def test_execute_http_exception_re_raised(self, dl_db, user):
        with patch("api.deeplinks.execute_deep_link",
                   new=AsyncMock(side_effect=HTTPException(418, "teapot"))):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 418

    def test_execute_generic_exception_500(self, dl_db, user):
        with patch("api.deeplinks.execute_deep_link",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 500

    def test_execute_missing_url_422(self, dl_db, user):
        resp = _client(deeplink_router, user=user, db=dl_db).post(
            "/api/deeplinks/execute", json={})
        assert resp.status_code == 422

    def test_execute_unauthenticated(self, dl_db):
        resp = _client(deeplink_router, db=dl_db).post(
            "/api/deeplinks/execute", json={"deeplink_url": "atom://agent/a1"})
        assert resp.status_code == 401


class TestDeeplinkAudit:
    def _audit_client(self, dl_db, user):
        return _client(deeplink_router, user=user, db=dl_db)

    def test_audit_empty(self, dl_db, user):
        resp = self._audit_client(dl_db, user).get("/api/deeplinks/audit")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_audit_scoped_to_current_user(self, dl_db, user):
        _dl_row(dl_db, user_id="user-w80b", agent_id=None)
        _dl_row(dl_db, user_id="other-user")
        resp = self._audit_client(dl_db, user).get("/api/deeplinks/audit")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["user_id"] == "user-w80b"

    def test_audit_cross_user_id_ignored(self, dl_db, user):
        _dl_row(dl_db, user_id="user-w80b")
        resp = self._audit_client(dl_db, user).get(
            "/api/deeplinks/audit?user_id=somebody-else")
        assert resp.status_code == 200
        assert all(r["user_id"] == "user-w80b" for r in resp.json())

    def test_audit_filters_agent_and_resource(self, dl_db, user):
        _dl_agent(dl_db, "a1")
        _dl_row(dl_db, user_id="user-w80b", agent_id="a1", resource_type="agent")
        _dl_row(dl_db, user_id="user-w80b", agent_id=None, resource_type="canvas")
        resp = self._audit_client(dl_db, user).get(
            "/api/deeplinks/audit?agent_id=a1&resource_type=agent")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["agent_id"] == "a1"

    def test_audit_pagination_and_order(self, dl_db, user):
        old = datetime(2026, 1, 1)
        new = datetime(2026, 2, 1)
        _dl_row(dl_db, user_id="user-w80b", resource_id="old", created_at=old)
        _dl_row(dl_db, user_id="user-w80b", resource_id="new", created_at=new)
        resp = self._audit_client(dl_db, user).get(
            "/api/deeplinks/audit?limit=1&offset=0")
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["resource_id"] == "new"  # most recent first

    def test_audit_limit_bounds_422(self, dl_db, user):
        client = self._audit_client(dl_db, user)
        assert client.get("/api/deeplinks/audit?limit=0").status_code == 422
        assert client.get("/api/deeplinks/audit?limit=1001").status_code == 422
        assert client.get("/api/deeplinks/audit?offset=-1").status_code == 422

    def test_audit_unauthenticated(self, dl_db):
        assert _client(deeplink_router, db=dl_db).get(
            "/api/deeplinks/audit").status_code == 401


class TestDeeplinkGenerate:
    def test_generate_success(self, dl_db, user):
        with patch("api.deeplinks.generate_deep_link",
                   return_value="atom://agent/a1?x=1"):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/generate",
                json={"resource_type": "agent", "resource_id": "a1",
                      "parameters": {"x": 1}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["deeplink_url"] == "atom://agent/a1?x=1"
        assert body["resource_type"] == "agent"

    def test_generate_default_parameters(self, dl_db, user):
        with patch("api.deeplinks.generate_deep_link", return_value="atom://canvas/c1"):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/generate",
                json={"resource_type": "canvas", "resource_id": "c1"})
        assert resp.status_code == 200
        assert resp.json()["parameters"] == {}

    def test_generate_invalid_resource_type_422(self, dl_db, user):
        resp = _client(deeplink_router, user=user, db=dl_db).post(
            "/api/deeplinks/generate",
            json={"resource_type": "bogus", "resource_id": "x"})
        assert resp.status_code == 422
        body = resp.json()["detail"]["error"]
        assert body["code"] == "VALIDATION_ERROR"
        assert body["details"]["provided"] == "bogus"

    def test_generate_disabled_503(self, dl_db, user):
        with patch("api.deeplinks.DEEPLINK_ENABLED", False):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/generate",
                json={"resource_type": "agent", "resource_id": "a1"})
        assert resp.status_code == 503

    def test_generate_value_error_422(self, dl_db, user):
        with patch("api.deeplinks.generate_deep_link",
                   side_effect=ValueError("bad param")):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/generate",
                json={"resource_type": "tool", "resource_id": "t1"})
        assert resp.status_code == 422

    def test_generate_generic_exception_500(self, dl_db, user):
        with patch("api.deeplinks.generate_deep_link",
                   side_effect=RuntimeError("boom")):
            resp = _client(deeplink_router, user=user, db=dl_db).post(
                "/api/deeplinks/generate",
                json={"resource_type": "workflow", "resource_id": "w1"})
        assert resp.status_code == 500

    def test_generate_missing_resource_422(self, dl_db, user):
        resp = _client(deeplink_router, user=user, db=dl_db).post(
            "/api/deeplinks/generate", json={"resource_type": "agent"})
        assert resp.status_code == 422

    def test_generate_unauthenticated(self, dl_db):
        resp = _client(deeplink_router, db=dl_db).post(
            "/api/deeplinks/generate",
            json={"resource_type": "agent", "resource_id": "a1"})
        assert resp.status_code == 401


class TestDeeplinkStats:
    def _stats_client(self, dl_db, user):
        return _client(deeplink_router, user=user, db=dl_db)

    def test_stats_empty(self, dl_db, user):
        resp = self._stats_client(dl_db, user).get("/api/deeplinks/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_executions"] == 0
        assert body["by_resource_type"] == {
            "agent": 0, "workflow": 0, "canvas": 0, "tool": 0}
        assert body["top_agents"] == []

    def test_stats_user_scoped(self, dl_db, user):
        _dl_row(dl_db, user_id="user-w80b", status="success")
        _dl_row(dl_db, user_id="user-w80b", status="failed")
        _dl_row(dl_db, user_id="other", status="success")
        resp = self._stats_client(dl_db, user).get("/api/deeplinks/stats")
        body = resp.json()
        assert body["total_executions"] == 2
        assert body["successful_executions"] == 1
        assert body["failed_executions"] == 1
        assert body["by_resource_type"]["agent"] == 2

    def test_stats_admin_sees_all(self, dl_db, user):
        user.role = UserRole.ADMIN.value
        _dl_row(dl_db, user_id="user-w80b", status="success")
        _dl_row(dl_db, user_id="other", status="success")
        resp = self._stats_client(dl_db, user).get("/api/deeplinks/stats")
        assert resp.json()["total_executions"] == 2

    def test_stats_sources_and_top_agents(self, dl_db, user):
        _dl_agent(dl_db, "a1", "Alpha")
        _dl_agent(dl_db, "a2", "Beta")
        now = datetime.now()
        _dl_row(dl_db, user_id="user-w80b", agent_id="a1", source="mobile",
                created_at=now)
        _dl_row(dl_db, user_id="user-w80b", agent_id="a1", source="mobile",
                created_at=now - timedelta(hours=1))
        _dl_row(dl_db, user_id="user-w80b", agent_id="a2", source="web",
                created_at=now - timedelta(days=2))
        resp = self._stats_client(dl_db, user).get("/api/deeplinks/stats")
        body = resp.json()
        assert body["by_source"]["mobile"] == 2
        assert body["by_source"]["web"] == 1
        assert body["last_24h_executions"] == 2
        assert body["last_7d_executions"] == 3
        agents = {a["agent_id"]: a["execution_count"] for a in body["top_agents"]}
        assert agents["a1"] == 2
        assert agents["a2"] == 1

    def test_stats_unauthenticated(self, dl_db):
        assert _client(deeplink_router, db=dl_db).get(
            "/api/deeplinks/stats").status_code == 401


class TestDeeplinkHelpers:
    def test_is_admin_user_string_and_enum_roles(self):
        from api.deeplinks import _is_admin_user

        for role in ("admin", "workspace_admin", "owner", "super_admin"):
            u = MagicMock()
            u.role = role
            assert _is_admin_user(u) is True
        u = MagicMock()
        u.role = "member"
        assert _is_admin_user(u) is False
        # UserRole enum instance (not string)
        u = MagicMock()
        u.role = UserRole.ADMIN
        assert _is_admin_user(u) is True
        u = MagicMock()
        u.role = UserRole.MEMBER
        assert _is_admin_user(u) is False
        # missing role attribute
        u = MagicMock()
        del u.role
        assert _is_admin_user(u) is False


# ============================================================================
# 6. api/workflow_debugging.py — WorkflowDebugger class patched
# ============================================================================
def _wf_client(monkeypatch, db, debugger):
    from api import workflow_debugging as wd

    monkeypatch.setattr(wd, "WorkflowDebugger", MagicMock(return_value=debugger))
    return _client(wf_debug_router, user=MagicMock(id="u-wf"), db=db)


def _wf_debugger():
    return MagicMock()


def _wf_session(session_id="s1", **kw):
    return SimpleNamespace(
        id=session_id,
        workflow_id=kw.get("workflow_id", "wf-1"),
        execution_id=kw.get("execution_id", "ex-1"),
        user_id=kw.get("user_id", "u-wf"),
        session_name=kw.get("session_name", "Debug"),
        status=kw.get("status", "active"),
        current_step=kw.get("current_step", 0),
        current_node_id=kw.get("current_node_id", "n1"),
        created_at=kw.get("created_at", datetime(2026, 1, 1)),
        updated_at=kw.get("updated_at", datetime(2026, 1, 1)),
    )


class TestWfDebugSessions:
    def test_create_session_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_debug_session.return_value = _wf_session()
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/sessions", json={
            "workflow_id": "wf-1", "execution_id": "ex-1", "session_name": "S",
            "stop_on_entry": True, "stop_on_exceptions": False, "stop_on_error": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "s1"
        assert body["workflow_id"] == "wf-1"
        assert body["created_at"] is not None
        call = d.create_debug_session.call_args
        assert call.kwargs["workflow_id"] == "wf-1"
        assert call.kwargs["user_id"] == "u-wf"
        assert call.kwargs["stop_on_entry"] is True

    def test_create_session_defaults(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_debug_session.return_value = _wf_session()
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/sessions", json={"workflow_id": "wf-1"})
        assert resp.status_code == 200
        call = d.create_debug_session.call_args.kwargs
        assert call["execution_id"] is None
        assert call["session_name"] is None
        assert call["stop_on_entry"] is False

    def test_create_session_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_debug_session.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/sessions", json={"workflow_id": "wf-1"})
        assert resp.status_code == 500

    def test_create_session_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_debug_session.side_effect = HTTPException(404, "no workflow")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/sessions", json={"workflow_id": "wf-1"})
        assert resp.status_code == 404

    def test_create_session_missing_workflow_422(self, monkeypatch, user):
        client = _wf_client(monkeypatch, MagicMock(), _wf_debugger())
        assert client.post("/api/workflows/wf-1/debug/sessions", json={}).status_code == 422

    def test_list_sessions_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_active_debug_sessions.return_value = [
            _wf_session("s1", updated_at=None), _wf_session("s2")]
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/wf-1/debug/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["updated_at"] is None
        d.get_active_debug_sessions.assert_called_once_with("wf-1", "u-wf")

    def test_list_sessions_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_active_debug_sessions.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.get("/api/workflows/wf-1/debug/sessions").status_code == 500

    def test_sessions_unauthenticated(self):
        client = _client(wf_debug_router)
        assert client.post("/api/workflows/wf-1/debug/sessions",
                           json={"workflow_id": "wf-1"}).status_code == 401
        assert client.get("/api/workflows/wf-1/debug/sessions").status_code == 401

    def test_pause_session_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.pause_debug_session.return_value = True
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/sessions/s1/pause")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Debug session paused"

    def test_pause_session_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.pause_debug_session.return_value = False
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/sessions/nope/pause")
        assert resp.status_code == 404

    def test_pause_session_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.pause_debug_session.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/s1/pause").status_code == 500

    def test_resume_session_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.resume_debug_session.return_value = True
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/sessions/s1/resume")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Debug session resumed"

    def test_resume_session_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.resume_debug_session.return_value = False
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/nope/resume").status_code == 404

    def test_resume_session_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.resume_debug_session.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/s1/resume").status_code == 500

    def test_complete_session_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_debug_session.return_value = True
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/sessions/s1/complete")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Debug session completed"

    def test_complete_session_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_debug_session.return_value = False
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/nope/complete").status_code == 404

    def test_complete_session_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_debug_session.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/s1/complete").status_code == 500

    def test_pause_resume_complete_unauthenticated(self):
        client = _client(wf_debug_router)
        assert client.post("/api/workflows/debug/sessions/s1/pause").status_code == 401
        assert client.post("/api/workflows/debug/sessions/s1/resume").status_code == 401
        assert client.post("/api/workflows/debug/sessions/s1/complete").status_code == 401


class TestWfBreakpoints:
    def _bp(self, bp_id="bp1", **kw):
        return SimpleNamespace(
            id=bp_id,
            workflow_id=kw.get("workflow_id", "wf-1"),
            debug_session_id=kw.get("debug_session_id", None),
            node_id=kw.get("node_id", "n1"),
            edge_id=kw.get("edge_id", None),
            breakpoint_type=kw.get("breakpoint_type", "node"),
            condition=kw.get("condition", None),
            hit_limit=kw.get("hit_limit", None),
            hit_count=kw.get("hit_count", 0),
            log_message=kw.get("log_message", None),
            is_active=kw.get("is_active", True),
            is_disabled=kw.get("is_disabled", False),
            created_by=kw.get("created_by", "u-wf"),
            created_at=kw.get("created_at", datetime(2026, 1, 1)),
        )

    def test_add_breakpoint_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.add_breakpoint.return_value = self._bp(breakpoint_type="edge")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "workflow_id": "wf-1", "node_id": "n1", "debug_session_id": "s1",
            "edge_id": "e1", "breakpoint_type": "edge", "condition": "x>1",
            "hit_limit": 3, "log_message": "hit"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["breakpoint_id"] == "bp1"
        assert body["breakpoint_type"] == "edge"
        call = d.add_breakpoint.call_args.kwargs
        assert call["workflow_id"] == "wf-1"
        assert call["user_id"] == "u-wf"
        assert call["hit_limit"] == 3

    def test_add_breakpoint_defaults(self, monkeypatch, user):
        d = _wf_debugger()
        d.add_breakpoint.return_value = self._bp()
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "workflow_id": "wf-1", "node_id": "n1"})
        assert resp.status_code == 200
        call = d.add_breakpoint.call_args.kwargs
        assert call["breakpoint_type"] == "node"
        assert call["debug_session_id"] is None

    def test_add_breakpoint_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.add_breakpoint.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "workflow_id": "wf-1", "node_id": "n1"})
        assert resp.status_code == 500

    def test_add_breakpoint_missing_node_422(self, monkeypatch, user):
        client = _wf_client(monkeypatch, MagicMock(), _wf_debugger())
        assert client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "workflow_id": "wf-1"}).status_code == 422

    def test_get_breakpoints_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_breakpoints.return_value = [self._bp("b1")]
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/wf-1/debug/breakpoints?active_only=false")
        assert resp.status_code == 200
        assert resp.json()[0]["breakpoint_id"] == "b1"
        d.get_breakpoints.assert_called_once_with("wf-1", "u-wf", False)

    def test_get_breakpoints_default_active_only(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_breakpoints.return_value = []
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/wf-1/debug/breakpoints")
        assert resp.status_code == 200
        d.get_breakpoints.assert_called_once_with("wf-1", "u-wf", True)

    def test_get_breakpoints_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_breakpoints.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.get("/api/workflows/wf-1/debug/breakpoints").status_code == 500

    def test_remove_breakpoint_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.remove_breakpoint.return_value = True
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.delete("/api/workflows/debug/breakpoints/bp1")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Breakpoint removed"
        d.remove_breakpoint.assert_called_once_with("bp1", "u-wf")

    def test_remove_breakpoint_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.remove_breakpoint.return_value = False
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.delete("/api/workflows/debug/breakpoints/nope").status_code == 404

    def test_remove_breakpoint_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.remove_breakpoint.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.delete("/api/workflows/debug/breakpoints/bp1").status_code == 500

    def test_toggle_breakpoint_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.toggle_breakpoint.return_value = True
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.put("/api/workflows/debug/breakpoints/bp1/toggle")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_disabled"] is False  # not new_state

    def test_toggle_breakpoint_disables(self, monkeypatch, user):
        d = _wf_debugger()
        d.toggle_breakpoint.return_value = False
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.put("/api/workflows/debug/breakpoints/bp1/toggle")
        assert resp.json()["is_disabled"] is True

    def test_toggle_breakpoint_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.toggle_breakpoint.return_value = None
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.put("/api/workflows/debug/breakpoints/nope/toggle").status_code == 404

    def test_toggle_breakpoint_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.toggle_breakpoint.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.put("/api/workflows/debug/breakpoints/bp1/toggle").status_code == 500

    def test_breakpoints_unauthenticated(self):
        client = _client(wf_debug_router)
        assert client.post("/api/workflows/wf-1/debug/breakpoints",
                           json={"workflow_id": "wf-1", "node_id": "n"}).status_code == 401
        assert client.get("/api/workflows/wf-1/debug/breakpoints").status_code == 401
        assert client.delete("/api/workflows/debug/breakpoints/b1").status_code == 401
        assert client.put("/api/workflows/debug/breakpoints/b1/toggle").status_code == 401


class TestWfStepExecution:
    @pytest.mark.parametrize("action,method", [
        ("step_over", "step_over"),
        ("step_into", "step_into"),
        ("step_out", "step_out"),
        ("continue", "continue_execution"),
        ("pause", "pause_execution"),
    ])
    def test_step_actions_success(self, monkeypatch, user, action, method):
        d = _wf_debugger()
        getattr(d, method).return_value = {"message": "stepped"}
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/step",
                           json={"session_id": "s1", "action": action})
        assert resp.status_code == 200
        assert resp.json() == {"message": "stepped"}
        getattr(d, method).assert_called_once_with("s1")

    def test_step_invalid_action_422(self, monkeypatch, user):
        client = _wf_client(monkeypatch, MagicMock(), _wf_debugger())
        resp = client.post("/api/workflows/debug/step",
                           json={"session_id": "s1", "action": "teleport"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error"]["code"] == "VALIDATION_ERROR"

    def test_step_session_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.step_over.return_value = None
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/step",
                           json={"session_id": "nope", "action": "step_over"})
        assert resp.status_code == 404

    def test_step_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.step_over.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/step",
                           json={"session_id": "s1", "action": "step_over"})
        assert resp.status_code == 500

    def test_step_unauthenticated(self):
        assert _client(wf_debug_router).post(
            "/api/workflows/debug/step",
            json={"session_id": "s1", "action": "pause"}).status_code == 401


class TestWfTraces:
    def _trace(self, trace_id="t1", **kw):
        return SimpleNamespace(
            id=trace_id,
            workflow_id=kw.get("workflow_id", "wf-1"),
            execution_id=kw.get("execution_id", "ex-1"),
            debug_session_id=kw.get("debug_session_id", None),
            step_number=kw.get("step_number", 1),
            node_id=kw.get("node_id", "n1"),
            node_type=kw.get("node_type", "action"),
            status=kw.get("status", "completed"),
            input_data=kw.get("input_data", {"i": 1}),
            output_data=kw.get("output_data", None),
            error_message=kw.get("error_message", None),
            variable_changes=kw.get("variable_changes", {}),
            started_at=kw.get("started_at", datetime(2026, 1, 1)),
            completed_at=kw.get("completed_at", datetime(2026, 1, 2)),
            duration_ms=kw.get("duration_ms", 10),
        )

    def test_create_trace_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_trace.return_value = self._trace()
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/traces", json={
            "workflow_id": "wf-1", "execution_id": "ex-1", "step_number": 1,
            "node_id": "n1", "node_type": "action", "input_data": {"i": 1},
            "variables_before": {"v": 2}, "debug_session_id": "s1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["trace_id"] == "t1"
        assert body["status"] == "completed"
        call = d.create_trace.call_args.kwargs
        assert call["workflow_id"] == "wf-1"
        assert call["variables_before"] == {"v": 2}

    def test_create_trace_defaults(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_trace.return_value = self._trace()
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/traces", json={
            "workflow_id": "wf-1", "execution_id": "ex-1", "step_number": 1,
            "node_id": "n1", "node_type": "action"})
        assert resp.status_code == 200
        call = d.create_trace.call_args.kwargs
        assert call["input_data"] is None
        assert call["debug_session_id"] is None

    def test_create_trace_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_trace.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/traces", json={
            "workflow_id": "wf-1", "execution_id": "ex-1", "step_number": 1,
            "node_id": "n1", "node_type": "action"})
        assert resp.status_code == 500

    def test_create_trace_missing_fields_422(self, monkeypatch, user):
        client = _wf_client(monkeypatch, MagicMock(), _wf_debugger())
        assert client.post("/api/workflows/debug/traces", json={
            "workflow_id": "wf-1"}).status_code == 422

    def test_complete_trace_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_trace.return_value = True
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.put("/api/workflows/debug/traces/t1/complete", json={
            "output_data": {"o": 1}, "variables_after": {"v": 3},
            "error_message": None})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Trace completed"
        call = d.complete_trace.call_args.kwargs
        assert call["trace_id"] == "t1"
        assert call["output_data"] == {"o": 1}

    def test_complete_trace_not_found_404(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_trace.return_value = False
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.put("/api/workflows/debug/traces/nope/complete",
                          json={}).status_code == 404

    def test_complete_trace_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_trace.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.put("/api/workflows/debug/traces/t1/complete",
                          json={}).status_code == 500

    def test_get_execution_traces_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_execution_traces.return_value = [
            self._trace("t1", completed_at=None), self._trace("t2")]
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/executions/ex-1/traces?debug_session_id=s1&limit=50")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["completed_at"] is None
        d.get_execution_traces.assert_called_once_with("ex-1", "s1", 50)

    def test_get_execution_traces_defaults(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_execution_traces.return_value = []
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/executions/ex-1/traces")
        assert resp.status_code == 200
        d.get_execution_traces.assert_called_once_with("ex-1", None, 100)

    def test_get_execution_traces_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_execution_traces.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.get("/api/workflows/executions/ex-1/traces").status_code == 500

    def test_traces_unauthenticated(self):
        client = _client(wf_debug_router)
        assert client.post("/api/workflows/debug/traces", json={
            "workflow_id": "w", "execution_id": "e", "step_number": 1,
            "node_id": "n", "node_type": "t"}).status_code == 401
        assert client.put("/api/workflows/debug/traces/t1/complete",
                          json={}).status_code == 401
        assert client.get("/api/workflows/executions/e/traces").status_code == 401


class TestWfVariables:
    def _var(self, vid="v1", **kw):
        return SimpleNamespace(
            id=vid,
            trace_id=kw.get("trace_id", "t1"),
            variable_name=kw.get("variable_name", "x"),
            variable_path=kw.get("variable_path", "$.x"),
            variable_type=kw.get("variable_type", "int"),
            value=kw.get("value", 1),
            value_preview=kw.get("value_preview", "1"),
            is_mutable=kw.get("is_mutable", True),
            scope=kw.get("scope", "local"),
            is_changed=kw.get("is_changed", False),
            previous_value=kw.get("previous_value", None),
            is_watch=kw.get("is_watch", False),
            watch_expression=kw.get("watch_expression", None),
        )

    def test_get_session_variables_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_watch_variables.return_value = [self._var()]
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/debug/sessions/s1/variables")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["variable_name"] == "x"
        assert body[0]["is_watch"] is False
        d.get_watch_variables.assert_called_once_with("s1")

    def test_get_session_variables_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_watch_variables.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.get("/api/workflows/debug/sessions/s1/variables").status_code == 500

    def test_get_trace_variables_success(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_variables_for_trace.return_value = [self._var(vid="v2", is_watch=True)]
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.get("/api/workflows/debug/traces/t1/variables")
        assert resp.status_code == 200
        assert resp.json()[0]["variable_id"] == "v2"
        d.get_variables_for_trace.assert_called_once_with("t1")

    def test_get_trace_variables_service_failure_500(self, monkeypatch, user):
        d = _wf_debugger()
        d.get_variables_for_trace.side_effect = RuntimeError("boom")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.get("/api/workflows/debug/traces/t1/variables").status_code == 500

    def test_variables_unauthenticated(self):
        client = _client(wf_debug_router)
        assert client.get("/api/workflows/debug/sessions/s1/variables").status_code == 401
        assert client.get("/api/workflows/debug/traces/t1/variables").status_code == 401


class TestWfHTTPExceptionPropagation:
    """Every handler's `except HTTPException: raise` guard re-raises
    documented 4xx instead of rewrapping as 500 (R84 pattern)."""

    @pytest.mark.parametrize("http_method,path,method", [
        ("get", "/api/workflows/wf-1/debug/sessions", "get_active_debug_sessions"),
        ("get", "/api/workflows/wf-1/debug/breakpoints", "get_breakpoints"),
        ("put", "/api/workflows/debug/traces/t1/complete", "complete_trace"),
        ("get", "/api/workflows/executions/ex-1/traces", "get_execution_traces"),
        ("get", "/api/workflows/debug/sessions/s1/variables", "get_watch_variables"),
        ("get", "/api/workflows/debug/traces/t1/variables", "get_variables_for_trace"),
    ])
    def test_http_exception_propagates(self, monkeypatch, user, http_method, path, method):
        d = _wf_debugger()
        getattr(d, method).side_effect = HTTPException(422, "bad input")
        client = _wf_client(monkeypatch, MagicMock(), d)
        if http_method == "put":
            resp = client.put(path, json={})
        else:
            resp = client.get(path)
        assert resp.status_code == 422

    def test_add_breakpoint_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.add_breakpoint.side_effect = HTTPException(404, "no workflow")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/wf-1/debug/breakpoints", json={
            "workflow_id": "wf-1", "node_id": "n1"})
        assert resp.status_code == 404

    def test_create_trace_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.create_trace.side_effect = HTTPException(409, "conflict")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/traces", json={
            "workflow_id": "wf-1", "execution_id": "ex-1", "step_number": 1,
            "node_id": "n1", "node_type": "action"})
        assert resp.status_code == 409

    def test_step_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.step_over.side_effect = HTTPException(423, "locked")
        client = _wf_client(monkeypatch, MagicMock(), d)
        resp = client.post("/api/workflows/debug/step",
                           json={"session_id": "s1", "action": "step_over"})
        assert resp.status_code == 423

    def test_pause_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.pause_debug_session.side_effect = HTTPException(400, "nope")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/s1/pause").status_code == 400

    def test_remove_breakpoint_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.remove_breakpoint.side_effect = HTTPException(400, "nope")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.delete("/api/workflows/debug/breakpoints/b1").status_code == 400

    def test_toggle_breakpoint_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.toggle_breakpoint.side_effect = HTTPException(400, "nope")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.put("/api/workflows/debug/breakpoints/b1/toggle").status_code == 400

    def test_resume_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.resume_debug_session.side_effect = HTTPException(400, "nope")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/s1/resume").status_code == 400

    def test_complete_session_http_exception_propagates(self, monkeypatch, user):
        d = _wf_debugger()
        d.complete_debug_session.side_effect = HTTPException(400, "nope")
        client = _wf_client(monkeypatch, MagicMock(), d)
        assert client.post("/api/workflows/debug/sessions/s1/complete").status_code == 400


# ============================================================================
# 7. api/browser_routes.py — playwright mocked, MagicMock db
# ============================================================================
def _browser_client(db=None, user=None):
    from core.security_dependencies import get_current_user as sec_user

    app = FastAPI()
    app.include_router(browser_router)
    if user is not None:
        app.dependency_overrides[sec_user] = lambda: user
    if db is not None:
        def _get_db():
            yield db
        app.dependency_overrides[get_db] = _get_db
        app.db = db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def browser_user():
    u = MagicMock()
    u.id = "browser-user"
    u.role = UserRole.ADMIN.value
    return u


def _gov_allowed(agent_id="ag-1", maturity="AUTONOMOUS"):
    agent = SimpleNamespace(id=agent_id, maturity_level=maturity, status="active")
    check = {"allowed": True, "reason": ""}
    return agent, check


def _gov_denied(agent_id="ag-1"):
    agent = SimpleNamespace(id=agent_id, maturity_level="STUDENT", status="STUDENT")
    check = {"allowed": False, "reason": "maturity too low"}
    return agent, check


def _patch_browser_tools(monkeypatch, **results):
    """Patch the 8 browser functions as bound in api.browser_routes.

    The routes import the functions at module load (`from tools.browser_tool
    import ...`), so patching tools.browser_tool.* does NOT rebind them —
    patch api.browser_routes.<name> directly.
    """
    from api import browser_routes as br

    names = ("browser_click", "browser_close_session", "browser_create_session",
             "browser_execute_script", "browser_extract_text", "browser_fill_form",
             "browser_get_page_info", "browser_navigate", "browser_screenshot")
    mocks = {}
    for n in names:
        m = AsyncMock(return_value=results.get(n, {"success": True}))
        monkeypatch.setattr(br, n, m)
        mocks[n] = m
    return mocks


class TestBrowserGovernanceHelper:
    def test_check_governance_skipped_without_agent(self):
        from api.browser_routes import _check_browser_governance

        db = MagicMock()
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True):
            agent, check = asyncio.run(_check_browser_governance(
                db, agent_id="", user_id="u", action_type="browser_click"))
        assert agent is None and check is None

    def test_check_governance_skipped_when_flag_off(self):
        from api.browser_routes import _check_browser_governance

        db = MagicMock()
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=False):
            agent, check = asyncio.run(_check_browser_governance(
                db, agent_id="ag-1", user_id="u", action_type="browser_click"))
        assert agent is None and check is None

    def test_check_governance_allowed(self, browser_user):
        from api.browser_routes import _check_browser_governance

        db = MagicMock()
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            got_agent, got_check = asyncio.run(_check_browser_governance(
                db, agent_id="ag-1", user_id="u", action_type="browser_click"))
        assert got_agent is agent
        assert got_check["allowed"] is True

    def test_check_governance_denied_raises_403(self):
        from api.browser_routes import _check_browser_governance

        db = MagicMock()
        agent, check = _gov_denied()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            with pytest.raises(HTTPException) as ei:
                asyncio.run(_check_browser_governance(
                    db, agent_id="ag-1", user_id="u", action_type="browser_click"))
        assert ei.value.status_code == 403

    def test_check_governance_agent_not_found(self):
        from api.browser_routes import _check_browser_governance

        db = MagicMock()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(None, None))
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory"):
            agent, check = asyncio.run(_check_browser_governance(
                db, agent_id="ag-1", user_id="u", action_type="browser_click"))
        assert agent is None and check is None

    def test_check_governance_resolver_exception_swallowed(self):
        from api.browser_routes import _check_browser_governance

        db = MagicMock()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(
            side_effect=RuntimeError("resolver boom"))
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory"):
            agent, check = asyncio.run(_check_browser_governance(
                db, agent_id="ag-1", user_id="u", action_type="browser_click"))
        assert agent is None and check is None

    def test_create_browser_audit_failure_returns_none(self):
        from api.browser_routes import _create_browser_audit

        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit boom")
        audit = _create_browser_audit(
            db, user_id="u", session_id="s1", action_type="navigate",
            action_target="http://x", action_params={}, success=True)
        assert audit is None


class TestBrowserCreateSession:
    def test_create_session_success(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        tools = _patch_browser_tools(monkeypatch, browser_create_session={
            "success": True, "session_id": "sess-1", "headless": True})
        resp = client.post("/api/browser/session/create", json={
            "browser_type": "firefox", "agent_id": "ag-1", "headless": False})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        tools["browser_create_session"].assert_awaited_once()
        created = db.add.call_args[0][0]
        assert created.session_id == "sess-1"
        assert created.headless is False
        assert created.browser_type == "firefox"

    def test_create_session_default_headless_from_result(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_create_session={
            "success": True, "session_id": "sess-2", "headless": True})
        resp = client.post("/api/browser/session/create", json={})
        assert resp.status_code == 200
        assert db.add.call_args[0][0].headless is True

    def test_create_session_db_record_failure_swallowed(self, monkeypatch, browser_user):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db boom")
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_create_session={
            "success": True, "session_id": "sess-3"})
        resp = client.post("/api/browser/session/create", json={})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_create_session_governance_error_403(self, monkeypatch, browser_user):
        client = _browser_client(db=MagicMock(), user=browser_user)
        _patch_browser_tools(monkeypatch, browser_create_session={
            "success": False, "error": "Governance denied"})
        resp = client.post("/api/browser/session/create", json={"agent_id": "ag-1"})
        assert resp.status_code == 403

    def test_create_session_generic_failure_400(self, monkeypatch, browser_user):
        client = _browser_client(db=MagicMock(), user=browser_user)
        _patch_browser_tools(monkeypatch, browser_create_session={
            "success": False, "error": "playwright crash"})
        resp = client.post("/api/browser/session/create", json={})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "SESSION_CREATE_FAILED"

    def test_create_session_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/session/create", json={}).status_code == 401


class TestBrowserNavigate:
    def test_navigate_success_no_agent(self, monkeypatch, browser_user):
        db = MagicMock()
        _chain(db)
        db.query.return_value.filter.return_value.first.return_value = None
        client = _browser_client(db=db, user=browser_user)
        tools = _patch_browser_tools(monkeypatch, browser_navigate={
            "success": True, "title": "Example", "url": "https://example.com"})
        resp = client.post("/api/browser/navigate", json={
            "session_id": "s1", "url": "https://example.com"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Example"
        tools["browser_navigate"].assert_awaited_once()
        added = db.add.call_args
        assert added is not None

    def test_navigate_governance_allowed_creates_execution(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = None
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            tools = _patch_browser_tools(monkeypatch, browser_navigate={
                "success": True, "title": "T", "url": "http://x"})
            resp = client.post("/api/browser/navigate", json={
                "session_id": "s1", "url": "http://x", "agent_id": "ag-1"})
        assert resp.status_code == 200
        # AgentExecution created
        created = [c[0][0] for c in db.add.call_args_list
                   if type(c[0][0]).__name__ == "AgentExecution"]
        assert created
        assert created[0].agent_id == "ag-1"
        tools["browser_navigate"].assert_awaited_once_with(
            session_id="s1", url="http://x", wait_until="load", user_id="browser-user")

    def test_navigate_governance_denied_403_with_audit(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_denied()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            _patch_browser_tools(monkeypatch)
            resp = client.post("/api/browser/navigate", json={
                "session_id": "s1", "url": "http://x", "agent_id": "ag-1"})
        assert resp.status_code == 403
        audits = [c[0][0] for c in db.add.call_args_list
                  if type(c[0][0]).__name__ == "BrowserAudit"]
        assert audits and audits[0].success is False

    def test_navigate_governance_resolver_exception_continues(self, monkeypatch, browser_user):
        db = MagicMock()
        _chain(db)
        db.query.return_value.filter.return_value.first.return_value = None
        client = _browser_client(db=db, user=browser_user)
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(
            side_effect=RuntimeError("boom"))
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory"):
            _patch_browser_tools(monkeypatch, browser_navigate={
                "success": True, "title": "T", "url": "http://x"})
            resp = client.post("/api/browser/navigate", json={
                "session_id": "s1", "url": "http://x", "agent_id": "ag-1"})
        assert resp.status_code == 200

    def test_navigate_updates_db_session(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace(
            current_url=None, page_title=None, id="db-1")
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_navigate={
            "success": True, "title": "T", "url": "http://x"})
        resp = client.post("/api/browser/navigate", json={
            "session_id": "s1", "url": "http://x"})
        assert resp.status_code == 200
        row = q.first.return_value
        assert row.current_url == "http://x"
        assert row.page_title == "T"

    def test_navigate_db_update_failure_swallowed(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace()
        db.commit.side_effect = RuntimeError("commit boom")
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_navigate={
            "success": True, "title": "T", "url": "http://x"})
        resp = client.post("/api/browser/navigate", json={
            "session_id": "s1", "url": "http://x"})
        assert resp.status_code == 200

    def test_navigate_failure_audits_error(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_navigate={
            "success": False, "error": "timeout"})
        resp = client.post("/api/browser/navigate", json={
            "session_id": "s1", "url": "http://x"})
        assert resp.status_code == 200
        audits = [c[0][0] for c in db.add.call_args_list
                  if type(c[0][0]).__name__ == "BrowserAudit"]
        assert audits[0].success is False
        assert audits[0].error_message == "timeout"

    def test_navigate_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/navigate", json={
                "session_id": "s1", "url": "http://x"}).status_code == 401


class TestBrowserScreenshot:
    def test_screenshot_success(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        tools = _patch_browser_tools(monkeypatch, browser_screenshot={
            "success": True, "size_bytes": 42})
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=False):
            resp = client.post("/api/browser/screenshot", json={
                "session_id": "s1", "full_page": True, "path": "/tmp/s.png",
                "agent_id": "ag-1"})
        assert resp.status_code == 200
        assert resp.json()["size_bytes"] == 42
        tools["browser_screenshot"].assert_awaited_once_with(
            session_id="s1", full_page=True, path="/tmp/s.png",
            user_id="browser-user")

    def test_screenshot_with_governance(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            _patch_browser_tools(monkeypatch, browser_screenshot={
                "success": True, "size_bytes": 1})
            resp = client.post("/api/browser/screenshot", json={
                "session_id": "s1", "agent_id": "ag-1"})
        assert resp.status_code == 200

    def test_screenshot_failure(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_screenshot={
            "success": False, "error": "no page"})
        resp = client.post("/api/browser/screenshot", json={"session_id": "s1"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_screenshot_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/screenshot", json={"session_id": "s1"}).status_code == 401


class TestBrowserFillForm:
    def test_fill_form_no_submit_governance(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            tools = _patch_browser_tools(monkeypatch, browser_fill_form={
                "success": True, "fields_filled": 2})
            resp = client.post("/api/browser/fill-form", json={
                "session_id": "s1", "selectors": {"#a": "1"}, "agent_id": "ag-1"})
        assert resp.status_code == 200
        # fill (non-submit) uses browser_fill_form action
        gov.can_perform_action.assert_called_once_with(
            agent_id="ag-1", action_type="browser_fill_form")
        tools["browser_fill_form"].assert_awaited_once_with(
            session_id="s1", selectors={"#a": "1"}, submit=False,
            user_id="browser-user")

    def test_fill_form_submit_governance(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            tools = _patch_browser_tools(monkeypatch, browser_fill_form={
                "success": True, "fields_filled": 2})
            resp = client.post("/api/browser/fill-form", json={
                "session_id": "s1", "selectors": {"#a": "1"}, "submit": True,
                "agent_id": "ag-1"})
        assert resp.status_code == 200
        gov.can_perform_action.assert_called_once_with(
            agent_id="ag-1", action_type="browser_form_submit")
        tools["browser_fill_form"].assert_awaited_once_with(
            session_id="s1", selectors={"#a": "1"}, submit=True,
            user_id="browser-user")

    def test_fill_form_success_no_agent(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_fill_form={
            "success": True, "fields_filled": 3})
        resp = client.post("/api/browser/fill-form", json={
            "session_id": "s1", "selectors": {"#a": "1", "#b": "2"}})
        assert resp.status_code == 200
        assert resp.json()["fields_filled"] == 3

    def test_fill_form_failure(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_fill_form={
            "success": False, "error": "selector missing", "fields_filled": 0})
        resp = client.post("/api/browser/fill-form", json={
            "session_id": "s1", "selectors": {"#x": "1"}})
        assert resp.status_code == 200

    def test_fill_form_missing_selectors_422(self, monkeypatch, browser_user):
        client = _browser_client(db=MagicMock(), user=browser_user)
        resp = client.post("/api/browser/fill-form", json={"session_id": "s1"})
        assert resp.status_code == 422

    def test_fill_form_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/fill-form", json={
                "session_id": "s1", "selectors": {}}).status_code == 401


class TestBrowserClick:
    def test_click_success_with_governance(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            tools = _patch_browser_tools(monkeypatch, browser_click={
                "success": True})
            resp = client.post("/api/browser/click", json={
                "session_id": "s1", "selector": "#btn", "wait_for": "nav",
                "agent_id": "ag-1"})
        assert resp.status_code == 200
        tools["browser_click"].assert_awaited_once_with(
            session_id="s1", selector="#btn", wait_for="nav",
            user_id="browser-user")

    def test_click_success_no_agent(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_click={"success": True})
        resp = client.post("/api/browser/click", json={
            "session_id": "s1", "selector": "#btn"})
        assert resp.status_code == 200

    def test_click_failure_audits(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_click={
            "success": False, "error": "not found"})
        resp = client.post("/api/browser/click", json={
            "session_id": "s1", "selector": "#x"})
        assert resp.status_code == 200
        audits = [c[0][0] for c in db.add.call_args_list
                  if type(c[0][0]).__name__ == "BrowserAudit"]
        assert audits[0].error_message == "not found"

    def test_click_missing_selector_422(self, monkeypatch, browser_user):
        client = _browser_client(db=MagicMock(), user=browser_user)
        assert client.post("/api/browser/click", json={
            "session_id": "s1"}).status_code == 422

    def test_click_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/click", json={
                "session_id": "s1", "selector": "#a"}).status_code == 401


class TestBrowserExtractText:
    def test_extract_text_success(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        tools = _patch_browser_tools(monkeypatch, browser_extract_text={
            "success": True, "length": 7})
        resp = client.post("/api/browser/extract-text", json={
            "session_id": "s1", "selector": "p"})
        assert resp.status_code == 200
        tools["browser_extract_text"].assert_awaited_once_with(
            session_id="s1", selector="p", user_id="browser-user")

    def test_extract_text_with_agent_governance(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        agent, check = _gov_allowed()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, None))
        gov = MagicMock()
        gov.can_perform_action.return_value = check
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=True), \
                patch("api.browser_routes.AgentContextResolver",
                      return_value=resolver), \
                patch("api.browser_routes.ServiceFactory") as sf:
            sf.get_governance_service.return_value = gov
            _patch_browser_tools(monkeypatch, browser_extract_text={
                "success": True, "length": 1})
            resp = client.post("/api/browser/extract-text", json={
                "session_id": "s1", "agent_id": "ag-1"})
        assert resp.status_code == 200

    def test_extract_text_failure(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_extract_text={
            "success": False, "error": "stale", "length": 0})
        resp = client.post("/api/browser/extract-text", json={"session_id": "s1"})
        assert resp.status_code == 200
        audits = [c[0][0] for c in db.add.call_args_list
                  if type(c[0][0]).__name__ == "BrowserAudit"]
        assert audits[0].result_data == {}

    def test_extract_text_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/extract-text", json={"session_id": "s1"}).status_code == 401


class TestBrowserExecuteScript:
    def test_execute_script_success(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        tools = _patch_browser_tools(monkeypatch, browser_execute_script={
            "success": True, "result": 1})
        with patch("core.feature_flags.FeatureFlags.should_enforce_governance",
                   return_value=False):
            resp = client.post("/api/browser/execute-script", json={
                "session_id": "s1", "script": "return 1;", "agent_id": "ag-1"})
        assert resp.status_code == 200
        tools["browser_execute_script"].assert_awaited_once_with(
            session_id="s1", script="return 1;", user_id="browser-user")

    def test_execute_script_failure(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_execute_script={
            "success": False, "error": "syntax"})
        resp = client.post("/api/browser/execute-script", json={
            "session_id": "s1", "script": "bad("})
        assert resp.status_code == 200
        audits = [c[0][0] for c in db.add.call_args_list
                  if type(c[0][0]).__name__ == "BrowserAudit"]
        assert audits[0].action_target == "4 chars"

    def test_execute_script_missing_script_422(self, monkeypatch, browser_user):
        client = _browser_client(db=MagicMock(), user=browser_user)
        assert client.post("/api/browser/execute-script", json={
            "session_id": "s1"}).status_code == 422

    def test_execute_script_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/execute-script", json={
                "session_id": "s1", "script": "x"}).status_code == 401


class TestBrowserCloseSession:
    def test_close_session_success(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace(status="active", closed_at=None)
        client = _browser_client(db=db, user=browser_user)
        tools = _patch_browser_tools(monkeypatch, browser_close_session={
            "success": True})
        resp = client.post("/api/browser/session/close", json={
            "session_id": "s1", "agent_id": "ag-1"})
        assert resp.status_code == 200
        row = q.first.return_value
        assert row.status == "closed"
        assert row.closed_at is not None
        tools["browser_close_session"].assert_awaited_once_with(
            session_id="s1", user_id="browser-user")

    def test_close_session_db_update_failure_swallowed(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace()
        db.commit.side_effect = RuntimeError("boom")
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_close_session={"success": True})
        resp = client.post("/api/browser/session/close", json={"session_id": "s1"})
        assert resp.status_code == 200

    def test_close_session_no_db_row(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = None
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_close_session={"success": True})
        resp = client.post("/api/browser/session/close", json={"session_id": "s1"})
        assert resp.status_code == 200

    def test_close_session_failure(self, monkeypatch, browser_user):
        db = MagicMock()
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_close_session={
            "success": False, "error": "gone"})
        resp = client.post("/api/browser/session/close", json={"session_id": "s1"})
        assert resp.status_code == 200

    def test_close_session_unauthenticated(self):
        assert _browser_client(db=MagicMock()).post(
            "/api/browser/session/close", json={"session_id": "s1"}).status_code == 401


class TestBrowserGetSessionInfo:
    def test_info_success_with_db_row(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = SimpleNamespace(
            id="db-1", created_at=datetime(2026, 1, 1),
            status="active", browser_type="chromium")
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_get_page_info={
            "success": True, "url": "http://x"})
        resp = client.get("/api/browser/session/s1/info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["db_session_id"] == "db-1"
        assert body["status"] == "active"
        assert body["created_at"] is not None

    def test_info_success_no_db_row(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.return_value = None
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_get_page_info={
            "success": True, "url": "http://x"})
        resp = client.get("/api/browser/session/s1/info")
        assert resp.status_code == 200
        assert "db_session_id" not in resp.json()

    def test_info_db_error_swallowed(self, monkeypatch, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.first.side_effect = RuntimeError("db boom")
        client = _browser_client(db=db, user=browser_user)
        _patch_browser_tools(monkeypatch, browser_get_page_info={
            "success": True, "url": "http://x"})
        resp = client.get("/api/browser/session/s1/info")
        assert resp.status_code == 200

    def test_info_unauthenticated(self):
        assert _browser_client(db=MagicMock()).get(
            "/api/browser/session/s1/info").status_code == 401


class TestBrowserListSessions:
    def _browser_session_row(self, sid="s1", **kw):
        return SimpleNamespace(
            session_id=sid,
            id="db-" + sid,
            browser_type=kw.get("browser_type", "chromium"),
            headless=kw.get("headless", True),
            status=kw.get("status", "active"),
            current_url=kw.get("current_url", None),
            page_title=kw.get("page_title", None),
            created_at=kw.get("created_at", datetime(2026, 1, 1)),
            closed_at=kw.get("closed_at", None),
        )

    def test_list_sessions_success(self, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.all.return_value = [self._browser_session_row(), self._browser_session_row(
            "s2", closed_at=datetime(2026, 1, 2))]
        client = _browser_client(db=db, user=browser_user)
        resp = client.get("/api/browser/sessions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 2
        assert body["data"][1]["closed_at"] is not None

    def test_list_sessions_service_failure_500(self, browser_user):
        db = MagicMock()
        _chain(db)
        db.query.return_value.order_by.return_value.limit.return_value.all.side_effect = (
            RuntimeError("boom"))
        client = _browser_client(db=db, user=browser_user)
        resp = client.get("/api/browser/sessions")
        assert resp.status_code == 500

    def test_list_sessions_unauthenticated(self):
        assert _browser_client(db=MagicMock()).get(
            "/api/browser/sessions").status_code == 401


class TestBrowserAuditLog:
    def _audit_row(self, aid="a1", **kw):
        return SimpleNamespace(
            id=aid,
            session_id=kw.get("session_id", "s1"),
            action_type=kw.get("action_type", "click"),
            action_target=kw.get("action_target", "#x"),
            success=kw.get("success", True),
            result_summary=kw.get("result_summary", None),
            error_message=kw.get("error_message", None),
            duration_ms=kw.get("duration_ms", 5),
            created_at=kw.get("created_at", datetime(2026, 1, 1)),
        )

    def test_audit_success(self, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.all.return_value = [self._audit_row()]
        client = _browser_client(db=db, user=browser_user)
        resp = client.get("/api/browser/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"][0]["action_type"] == "click"
        assert body["message"] == "Retrieved 1 audit entries"

    def test_audit_with_session_filter(self, browser_user):
        db = MagicMock()
        q = _chain(db)
        q.all.return_value = []
        client = _browser_client(db=db, user=browser_user)
        resp = client.get("/api/browser/audit?session_id=s9")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_audit_service_failure_500(self, browser_user):
        db = MagicMock()
        _chain(db)
        db.query.return_value.order_by.return_value.limit.return_value.all.side_effect = (
            RuntimeError("boom"))
        client = _browser_client(db=db, user=browser_user)
        assert client.get("/api/browser/audit").status_code == 500

    def test_audit_unauthenticated(self):
        assert _browser_client(db=MagicMock()).get(
            "/api/browser/audit").status_code == 401


# ============================================================================
# 8. api/integrations/memory_backfill_routes.py
# ============================================================================
class TestParseIsoDatetime:
    def test_parse_z_suffix(self):
        from api.integrations.memory_backfill_routes import parse_iso_datetime

        dt = parse_iso_datetime("2026-03-27T00:00:00Z")
        assert dt == datetime(2026, 3, 27, tzinfo=timezone.utc)

    def test_parse_naive_assumes_utc(self):
        from api.integrations.memory_backfill_routes import parse_iso_datetime

        dt = parse_iso_datetime("2026-03-27T00:00:00")
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(0)

    def test_parse_aware_converts_to_utc(self):
        from api.integrations.memory_backfill_routes import parse_iso_datetime

        dt = parse_iso_datetime("2026-03-27T00:00:00+05:00")
        assert dt.tzinfo is not None
        assert dt == datetime(2026, 3, 26, 19, 0, tzinfo=timezone.utc)

    def test_parse_invalid_raises_value_error(self):
        from api.integrations.memory_backfill_routes import parse_iso_datetime

        with pytest.raises(ValueError):
            parse_iso_datetime("not-a-date")


def _backfill_client(db=None):
    return _client(backfill_router, db=db)


class TestTriggerBackfill:
    def test_trigger_success(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_backfill",
                   new=AsyncMock(return_value={
                       "success": True, "job_id": "j1", "integration_id": "outlook"})):
            resp = _backfill_client(db).post("/api/integrations/outlook/backfill", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["job_id"] == "j1"
        assert body["message"] == "Backfill started for outlook"

    def test_trigger_with_dates(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_backfill",
                   new=AsyncMock(return_value={"success": False})) as tb:
            resp = _backfill_client(db).post("/api/integrations/outlook/backfill", json={
                "start_date": "2026-03-27T00:00:00Z",
                "end_date": "2026-04-26T23:59:59Z",
                "limit": 100})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Backfill failed for outlook"
        call = tb.await_args
        assert call.kwargs["start_date"] == datetime(2026, 3, 27, tzinfo=timezone.utc)
        assert call.kwargs["end_date"] == datetime(
            2026, 4, 26, 23, 59, 59, tzinfo=timezone.utc)
        assert call.kwargs["limit"] == 100

    def test_trigger_invalid_date_400(self):
        db = MagicMock()
        resp = _backfill_client(db).post("/api/integrations/outlook/backfill", json={
            "start_date": "garbage"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Internal error"

    def test_trigger_reversed_dates_400(self):
        db = MagicMock()
        resp = _backfill_client(db).post("/api/integrations/outlook/backfill", json={
            "start_date": "2026-05-01T00:00:00Z",
            "end_date": "2026-04-01T00:00:00Z"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "start_date must be before end_date"

    def test_trigger_limit_bounds_422(self):
        db = MagicMock()
        client = _backfill_client(db)
        assert client.post("/api/integrations/outlook/backfill", json={
            "limit": 0}).status_code == 422
        assert client.post("/api/integrations/outlook/backfill", json={
            "limit": 10001}).status_code == 422

    def test_trigger_service_failure_500(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_backfill",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = _backfill_client(db).post("/api/integrations/outlook/backfill", json={})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"


class TestBackfillStatus:
    def test_status_success(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin.get_job_status",
                   return_value={"job_id": "j1", "status": "running", "progress": 45}):
            resp = _backfill_client(db).get("/api/integrations/outlook/backfill/status/j1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "running"

    def test_status_not_found_404(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin.get_job_status",
                   return_value=None):
            resp = _backfill_client(db).get("/api/integrations/outlook/backfill/status/jx")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_status_service_failure_500(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.MemoryIntegrationMixin.get_job_status",
                   side_effect=RuntimeError("boom")):
            resp = _backfill_client(db).get("/api/integrations/outlook/backfill/status/j1")
        assert resp.status_code == 500


class TestTriggerAllBackfills:
    def test_all_success(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_all_backfills",
                   new=AsyncMock(return_value={
                       "success": True, "total_triggered": 2,
                       "job_ids": ["j1", "j2"], "errors": [],
                       "message": "Triggered 2 backfills"})):
            resp = _backfill_client(db).post("/api/integrations/backfill/all", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total_triggered"] == 2
        assert body["message"] == "Triggered 2 backfills"

    def test_specific_ids_success_and_partial_errors(self):
        db = MagicMock()
        results = [
            {"success": True, "job_id": "j1"},
            {"success": False, "error": "not configured"},
        ]

        async def _fake(*args, **kwargs):
            return results.pop(0)

        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_backfill",
                   new=_fake):
            resp = _backfill_client(db).post("/api/integrations/backfill/all", json={
                "integration_ids": ["outlook", "gmail"],
                "start_date": "2026-03-27T00:00:00Z",
                "end_date": "2026-04-26T23:59:59Z",
                "limit_per_integration": 10})
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["total_triggered"] == 1
        assert body["job_ids"] == ["j1"]
        assert body["errors"] == ["gmail: not configured"]
        assert body["success"] is True

    def test_specific_ids_all_failed(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_backfill",
                   new=AsyncMock(return_value={"success": False, "error": "nope"})):
            resp = _backfill_client(db).post("/api/integrations/backfill/all", json={
                "integration_ids": ["outlook"]})
        body = resp.json()["data"]
        assert body["success"] is False
        assert body["total_triggered"] == 0

    def test_specific_ids_exception_captured(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_backfill",
                   new=AsyncMock(side_effect=RuntimeError("kaboom"))):
            resp = _backfill_client(db).post("/api/integrations/backfill/all", json={
                "integration_ids": ["outlook", "gmail"]})
        body = resp.json()["data"]
        assert len(body["errors"]) == 2
        assert all("kaboom" in e for e in body["errors"])

    def test_all_invalid_date_400(self):
        db = MagicMock()
        resp = _backfill_client(db).post("/api/integrations/backfill/all", json={
            "start_date": "garbage"})
        assert resp.status_code == 400

    def test_all_reversed_dates_400(self):
        db = MagicMock()
        resp = _backfill_client(db).post("/api/integrations/backfill/all", json={
            "start_date": "2026-05-01T00:00:00Z",
            "end_date": "2026-04-01T00:00:00Z"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "start_date must be before end_date"

    def test_all_service_failure_500(self):
        db = MagicMock()
        with patch("core.memory_integration_mixin.IntegrationBackfillManager.trigger_all_backfills",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = _backfill_client(db).post("/api/integrations/backfill/all", json={})
        assert resp.status_code == 500


class TestActiveBackfills:
    def test_active_success(self):
        from core.memory_integration_mixin import BackfillJob

        running = BackfillJob("j1", "outlook")
        running.status = "running"
        pending = BackfillJob("j2", "gmail")
        pending.status = "pending"
        done = BackfillJob("j3", "slack")
        done.status = "completed"
        with patch("core.memory_integration_mixin._backfill_jobs",
                   {"j1": running, "j2": pending, "j3": done}):
            resp = _backfill_client(MagicMock()).get("/api/integrations/backfill/active")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "Found 2 active jobs"
        statuses = {j["job_id"]: j["status"] for j in body["data"]}
        assert statuses == {"j1": "running", "j2": "pending"}

    def test_active_none(self):
        with patch("core.memory_integration_mixin._backfill_jobs", {}):
            resp = _backfill_client(MagicMock()).get("/api/integrations/backfill/active")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_active_service_failure_500(self):
        bad = MagicMock()
        bad.values.side_effect = RuntimeError("boom")
        with patch("core.memory_integration_mixin._backfill_jobs", bad):
            resp = _backfill_client(MagicMock()).get("/api/integrations/backfill/active")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"
