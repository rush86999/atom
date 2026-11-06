"""Failure-first contracts for verified document-ingestion settings writes."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.document_settings_write_service as service
from api.document_ingestion_routes import router as ingestion_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AuditLog, IngestionSettings, Tenant, User, Workspace


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/document-settings.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        Workspace(id="ws2", name="Workspace Two", tenant_id="t1"),
        User(
            id="user-1", tenant_id="t1", workspace_id="ws1",
            email="user1@example.com", first_name="User", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="user-2", tenant_id="t1", workspace_id="ws2",
            email="user2@example.com", first_name="User", last_name="Two",
            role="member", status="active", is_active=True),
    ])
    seed.add_all([
        IngestionSettings(
            id="seed-ws1", tenant_id="t1", workspace_id="ws1",
            integration_id="gdrive", enabled=False,
            auto_sync_new_files=True, file_types=["pdf"],
            sync_folders=["/kept"], exclude_folders=["/skip"],
            max_file_size_mb=25, sync_frequency_minutes=90,
            entity_types=["invoice"], sync_mode="full"),
        IngestionSettings(
            id="seed-ws2", tenant_id="t1", workspace_id="ws2",
            integration_id="gdrive", enabled=True,
            auto_sync_new_files=False, file_types=["docx"],
            sync_folders=["/other"], exclude_folders=[],
            max_file_size_mb=5, sync_frequency_minutes=15),
    ])
    seed.commit()
    seed.close()

    app = FastAPI()
    app.include_router(ingestion_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        scoped = FastAPI()
        scoped.include_router(ingestion_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "user-1": Session().query(User).filter(User.id == "user-1").one(),
        "user-2": Session().query(User).filter(User.id == "user-2").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
    )


def _row(env, workspace_id, integration_id="gdrive"):
    db = env.Session()
    try:
        return db.query(IngestionSettings).filter(
            IngestionSettings.workspace_id == workspace_id,
            IngestionSettings.integration_id == integration_id).first()
    finally:
        db.close()


def _audits(env, operation_id=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _peer_update(env, row_id, **values):
    db = env.Session()
    try:
        db.execute(update(IngestionSettings).where(
            IngestionSettings.id == row_id).values(**values))
        db.commit()
    finally:
        db.close()


def test_create_new_settings_with_audit(env):
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=create-one",
        json={"integration_id": "dropbox", "enabled": True,
              "file_types": ["txt"], "max_file_size_mb": 10})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["enabled"] is True
    assert body["data"]["file_types"] == ["txt"]
    assert body["data"]["verification"]["status"] == "verified"
    assert body["data"]["operation_id"] == "document-settings:create-one"

    row = _row(env, "ws1", "dropbox")
    assert row is not None
    assert row.enabled is True
    assert row.file_types == ["txt"]
    assert row.max_file_size_mb == 10
    assert row.workspace_id == "ws1"

    audits = _audits(env, "document-settings:create-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "document_settings_updated"
    assert audit.user_id == "user-1"
    assert audit.workspace_id == "ws1"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == "dropbox"
    assert metadata["target_workspace_id"] == "ws1"
    assert "txt" not in audit.metadata_json
    assert "/kept" not in audit.metadata_json


def test_merge_preserves_unspecified_and_hybrid_fields(env):
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=merge-one",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code == 200, response.text
    row = _row(env, "ws1")
    assert row.enabled is True
    assert row.file_types == ["pdf"]
    assert row.sync_folders == ["/kept"]
    assert row.exclude_folders == ["/skip"]
    assert row.max_file_size_mb == 25
    assert row.sync_frequency_minutes == 90
    # Hybrid ingestion columns in the same row are not part of this family.
    assert row.entity_types == ["invoice"]
    assert row.sync_mode == "full"

    other = _row(env, "ws2")
    assert other.enabled is True and other.file_types == ["docx"]


def test_only_integration_id_is_no_change(env):
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings",
        json={"integration_id": "gdrive"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["verification"]["status"] == "no_change"
    assert body["data"]["verification"]["effect"] == "none"
    assert _audits(env) == []
    assert _row(env, "ws1").enabled is False


def test_matching_update_is_no_change(env):
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings",
        json={"integration_id": "gdrive", "enabled": False,
              "file_types": ["pdf"]})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["verification"]["status"] == "no_change"
    assert _audits(env) == []


def test_stale_settings_before_claim_refuses(env, monkeypatch):
    original = service._load_settings
    changed = {"done": False}

    def load_then_change(db, workspace_id, integration_id):
        row = original(db, workspace_id, integration_id)
        if not changed["done"] and workspace_id == "ws1":
            changed["done"] = True
            _peer_update(env, "seed-ws1", file_types=["peer"])
        return row

    monkeypatch.setattr(service, "_load_settings", load_then_change)
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=stale",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "STALE_TARGET"
    assert detail["verification"]["effect"] == "none"
    assert _row(env, "ws1").file_types == ["peer"]
    assert _row(env, "ws1").enabled is False
    assert _audits(env) == []


def test_replay_changed_material_and_later_revision(env):
    client = env.client(env.actors["user-1"])
    first = client.put(
        "/api/document-ingestion/settings?operation_id=replay",
        json={"integration_id": "gdrive", "enabled": True})
    assert first.status_code == 200, first.text
    replay = client.put(
        "/api/document-ingestion/settings?operation_id=replay",
        json={"integration_id": "gdrive", "enabled": True})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = client.put(
        "/api/document-ingestion/settings?operation_id=replay",
        json={"integration_id": "gdrive", "enabled": False})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    _peer_update(env, "seed-ws1", max_file_size_mb=99)
    later = client.put(
        "/api/document-ingestion/settings?operation_id=replay",
        json={"integration_id": "gdrive", "enabled": True})
    assert later.status_code == 503, later.text
    assert later.json()["detail"]["error"]["code"] == (
        "DOCUMENT_SETTINGS_COMMITTED_UNVERIFIED")


@pytest.mark.parametrize("change", ["deactivate", "tenant_move"])
def test_authority_change_before_claim_refuses(env, monkeypatch, change):
    original = service._load_settings
    changed = {"done": False}

    def load_then_change(db, workspace_id, integration_id):
        row = original(db, workspace_id, integration_id)
        if not changed["done"] and workspace_id == "ws1":
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate"
                    else {"tenant_id": "t2", "workspace_id": "ws2"})
                peer.execute(update(User).where(
                    User.id == "user-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_load_settings", load_then_change)
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=authority",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _row(env, "ws1").enabled is False
    assert _audits(env) == []


def test_confirmed_audit_rollback_reports_effect_none(env, monkeypatch):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=rollback",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "DOCUMENT_SETTINGS_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert _row(env, "ws1").enabled is False
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=readback",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "DOCUMENT_SETTINGS_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert _row(env, "ws1").enabled is True
    assert len(_audits(env, "document-settings:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-SETTINGS-SECRET")

        db.commit = lost_commit
        result = service.update_ingestion_settings(
            db, actor=env.actors["user-1"], workspace_id="ws1",
            integration_id="gdrive", changes={"enabled": True},
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == (
        "document-settings:lost-confirmation")
    assert "SYNTHETIC-SETTINGS-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-SETTINGS-SECRET" not in caplog.text
    assert _row(env, "ws1").enabled is False
    assert _audits(env) == []


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "workspace_id",
    "success",
    "security_level",
    "resource",
    "metadata_target_id",
    "metadata_target_workspace_id",
    "metadata_prior_digest",
    "metadata_result_digest",
    "metadata_request_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "user-2"
        elif field == "tenant_id":
            row.tenant_id = "t2"
        elif field == "workspace_id":
            row.workspace_id = "ws2"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "resource":
            row.resource = "ingestion_settings:ws1:other"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_target_workspace_id":
            metadata["target_workspace_id"] = "ws2"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client(env.actors["user-1"]).put(
        f"/api/document-ingestion/settings?operation_id=audit-{field}",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "DOCUMENT_SETTINGS_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_cross_workspace_rows_are_isolated(env):
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=isolate",
        json={"integration_id": "gdrive", "enabled": True})
    assert response.status_code == 200, response.text
    assert _row(env, "ws1").enabled is True
    other = _row(env, "ws2")
    assert other.enabled is True
    assert other.file_types == ["docx"]
    assert other.max_file_size_mb == 5

    response2 = env.client(env.actors["user-2"]).put(
        "/api/document-ingestion/settings?operation_id=isolate-two",
        json={"integration_id": "gdrive", "enabled": False})
    assert response2.status_code == 200, response2.text
    assert _row(env, "ws2").enabled is False
    assert _row(env, "ws1").enabled is True


def test_raw_folders_are_absent_from_audit_and_logs(env, caplog):
    response = env.client(env.actors["user-1"]).put(
        "/api/document-ingestion/settings?operation_id=folder-secret",
        json={"integration_id": "gdrive",
              "sync_folders": ["/SECRET_FOLDER"],
              "exclude_folders": ["/SECRET_EXCLUDED"]})
    assert response.status_code == 200, response.text
    audit = _audits(env, "document-settings:folder-secret")[0]
    assert "SECRET_FOLDER" not in (audit.metadata_json or "")
    assert "SECRET_EXCLUDED" not in (audit.metadata_json or "")
    assert "SECRET_FOLDER" not in (audit.description or "")
    assert "SECRET_FOLDER" not in caplog.text


def test_anonymous_requests_are_refused(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.put(
        "/api/document-ingestion/settings",
        json={"integration_id": "gdrive", "enabled": True}).status_code == 401
    assert _row(env, "ws1").enabled is False
