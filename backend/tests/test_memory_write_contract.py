"""Failure-first contracts for scoped durable memory and context writes."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.memory_write_service as service
from api.memory_routes import router as memory_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AuditLog, Tenant, TenantSetting, User


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/memory-contract.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    tenants = [
        Tenant(id="default", name="Personal", subdomain="personal"),
        Tenant(id="tenant-2", name="Tenant Two", subdomain="tenant-two"),
    ]
    users = [
        User(
            id="user-1", tenant_id="default", email="u1@example.com",
            first_name="User", last_name="One", role="member",
            status="active", is_active=True),
        User(
            id="user-2", tenant_id="default", email="u2@example.com",
            first_name="User", last_name="Two", role="member",
            status="active", is_active=True),
        User(
            id="user-3", tenant_id="tenant-2", email="u3@example.com",
            first_name="User", last_name="Three", role="member",
            status="active", is_active=True),
    ]
    seed.add_all(tenants + users)
    seed.commit()
    seed.close()

    app = FastAPI()
    app.include_router(memory_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        # A per-user app keeps the dependency override scoped to that actor,
        # so two clients used in one test cannot race on the same global
        # override.
        scoped = FastAPI()
        scoped.include_router(memory_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "user-1": Session().query(User).filter(User.id == "user-1").one(),
        "user-2": Session().query(User).filter(User.id == "user-2").one(),
        "user-3": Session().query(User).filter(User.id == "user-3").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
    )


def _setting_rows(env):
    db = env.Session()
    try:
        return db.query(TenantSetting).order_by(
            TenantSetting.created_at).all()
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


def _op(suffix, action="store"):
    return f"memory:{action}:{suffix}"


def _peer_update(env, setting_key, mutate):
    db = env.Session()
    try:
        row = db.query(TenantSetting).filter(
            TenantSetting.setting_key == setting_key).first()
        assert row is not None
        document = json.loads(row.setting_value)
        mutate(document)
        row.setting_value = json.dumps(
            document, sort_keys=True, separators=(",", ":"))
        db.commit()
    finally:
        db.close()


def test_store_roundtrip_audit_and_safe_receipt(env):
    response = env.client(env.actors["user-1"]).post(
        "/api/memory?operation_id=store-one",
        json={"key": "k1", "value": {"a": 1}, "metadata": {"m": 2}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["key"] == "k1"
    assert body["value"] == {"a": 1}
    assert body["metadata"] == {"m": 2}
    assert body["verification"]["status"] == "verified"
    assert body["operation_id"] == _op("store-one")

    rows = _setting_rows(env)
    assert len(rows) == 1
    assert rows[0].tenant_id == "default"
    assert rows[0].setting_key.startswith("memory:v1:")
    document = json.loads(rows[0].setting_value)
    assert document["schema"] == "atom-memory-entry-1"
    assert document["scope"] == {
        "tenant_id": "default", "user_id": "user-1", "agent_id": None}
    assert document["key"] == "k1"
    assert document["value"] == {"a": 1}
    assert document["revision"] == 1

    read = env.client(env.actors["user-1"]).get("/api/memory/k1")
    assert read.status_code == 200, read.text
    assert read.json()["value"] == {"a": 1}

    audits = _audits(env, _op("store-one"))
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "memory_stored"
    assert audit.user_id == "user-1"
    assert audit.tenant_id == "default"
    assert audit.workspace_id is None
    assert audit.success is True
    metadata = json.loads(audit.metadata_json)
    assert metadata["setting_key"] == rows[0].setting_key
    assert metadata["scope_json"] == json.dumps(
        {"agent_id": None, "tenant_id": "default", "user_id": "user-1"},
        sort_keys=True, separators=(",", ":"))
    assert "k1" not in audit.metadata_json
    assert '{"a":1}' not in audit.metadata_json
    assert '"m":2' not in audit.metadata_json


def test_scope_isolation_across_users_tenants_and_agents(env):
    first = env.client(env.actors["user-1"])
    second = env.client(env.actors["user-2"])
    third = env.client(env.actors["user-3"])

    assert first.post("/api/memory", json={
        "key": "shared", "value": "user-one"}).status_code == 200
    assert second.post("/api/memory", json={
        "key": "shared", "value": "user-two"}).status_code == 200
    assert third.post("/api/memory", json={
        "key": "shared", "value": "tenant-two"}).status_code == 200

    assert first.get("/api/memory/shared").json()["value"] == "user-one"
    assert second.get("/api/memory/shared").json()["value"] == "user-two"
    assert third.get("/api/memory/shared").json()["value"] == "tenant-two"

    assert first.get("/api/memory/search?q=user").json()["data"][0][
        "value"] == "user-one"
    assert second.get("/api/memory/search?q=user").json()["data"][0][
        "value"] == "user-two"

    assert first.delete("/api/memory/shared").status_code == 200
    assert second.get("/api/memory/shared").json()["value"] == "user-two"

    assert first.post(
        "/api/memory?agent_id=agent-a",
        json={"key": "agent-key", "value": "agent-a-value"}).status_code == 200
    assert first.get("/api/memory/agent-key").status_code == 404
    assert first.get(
        "/api/memory/agent-key?agent_id=agent-a").json()["value"] == (
            "agent-a-value")
    assert second.get(
        "/api/memory/agent-key?agent_id=agent-a").status_code == 404
    assert third.get(
        "/api/memory/agent-key?agent_id=agent-a").status_code == 404


def test_store_update_and_stale_prior_refuses(env, monkeypatch):
    client = env.client(env.actors["user-1"])
    assert client.post("/api/memory", json={
        "key": "k2", "value": "first"}).status_code == 200
    assert client.post("/api/memory", json={
        "key": "k2", "value": "second"}).status_code == 200

    rows = _setting_rows(env)
    setting_key = rows[0].setting_key
    original = service._read_setting
    state = {"changed": False}

    def read_then_peer_change(db, tenant_id, key):
        snapshot = original(db, tenant_id, key)
        if not state["changed"] and key == setting_key:
            state["changed"] = True
            _peer_update(env, setting_key, lambda doc: doc.update(
                {"value": "peer", "revision": doc["revision"] + 1}))
        return snapshot

    monkeypatch.setattr(
        service, "_read_setting", read_then_peer_change)
    stale = client.post("/api/memory", json={
        "key": "k2", "value": "third"})
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["error"]["code"] == "STALE_TARGET"
    assert detail["verification"]["effect"] == "none"
    assert client.get("/api/memory/k2").json()["value"] == "peer"
    assert len(_audits(env)) == 2


def test_store_replay_changed_material_and_later_revision(env):
    client = env.client(env.actors["user-1"])
    first = client.post(
        "/api/memory?operation_id=replay", json={
            "key": "k3", "value": "one"})
    assert first.status_code == 200, first.text
    replay = client.post(
        "/api/memory?operation_id=replay", json={
            "key": "k3", "value": "one"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = client.post(
        "/api/memory?operation_id=replay", json={
            "key": "k3", "value": "different"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    assert len(_audits(env)) == 1

    _peer_update(env, _setting_rows(env)[0].setting_key, lambda doc: doc.update(
        {"value": "later", "revision": doc["revision"] + 1}))
    later = client.post(
        "/api/memory?operation_id=replay", json={
            "key": "k3", "value": "one"})
    assert later.status_code == 503, later.text
    detail = later.json()["detail"]
    assert detail["error"]["code"] == "MEMORY_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert detail["verification"]["replay"] == "do_not_repeat"


def test_context_merge_replay_competing_and_scope_isolation(env, monkeypatch):
    first = env.client(env.actors["user-1"])
    second = env.client(env.actors["user-2"])
    assert first.post(
        "/api/memory/context/s1?operation_id=ctx-one",
        json={"topic": "math"}).status_code == 200
    replay = first.post(
        "/api/memory/context/s1?operation_id=ctx-one",
        json={"topic": "math"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"

    assert first.post(
        "/api/memory/context/s1?operation_id=ctx-two",
        json={"difficulty": "hard"}).status_code == 200
    context = first.get("/api/memory/context/s1").json()["context"]
    assert context["topic"] == "math"
    assert context["difficulty"] == "hard"
    assert "_updated_at" in context
    assert second.get("/api/memory/context/s1").json()["context"] == {}

    later_replay = first.post(
        "/api/memory/context/s1?operation_id=ctx-one",
        json={"topic": "math"})
    assert later_replay.status_code == 503, later_replay.text
    assert later_replay.json()["detail"]["error"]["code"] == (
        "MEMORY_COMMITTED_UNVERIFIED")

    rows = [row for row in _setting_rows(env)
            if row.setting_key.startswith("memory-context:v1:")]
    setting_key = rows[0].setting_key
    original = service._read_setting
    state = {"changed": False}

    def read_then_peer_change(db, tenant_id, key):
        snapshot = original(db, tenant_id, key)
        if not state["changed"] and key == setting_key:
            state["changed"] = True
            _peer_update(env, setting_key, lambda doc: doc.update({
                "context": {**doc["context"], "peer": True},
                "revision": doc["revision"] + 1,
            }))
        return snapshot

    monkeypatch.setattr(
        service, "_read_setting", read_then_peer_change)
    competing = first.post(
        "/api/memory/context/s1", json={"late": True})
    assert competing.status_code == 409, competing.text
    assert competing.json()["detail"]["error"]["code"] == "STALE_TARGET"
    context = first.get("/api/memory/context/s1").json()["context"]
    assert context["peer"] is True
    assert context["topic"] == "math"
    assert "late" not in context


def test_delete_replay_missing_and_stale(env, monkeypatch):
    client = env.client(env.actors["user-1"])
    assert client.post("/api/memory", json={
        "key": "k4", "value": "one"}).status_code == 200
    deleted = client.delete("/api/memory/k4?operation_id=del-one")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["message"] == "Memory key 'k4' deleted"
    assert client.get("/api/memory/k4").status_code == 404

    replay = client.delete("/api/memory/k4?operation_id=del-one")
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["verification"]["status"] == "already_applied"
    assert client.delete("/api/memory/missing").status_code == 404

    assert client.post("/api/memory", json={
        "key": "k5", "value": "first"}).status_code == 200
    setting_key = [
        row.setting_key for row in _setting_rows(env)
        if row.setting_key.startswith("memory:v1:")
    ][0]
    original = service._read_setting
    state = {"changed": False}

    def read_then_peer_change(db, tenant_id, key):
        snapshot = original(db, tenant_id, key)
        if not state["changed"] and key == setting_key:
            state["changed"] = True
            _peer_update(env, setting_key, lambda doc: doc.update(
                {"value": "peer", "revision": doc["revision"] + 1}))
        return snapshot

    monkeypatch.setattr(
        service, "_read_setting", read_then_peer_change)
    stale = client.delete("/api/memory/k5")
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert client.get("/api/memory/k5").json()["value"] == "peer"


@pytest.mark.parametrize("kind", ["store", "context", "delete"])
def test_confirmed_audit_rollback_reports_effect_none(
        env, monkeypatch, kind):
    client = env.client(env.actors["user-1"])
    if kind == "delete":
        assert client.post("/api/memory", json={
            "key": "rollback-delete", "value": "keep"}).status_code == 200
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    if kind == "store":
        response = client.post(
            "/api/memory?operation_id=rollback-store",
            json={"key": "rollback-store", "value": "x"})
    elif kind == "context":
        response = client.post(
            "/api/memory/context/rollback-context?operation_id=rollback-context",
            json={"x": 1})
    else:
        response = client.delete(
            "/api/memory/rollback-delete?operation_id=rollback-delete")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "MEMORY_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert detail["verification"]["status"] == "refused"
    if kind == "store":
        assert client.get("/api/memory/rollback-store").status_code == 404
    elif kind == "context":
        assert client.get(
            "/api/memory/context/rollback-context").json()["context"] == {}
    else:
        assert client.get("/api/memory/rollback-delete").json()[
            "value"] == "keep"


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client(env.actors["user-1"]).post(
        "/api/memory?operation_id=readback",
        json={"key": "readback", "value": "x"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "MEMORY_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert detail["operation_id"] == _op("readback")
    assert len(_audits(env, _op("readback"))) == 1
    assert any(row.setting_key.startswith("memory:v1:")
               for row in _setting_rows(env))


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-MEMORY-SECRET")

        db.commit = lost_commit
        result = service.store_memory(
            db, actor=env.actors["user-1"], key="lost",
            value="x", operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == _op("lost-confirmation")
    assert "SYNTHETIC-MEMORY-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-MEMORY-SECRET" not in caplog.text
    assert _audits(env) == []


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "workspace_id",
    "success",
    "security_level",
    "metadata_scope_json",
    "metadata_setting_key",
    "metadata_target_digest",
    "metadata_request_digest",
    "metadata_prior_digest",
    "metadata_result_digest",
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
            row.tenant_id = "tenant-2"
        elif field == "workspace_id":
            row.workspace_id = "workspace-x"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "metadata_scope_json":
            metadata["scope_json"] = "wrong-scope"
        elif field == "metadata_setting_key":
            metadata["setting_key"] = "wrong-setting-key"
        elif field == "metadata_target_digest":
            metadata["target_digest"] = "wrong-target"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client(env.actors["user-1"]).post(
        f"/api/memory?operation_id=audit-{field}",
        json={"key": f"audit-{field}", "value": "x"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "MEMORY_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_raw_memory_material_is_absent_from_audit_and_logs(env, caplog):
    value = "SECRET_MEMORY_VALUE_123"
    metadata = {"secret_metadata": "SECRET_METADATA_456"}
    response = env.client(env.actors["user-1"]).post(
        "/api/memory?operation_id=secret-store",
        json={"key": "SECRET_MEMORY_KEY", "value": value,
              "metadata": metadata})
    assert response.status_code == 200, response.text
    assert value in response.text
    audit = _audits(env, _op("secret-store"))[0]
    assert value not in (audit.metadata_json or "")
    assert "SECRET_METADATA_456" not in (audit.metadata_json or "")
    assert "SECRET_MEMORY_KEY" not in (audit.metadata_json or "")
    assert value not in (audit.description or "")
    assert "SECRET_METADATA_456" not in caplog.text
    assert "SECRET_MEMORY_KEY" not in caplog.text


def test_anonymous_requests_are_refused(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.get("/api/memory/k1").status_code == 401
    assert client.post("/api/memory", json={
        "key": "anon", "value": "x"}).status_code == 401
    assert client.delete("/api/memory/anon").status_code == 401
    assert client.get("/api/memory/search?q=x").status_code == 401
