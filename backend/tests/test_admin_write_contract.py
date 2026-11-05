"""Failure-first contract controls for the seven admin privilege/budget routes."""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker

import core.admin_write_service as service
from api.admin.budget_routes import router as budget_router
from api.admin_routes import router as admin_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AdminRole,
    AdminUser,
    AuditLog,
    Tenant,
    TenantSetting,
    User,
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/admin-contract.db",
        connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    super_admin = User(
        id="super-1", email="super@example.com", hashed_password="x",
        first_name="Super", last_name="Admin", role="super_admin",
        status="active", tenant_id="tenant-1", is_active=True)
    workspace_admin = User(
        id="workspace-admin-1", email="wa@example.com", hashed_password="x",
        first_name="Workspace", last_name="Admin", role="workspace_admin",
        status="active", tenant_id="tenant-1", is_active=True)
    role = AdminRole(
        id="role-1", name="Role One",
        permissions={"users": True, "workflows": False}, description="d")
    other_role = AdminRole(
        id="role-2", name="Role Two",
        permissions={"users": False}, description="other")
    admin_user = AdminUser(
        id="admin-user-1", email="admin-user@example.com", name="Admin User",
        password_hash="hash", role_id="role-1", status="active")
    tenant = Tenant(
        id="tenant-1", name="Tenant One", subdomain="tenant-one")
    seed.add_all([
        super_admin, workspace_admin, role, other_role, admin_user, tenant])
    seed.commit()
    seed.close()

    app = FastAPI()
    app.include_router(admin_router)
    app.include_router(budget_router)

    def _db_override():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: super_admin
    yield SimpleNamespace(
        app=app, engine=engine, Session=Session,
        super_admin=super_admin, workspace_admin=workspace_admin)
    app.dependency_overrides.clear()
    engine.dispose()


def _client(env):
    return TestClient(env.app, raise_server_exceptions=False)


def _as(env, actor):
    env.app.dependency_overrides[get_current_user] = lambda: actor


def _seed_budget(env, value: str):
    db = env.Session()
    db.add(TenantSetting(
        tenant_id="tenant-1", setting_key="billing", setting_value=value))
    db.commit()
    db.close()


def _audit(env, operation_id):
    db = env.Session()
    try:
        return db.query(AuditLog).filter(
            AuditLog.id == operation_id).first()
    finally:
        db.close()


def test_role_create_update_delete_and_replay(env):
    client = _client(env)
    created = client.post(
        "/api/admin/roles?operation_id=role-create-1",
        json={"name": "Created Role", "permissions": {"users": True},
              "description": "created"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["verification"]["status"] == "verified"
    role_id = body["id"]
    assert body["operation_id"].startswith("admin:role-create:")
    assert _audit(env, body["operation_id"]).success is True

    replay = client.post(
        "/api/admin/roles?operation_id=role-create-1",
        json={"name": "Created Role", "permissions": {"users": True},
              "description": "created"})
    assert replay.status_code == 201, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"

    changed = client.post(
        "/api/admin/roles?operation_id=role-create-1",
        json={"name": "Different Role", "permissions": {"users": True},
              "description": "created"})
    assert changed.status_code == 409, changed.text

    updated = client.patch(
        f"/api/admin/roles/{role_id}?operation_id=role-update-1",
        json={"name": "Renamed Role", "permissions": {"users": False}})
    assert updated.status_code == 200, updated.text
    assert updated.json()["verification"]["status"] == "verified"
    fresh = env.Session()
    try:
        persisted = fresh.query(AdminRole).filter(
            AdminRole.id == role_id).one()
        assert persisted.name == "Renamed Role"
        assert persisted.permissions == {"users": False}
    finally:
        fresh.close()

    deleted = client.delete(
        f"/api/admin/roles/{role_id}?operation_id=role-delete-1")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["verification"]["status"] == "verified"
    fresh = env.Session()
    try:
        assert fresh.query(AdminRole).filter(
            AdminRole.id == role_id).first() is None
    finally:
        fresh.close()


def test_role_delete_in_use_and_concurrent_assignment_refuse(env, monkeypatch):
    client = _client(env)
    in_use = client.delete("/api/admin/roles/role-1")
    assert in_use.status_code == 409, in_use.text

    original_claim = service._claim_actor

    def claim_then_assign(db, actor, *, required="super_admin"):
        peer = env.Session()
        peer.add(AdminUser(
            id="late-user", email="late@example.com", name="Late",
            password_hash="hash", role_id="role-2", status="active"))
        peer.commit()
        peer.close()
        return original_claim(db, actor, required=required)

    monkeypatch.setattr(service, "_claim_actor", claim_then_assign)
    raced = client.delete("/api/admin/roles/role-2")
    assert raced.status_code == 409, raced.text
    fresh = env.Session()
    try:
        assert fresh.query(AdminRole).filter(
            AdminRole.id == "role-2").first() is not None
    finally:
        fresh.close()


def test_user_create_update_delete_and_replay(env):
    client = _client(env)
    created = client.post(
        "/api/admin/users?operation_id=user-create-1",
        json={"email": "new-admin@example.com", "name": "New Admin",
              "password": "password123", "role_id": "role-1"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["verification"]["status"] == "verified"
    admin_id = body["id"]

    duplicate = client.post(
        "/api/admin/users",
        json={"email": "new-admin@example.com", "name": "Dup",
              "password": "password123", "role_id": "role-1"})
    assert duplicate.status_code == 409, duplicate.text

    replay = client.post(
        "/api/admin/users?operation_id=user-create-1",
        json={"email": "new-admin@example.com", "name": "New Admin",
              "password": "password123", "role_id": "role-1"})
    assert replay.status_code == 201, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"

    updated = client.patch(
        f"/api/admin/users/{admin_id}?operation_id=user-update-1",
        json={"name": "Renamed Admin", "status": "inactive"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Renamed Admin"
    assert updated.json()["status"] == "inactive"

    deleted = client.delete(
        f"/api/admin/users/{admin_id}?operation_id=user-delete-1")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["verification"]["status"] == "verified"


def test_actor_demotion_before_claim_refuses_without_effect(env, monkeypatch):
    client = _client(env)
    original_claim = service._claim_actor

    def demote_then_claim(db, actor, *, required="super_admin"):
        peer = env.Session()
        peer.execute(update(User).where(User.id == actor.id).values(
            role="member"))
        peer.commit()
        peer.close()
        return original_claim(db, actor, required=required)

    monkeypatch.setattr(service, "_claim_actor", demote_then_claim)
    response = client.post(
        "/api/admin/roles",
        json={"name": "Should Not Exist", "permissions": {"users": True}})
    assert response.status_code == 409, response.text
    fresh = env.Session()
    try:
        assert fresh.query(AdminRole).filter(
            AdminRole.name == "Should Not Exist").first() is None
    finally:
        fresh.close()


def test_stale_role_update_and_user_update_refuse(env, monkeypatch):
    client = _client(env)
    original_claim = service._claim_actor

    def claim_then_change_role(db, actor, *, required="super_admin"):
        peer = env.Session()
        peer.execute(update(AdminRole).where(
            AdminRole.id == "role-2").values(description="peer change"))
        peer.commit()
        peer.close()
        return original_claim(db, actor, required=required)

    monkeypatch.setattr(service, "_claim_actor", claim_then_change_role)
    stale_role = client.patch(
        "/api/admin/roles/role-2", json={"name": "Changed Role"})
    assert stale_role.status_code == 409, stale_role.text

    monkeypatch.setattr(service, "_claim_actor", original_claim)

    def claim_then_change_user(db, actor, *, required="super_admin"):
        peer = env.Session()
        peer.execute(update(AdminUser).where(
            AdminUser.id == "admin-user-1").values(name="Peer Name"))
        peer.commit()
        peer.close()
        return original_claim(db, actor, required=required)

    monkeypatch.setattr(service, "_claim_actor", claim_then_change_user)
    stale_user = client.patch(
        "/api/admin/users/admin-user-1", json={"status": "inactive"})
    assert stale_user.status_code == 409, stale_user.text


def test_budget_partial_merge_and_stale_update_refuses(env, monkeypatch):
    _seed_budget(env, json.dumps({"budget_limit_usd": 10.0}))
    client = _client(env)
    first = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=budget-1",
        json={"budget_limit_usd": 25.0})
    assert first.status_code == 200, first.text
    assert first.json()["budget_limit_usd"] == 25.0
    assert first.json()["verification"]["status"] == "verified"

    replay = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=budget-1",
        json={"budget_limit_usd": 25.0})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"

    changed = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=budget-1",
        json={"budget_limit_usd": 26.0})
    assert changed.status_code == 409, changed.text

    second = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=budget-2",
        json={"enforcement_mode": "hard_stop"})
    assert second.status_code == 200, second.text
    assert second.json()["enforcement_mode"] == "hard_stop"
    fresh = env.Session()
    try:
        row = fresh.query(TenantSetting).filter(
            TenantSetting.tenant_id == "tenant-1",
            TenantSetting.setting_key == "billing").one()
        value = json.loads(row.setting_value)
        assert value["budget_limit_usd"] == 25.0
        assert value["enforcement"]["mode"] == "hard_stop"
    finally:
        fresh.close()

    original_claim = service._claim_actor

    def claim_then_change_budget(db, actor, *, required="workspace_admin"):
        peer = env.Session()
        row = peer.query(TenantSetting).filter(
            TenantSetting.tenant_id == "tenant-1",
            TenantSetting.setting_key == "billing").one()
        peer.execute(update(TenantSetting).where(
            TenantSetting.id == row.id).values(
                setting_value=json.dumps({"budget_limit_usd": 99.0})))
        peer.commit()
        peer.close()
        return original_claim(db, actor, required=required)

    monkeypatch.setattr(service, "_claim_actor", claim_then_change_budget)
    stale = client.put(
        "/api/admin/tenants/tenant-1/budget",
        json={"budget_limit_usd": 30.0})
    assert stale.status_code == 409, stale.text


def test_audit_refuted_and_lost_confirmation_are_honest(env, monkeypatch):
    client = _client(env)
    original_audit_row = service._audit_row

    def wrong_audit(**kwargs):
        row = original_audit_row(**kwargs)
        row.action = "wrong-admin-action"
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    refuted = client.post(
        "/api/admin/roles",
        json={"name": "Audit Refuted", "permissions": {"users": True}})
    assert refuted.status_code == 503, refuted.text
    assert refuted.json()["detail"]["verification"]["status"] == "refuted"

    monkeypatch.setattr(service, "_audit_row", original_audit_row)
    original_db = env.app.dependency_overrides[get_db]

    def flaky_db():
        session = env.Session()
        original_commit = session.commit
        state = {"failed": False}

        def commit():
            if not state["failed"] and any(
                    isinstance(row, AuditLog) for row in session.new):
                state["failed"] = True
                raise RuntimeError(
                    "lost confirmation SYNTHETIC-ADMIN-SECRET")
            return original_commit()

        session.commit = commit
        try:
            yield session
        finally:
            session.close()

    env.app.dependency_overrides[get_db] = flaky_db
    try:
        lost = client.post(
            "/api/admin/roles",
            json={"name": "Lost Confirmation", "permissions": {"users": True}})
        assert lost.status_code == 503, lost.text
        assert lost.json()["detail"]["error"]["code"] == "ADMIN_EFFECT_UNKNOWN"
        assert "SYNTHETIC-ADMIN-SECRET" not in lost.text
    finally:
        env.app.dependency_overrides[get_db] = original_db


def test_authorization_and_missing_target_refusals(env):
    client = _client(env)
    _as(env, env.workspace_admin)
    forbidden = client.post(
        "/api/admin/roles",
        json={"name": "Forbidden", "permissions": {"users": True}})
    assert forbidden.status_code == 403, forbidden.text

    _as(env, env.super_admin)
    missing_role = client.patch(
        "/api/admin/roles/missing-role", json={"name": "X"})
    assert missing_role.status_code == 404, missing_role.text
    missing_user = client.delete("/api/admin/users/missing-user")
    assert missing_user.status_code == 404, missing_user.text
    missing_tenant = client.put(
        "/api/admin/tenants/missing-tenant/budget",
        json={"budget_limit_usd": 10.0})
    assert missing_tenant.status_code == 404, missing_tenant.text


def test_concurrent_duplicate_role_create_has_one_typed_conflict(env):
    barrier = threading.Barrier(2)

    def create(operation_id):
        db = env.Session()
        try:
            barrier.wait()
            return service.create_admin_role(
                db, actor=env.super_admin, name="Concurrent Role",
                permissions={"users": True}, description=None,
                operation_id=operation_id)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ["concurrent-role-1", "concurrent-role-2"]))
    statuses = [result["status"] for result in results]
    assert statuses.count("verified") == 1, results
    assert statuses.count("conflict") == 1, results
    fresh = env.Session()
    try:
        assert fresh.query(AdminRole).filter(
            AdminRole.name == "Concurrent Role").count() == 1
    finally:
        fresh.close()


def test_concurrent_duplicate_user_email_has_one_typed_conflict(env):
    barrier = threading.Barrier(2)

    def create(operation_id):
        db = env.Session()
        try:
            barrier.wait()
            return service.create_admin_user(
                db, actor=env.super_admin, email="concurrent@example.com",
                name="Concurrent User", password="password123",
                role_id="role-1", operation_id=operation_id)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ["concurrent-user-1", "concurrent-user-2"]))
    statuses = [result["status"] for result in results]
    assert statuses.count("verified") == 1, results
    assert statuses.count("conflict") == 1, results
    fresh = env.Session()
    try:
        assert fresh.query(AdminUser).filter(
            AdminUser.email == "concurrent@example.com").count() == 1
    finally:
        fresh.close()
