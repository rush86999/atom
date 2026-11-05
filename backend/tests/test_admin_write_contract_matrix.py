"""Seven-route admin privilege/budget failure-first matrix.

Covers the work-order pairs beyond the base contract file: concurrent duplicate
creates, role deletion versus assignment, concurrent budget partial updates,
fresh-session consumers, the exact audit matrix, no-op requests, non-finite
budgets, authority disablement, later target revisions and tombstone replays.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

import core.admin_write_service as service
from core.auth import get_current_user
from core.models import AdminRole, AdminUser, AuditLog, TenantSetting, User
from tests.test_admin_write_contract import (
    _as,
    _audit,
    _client,
    _seed_budget,
    env,
)


def _role_count(env, name):
    db = env.Session()
    try:
        return db.query(AdminRole).filter(AdminRole.name == name).count()
    finally:
        db.close()


def _admin_count(env, email):
    db = env.Session()
    try:
        return db.query(AdminUser).filter(AdminUser.email == email).count()
    finally:
        db.close()


def _billing(env, tenant_id="tenant-1"):
    db = env.Session()
    try:
        row = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.setting_key == "billing",
        ).first()
        return None if row is None else json.loads(row.setting_value)
    finally:
        db.close()


def test_concurrent_duplicate_role_create_has_one_winner(env):
    barrier = threading.Barrier(2)

    def _create(operation_id):
        db = env.Session()
        try:
            barrier.wait()
            return service.create_admin_role(
                db, actor=env.super_admin, name="Race Role",
                permissions={"users": True}, description="race",
                operation_id=operation_id)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            _create, ["race-role-1", "race-role-2"]))
    verified = [r for r in results if r["status"] == "verified"]
    assert len(verified) == 1, results
    assert _role_count(env, "Race Role") == 1
    for result in results:
        if result["status"] != "verified":
            assert result["status"] in (
                "conflict", "committed_unverified", "effect_unknown"), result


def test_concurrent_duplicate_user_create_has_one_winner(env):
    barrier = threading.Barrier(2)

    def _create(operation_id):
        db = env.Session()
        try:
            barrier.wait()
            return service.create_admin_user(
                db, actor=env.super_admin,
                email="race-admin@example.com", name="Race Admin",
                password="password123", role_id="role-1",
                operation_id=operation_id)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            _create, ["race-user-1", "race-user-2"]))
    verified = [r for r in results if r["status"] == "verified"]
    assert len(verified) == 1, results
    assert _admin_count(env, "race-admin@example.com") == 1


def test_role_delete_and_user_assignment_never_leave_a_dangling_user(env):
    barrier = threading.Barrier(2)

    def _delete():
        db = env.Session()
        try:
            barrier.wait()
            return service.delete_admin_role(
                db, actor=env.super_admin, role_id="role-2",
                operation_id="race-role-delete")
        finally:
            db.close()

    def _assign():
        db = env.Session()
        try:
            barrier.wait()
            return service.create_admin_user(
                db, actor=env.super_admin,
                email="role-race-user@example.com", name="Role Race",
                password="password123", role_id="role-2",
                operation_id="race-role-assign")
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        delete_result, assign_result = [
            future.result() for future in [
                pool.submit(_delete), pool.submit(_assign)]]

    assert delete_result["status"] in (
        "verified", "conflict", "committed_unverified",
        "effect_unknown", "refused")
    assert assign_result["status"] in (
        "verified", "conflict", "committed_unverified",
        "effect_unknown", "refused")
    db = env.Session()
    try:
        role = db.query(AdminRole).filter(AdminRole.id == "role-2").first()
        assigned = db.query(AdminUser).filter(
            AdminUser.role_id == "role-2").all()
        if role is None:
            assert assigned == []
        if assigned:
            assert role is not None
    finally:
        db.close()


def test_concurrent_budget_partial_updates_do_not_lose_fields(env):
    _seed_budget(env, json.dumps({"budget_limit_usd": 10.0}))
    barrier = threading.Barrier(2)

    def _update(operation_id, limit=None, mode=None):
        db = env.Session()
        try:
            barrier.wait()
            return service.update_tenant_budget(
                db, actor=env.workspace_admin, tenant_id="tenant-1",
                budget_limit_usd=limit, enforcement_mode=mode,
                operation_id=operation_id)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        limit_result, mode_result = [
            future.result() for future in [
                pool.submit(_update, "race-budget-limit", 30.0, None),
                pool.submit(_update, "race-budget-mode", None, "hard_stop")]]

    final = _billing(env)
    assert final is not None
    if limit_result["status"] == "verified":
        assert final.get("budget_limit_usd") == 30.0
    else:
        assert final.get("budget_limit_usd") == 10.0
    if mode_result["status"] == "verified":
        assert final.get("enforcement", {}).get("mode") == "hard_stop"
    else:
        assert final.get("enforcement", {}).get("mode") != "hard_stop"


def test_fresh_session_consumers_observe_committed_role_permissions(env):
    client = _client(env)
    created = client.post(
        "/api/admin/roles?operation_id=perm-role-create",
        json={"name": "Permission Role", "permissions": {"users": True}})
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    updated = client.patch(
        f"/api/admin/roles/{role_id}?operation_id=perm-role-update",
        json={"permissions": {"users": False, "reports": True}})
    assert updated.status_code == 200, updated.text

    fresh = env.Session()
    try:
        persisted = fresh.query(AdminRole).filter(
            AdminRole.id == role_id).one()
        assert persisted.permissions == {
            "users": False, "reports": True}
    finally:
        fresh.close()

    read = client.get(f"/api/admin/roles/{role_id}")
    assert read.status_code == 200, read.text
    assert read.json()["permissions"] == {
        "users": False, "reports": True}


def test_fresh_session_budget_consumers_observe_committed_values(env):
    client = _client(env)
    updated = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=consumer-budget",
        json={"budget_limit_usd": 42.0, "enforcement_mode": "hard_stop"})
    assert updated.status_code == 200, updated.text

    from core.budget_enforcement_service import BudgetEnforcementService
    from core.spend_aggregation_service import SpendAggregationService

    fresh = env.Session()
    try:
        assert BudgetEnforcementService(fresh)._get_enforcement_mode(
            "tenant-1") == "hard_stop"
        assert SpendAggregationService(fresh)._budget_limit_from_setting(
            "tenant-1") == 42.0
    finally:
        fresh.close()


@pytest.mark.parametrize("bad_field", [
    "audit_id",
    "workspace_id",
    "security_level",
    "success",
    "event_type",
    "action",
    "user_id",
    "resource",
    "tenant_column",
    "metadata_actor_id",
    "metadata_target_id",
    "metadata_material_digest",
    "metadata_scope",
    "metadata_tenant_id",
    "metadata_operation_id_type",
    "metadata_result_digest_missing",
])
def test_audit_matrix_never_certifies_a_wrong_receipt(
        env, monkeypatch, bad_field):
    client = _client(env)
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if bad_field == "audit_id":
            row.id = "wrong-audit-id-" + row.id
        elif bad_field == "workspace_id":
            row.workspace_id = "tenant-1"
        elif bad_field == "security_level":
            row.security_level = "low"
        elif bad_field == "success":
            row.success = False
        elif bad_field == "event_type":
            row.event_type = "delete"
        elif bad_field == "action":
            row.action = "wrong-admin-action"
        elif bad_field == "user_id":
            row.user_id = "other-actor"
        elif bad_field == "resource":
            row.resource = "wrong-resource"
        elif bad_field == "tenant_column":
            row.tenant_id = "tenant-1"
        elif bad_field == "metadata_actor_id":
            metadata["actor_id"] = "other-actor"
        elif bad_field == "metadata_target_id":
            metadata["target_id"] = "other-target"
        elif bad_field == "metadata_material_digest":
            metadata["material_digest"] = "wrong-digest"
        elif bad_field == "metadata_scope":
            metadata["scope"] = "tenant"
        elif bad_field == "metadata_tenant_id":
            metadata["tenant_id"] = "tenant-1"
        elif bad_field == "metadata_operation_id_type":
            metadata["operation_id"] = 123
        elif bad_field == "metadata_result_digest_missing":
            metadata.pop("result_digest", None)
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = client.post(
        "/api/admin/roles",
        json={"name": f"Audit {bad_field}", "permissions": {"users": True}})
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["verification"]["status"] in (
        "refuted", "unavailable")


def test_noop_updates_do_not_create_operations(env):
    client = _client(env)
    role = client.patch("/api/admin/roles/role-1", json={})
    assert role.status_code == 200, role.text
    assert role.json()["verification"]["status"] == "no_change"
    assert role.json()["operation_id"] is None

    user = client.patch("/api/admin/users/admin-user-1", json={})
    assert user.status_code == 200, user.text
    assert user.json()["verification"]["status"] == "no_change"

    budget = client.put("/api/admin/tenants/tenant-1/budget", json={})
    assert budget.status_code == 200, budget.text
    assert budget.json()["verification"]["status"] == "no_change"


@pytest.mark.parametrize("value", ["Infinity", "-Infinity", "NaN"])
def test_non_finite_budget_values_are_rejected(env, value):
    before = _billing(env)
    body = '{"budget_limit_usd": %s}' % value
    response = _client(env).put(
        "/api/admin/tenants/tenant-1/budget",
        content=body,
        headers={"content-type": "application/json"})
    assert response.status_code == 422, response.text
    assert _billing(env) == before


@pytest.mark.parametrize("change", ["disable", "suspend"])
def test_disabled_actor_refuses_before_effect(env, change):
    client = _client(env)
    peer = env.Session()
    try:
        values = {"is_active": False} if change == "disable" else {
            "status": "suspended"}
        peer.execute(update(User).where(User.id == env.super_admin.id).values(
            **values))
        peer.commit()
    finally:
        peer.close()
    response = client.post(
        "/api/admin/roles",
        json={"name": f"Disabled {change}", "permissions": {"users": True}})
    assert response.status_code == 403, response.text
    assert _role_count(env, f"Disabled {change}") == 0


def test_later_role_target_revision_is_not_acknowledged(env):
    client = _client(env)
    created = client.post(
        "/api/admin/roles?operation_id=later-role-create",
        json={"name": "Later Role", "permissions": {"users": True}})
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    updated = client.patch(
        f"/api/admin/roles/{role_id}?operation_id=later-role-update",
        json={"name": "Later Role Renamed"})
    assert updated.status_code == 200, updated.text
    peer = env.Session()
    try:
        peer.execute(update(AdminRole).where(
            AdminRole.id == role_id).values(description="peer edit"))
        peer.commit()
    finally:
        peer.close()
    replay = client.patch(
        f"/api/admin/roles/{role_id}?operation_id=later-role-update",
        json={"name": "Later Role Renamed"})
    assert replay.status_code in (409, 503), replay.text
    assert replay.json().get("detail", {}).get(
        "verification", {}).get("status") != "already_applied"


def test_later_budget_revision_is_not_acknowledged(env):
    client = _client(env)
    updated = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=later-budget",
        json={"budget_limit_usd": 25.0})
    assert updated.status_code == 200, updated.text
    peer = env.Session()
    try:
        row = peer.query(TenantSetting).filter(
            TenantSetting.tenant_id == "tenant-1",
            TenantSetting.setting_key == "billing").one()
        row.setting_value = json.dumps({"budget_limit_usd": 99.0})
        peer.commit()
    finally:
        peer.close()
    replay = client.put(
        "/api/admin/tenants/tenant-1/budget?operation_id=later-budget",
        json={"budget_limit_usd": 25.0})
    assert replay.status_code == 503, replay.text
    assert replay.json()["detail"]["verification"]["status"] in (
        "refuted", "unavailable")


def test_role_and_user_delete_tombstones_replay(env):
    client = _client(env)
    role = client.post(
        "/api/admin/roles", json={
            "name": "Tombstone Role", "permissions": {"users": True}})
    assert role.status_code == 201, role.text
    role_id = role.json()["id"]
    deleted = client.delete(
        f"/api/admin/roles/{role_id}?operation_id=tombstone-role-delete")
    assert deleted.status_code == 200, deleted.text
    replay = client.delete(
        f"/api/admin/roles/{role_id}?operation_id=tombstone-role-delete")
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"

    user = client.post(
        "/api/admin/users", json={
            "email": "tombstone-admin@example.com", "name": "Tombstone",
            "password": "password123", "role_id": "role-1"})
    assert user.status_code == 201, user.text
    user_id = user.json()["id"]
    user_deleted = client.delete(
        f"/api/admin/users/{user_id}?operation_id=tombstone-user-delete")
    assert user_deleted.status_code == 200, user_deleted.text
    user_replay = client.delete(
        f"/api/admin/users/{user_id}?operation_id=tombstone-user-delete")
    assert user_replay.status_code == 200, user_replay.text
    assert user_replay.json()["verification"]["status"] == "already_applied"


def test_anonymous_admin_mutations_are_rejected(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    response = client.post(
        "/api/admin/roles",
        json={"name": "Anonymous Role", "permissions": {"users": True}})
    assert response.status_code in (401, 403), response.text
    assert _role_count(env, "Anonymous Role") == 0


def test_member_cannot_update_budget(env):
    member = SimpleNamespace(
        id="member-1", role="member", status="active", is_active=True)
    _as(env, member)
    response = _client(env).put(
        "/api/admin/tenants/tenant-1/budget",
        json={"budget_limit_usd": 10.0})
    assert response.status_code == 403, response.text
    assert _billing(env) is None
