"""Authority/current-scope controls for scoped durable memory writes.

These are the verifier's six two-session negatives plus active/current-scope
twins. A request-entry User object is only a snapshot: deactivation or tenant
reassignment after the document read must not let store/context/delete commit.
"""
from __future__ import annotations

import pytest
from sqlalchemy import update

import core.memory_write_service as service
from core.models import AuditLog, TenantSetting, User
from tests.test_memory_write_contract import (  # noqa: F401 — pytest fixture
    _audits,
    _setting_rows,
    env,
)


def _rows(env):
    return _setting_rows(env)


def _audit_count(env):
    return len(_audits(env))


def _change_actor(env, change):
    db = env.Session()
    try:
        values = (
            {"status": "inactive", "is_active": False}
            if change == "deactivate"
            else {"tenant_id": "tenant-2"}
        )
        db.execute(update(User).where(
            User.id == "user-1").values(**values))
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("operation", ["store", "context", "delete"])
@pytest.mark.parametrize("change", ["deactivate", "tenant_move"])
def test_authority_change_before_write_refuses(env, monkeypatch, operation, change):
    actor = env.actors["user-1"]
    client = env.client(actor)
    if operation == "delete":
        assert client.post(
            "/api/memory?operation_id=seed",
            json={"key": "held", "value": "keep-original"}).status_code == 200
    elif operation == "context":
        assert client.post(
            "/api/memory/context/session?operation_id=seed",
            json={"existing": "keep-original"}).status_code == 200

    before = [(row.id, row.setting_value) for row in _rows(env)]
    audits = _audit_count(env)
    original = service._read_setting
    moved = []

    def read_then_change(*args, **kwargs):
        result = original(*args, **kwargs)
        if not moved:
            _change_actor(env, change)
            moved.append(True)
        return result

    monkeypatch.setattr(service, "_read_setting", read_then_change)
    if operation == "store":
        response = client.post(
            "/api/memory?operation_id=stale-authority",
            json={"key": "held", "value": "must-not-write"})
    elif operation == "context":
        response = client.post(
            "/api/memory/context/session?operation_id=stale-authority",
            json={"new": "must-not-write"})
    else:
        response = client.delete(
            "/api/memory/held?operation_id=stale-authority")

    assert moved
    assert response.status_code in (401, 403, 409), response.text
    after = [(row.id, row.setting_value) for row in _rows(env)]
    assert before == after
    assert audits == _audit_count(env)


@pytest.mark.parametrize("operation", ["store", "context", "delete"])
def test_deactivated_actor_before_call_refuses(env, operation):
    client = env.client(env.actors["user-1"])
    if operation == "delete":
        assert client.post(
            "/api/memory", json={"key": "held", "value": "keep"}).status_code == 200
    elif operation == "context":
        assert client.post(
            "/api/memory/context/session", json={"a": 1}).status_code == 200
    before = [(row.id, row.setting_value) for row in _rows(env)]
    audits = _audit_count(env)
    _change_actor(env, "deactivate")

    if operation == "store":
        response = client.post(
            "/api/memory", json={"key": "held", "value": "must-not-write"})
    elif operation == "context":
        response = client.post(
            "/api/memory/context/session", json={"b": 2})
    else:
        response = client.delete("/api/memory/held")
    assert response.status_code == 403, response.text
    assert [(row.id, row.setting_value) for row in _rows(env)] == before
    assert audits == _audit_count(env)


def test_moved_actor_before_call_does_not_touch_old_scope(env):
    client = env.client(env.actors["user-1"])
    assert client.post(
        "/api/memory", json={"key": "old", "value": "old-value"}).status_code == 200
    old_scope = [
        row for row in _rows(env) if row.tenant_id == "default"]
    assert len(old_scope) == 1
    _change_actor(env, "tenant_move")

    # The current principal is now tenant-2. A new write lands in the current
    # scope; the old tenant's row is untouched.
    moved = client.post(
        "/api/memory", json={"key": "new", "value": "new-value"})
    assert moved.status_code == 200, moved.text
    rows = _rows(env)
    old_rows = [row for row in rows if row.tenant_id == "default"]
    new_rows = [row for row in rows if row.tenant_id == "tenant-2"]
    assert len(old_rows) == 1
    assert len(new_rows) == 1
    assert client.get("/api/memory/old").status_code == 404
    assert client.get("/api/memory/new").status_code == 200


def test_replay_under_unchanged_and_changed_authority(env):
    client = env.client(env.actors["user-1"])
    first = client.post(
        "/api/memory?operation_id=replay-authority",
        json={"key": "replay", "value": "v"})
    assert first.status_code == 200, first.text
    replay = client.post(
        "/api/memory?operation_id=replay-authority",
        json={"key": "replay", "value": "v"})
    assert replay.status_code == 200
    assert replay.json()["verification"]["status"] == "already_applied"
    audits = _audit_count(env)

    _change_actor(env, "deactivate")
    denied = client.post(
        "/api/memory?operation_id=replay-authority",
        json={"key": "replay", "value": "v"})
    assert denied.status_code == 403, denied.text
    assert audits == _audit_count(env)

    db = env.Session()
    try:
        db.execute(update(User).where(
            User.id == "user-1").values(
                status="active", is_active=True, tenant_id="tenant-2"))
        db.commit()
    finally:
        db.close()
    conflict = client.post(
        "/api/memory?operation_id=replay-authority",
        json={"key": "replay", "value": "v"})
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["error"]["code"] == (
        "OPERATION_CONFLICT")
    assert audits == _audit_count(env)


def test_bootstrap_tenantless_scope_is_stable(env):
    db = env.Session()
    try:
        bootstrap = User(
            id="bootstrap", tenant_id=None, email="bootstrap@example.com",
            first_name="Boot", last_name="Strap", role="member",
            status="active", is_active=True)
        db.add(bootstrap)
        db.commit()
        db.refresh(bootstrap)
    finally:
        db.close()
    client = env.client(bootstrap)
    stored = client.post(
        "/api/memory", json={"key": "bootstrap-key", "value": "v"})
    assert stored.status_code == 200, stored.text
    rows = _rows(env)
    assert len(rows) == 1
    assert rows[0].tenant_id == "default"
    assert client.get("/api/memory/bootstrap-key").json()["value"] == "v"


def test_fresh_session_reads_after_authority_change(env):
    client = env.client(env.actors["user-1"])
    assert client.post(
        "/api/memory", json={"key": "read", "value": "v"}).status_code == 200
    assert client.post(
        "/api/memory/context/session", json={"topic": "math"}).status_code == 200
    _change_actor(env, "deactivate")
    assert client.get("/api/memory/read").status_code == 404
    assert client.get("/api/memory/search?q=v").json()["metadata"]["count"] == 0
    assert client.get("/api/memory/context/session").json()["context"] == {}
