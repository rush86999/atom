"""Failure-first contracts for verified workflow-template create/update."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.workflow_template_write_service as service
from api.workflow_template_routes import router as template_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import AuditLog, Tenant, User, Workspace
from core.workflow_template_system import WorkflowTemplate, WorkflowTemplateManager


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/workflow-template.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        User(
            id="lead-1", tenant_id="t1", workspace_id="ws1",
            email="lead@example.com", first_name="Lead", last_name="One",
            role="team_lead", status="active", is_active=True),
        User(
            id="admin-1", tenant_id="t1", workspace_id="ws1",
            email="admin@example.com", first_name="Admin", last_name="One",
            role="admin", status="active", is_active=True),
        User(
            id="member-1", tenant_id="t1", workspace_id="ws1",
            email="member@example.com", first_name="Member", last_name="One",
            role="member", status="active", is_active=True),
    ])
    seed.commit()
    seed.close()

    manager = WorkflowTemplateManager(
        template_dir=str(tmp_path / "templates"))

    app = FastAPI()
    app.include_router(template_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    import api.workflow_template_routes as routes_module

    monkeypatch.setattr(
        routes_module, "get_template_manager", lambda: manager)

    def client(user: User):
        scoped = FastAPI()
        scoped.include_router(template_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "lead-1": Session().query(User).filter(User.id == "lead-1").one(),
        "admin-1": Session().query(User).filter(User.id == "admin-1").one(),
        "member-1": Session().query(User).filter(User.id == "member-1").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, manager=manager,
        directory=Path(tmp_path / "templates"),
    )


def _audits(env, operation_id=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _payload(env, template_id):
    path = env.directory / f"{template_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _write_peer(env, template_id, name, updated_at="2099-01-01T00:00:00"):
    path = env.directory / f"{template_id}.json"
    data = json.loads(path.read_text())
    data["name"] = name
    data["updated_at"] = updated_at
    path.write_text(json.dumps(data, indent=2))
    return data


def _create(client, operation_id="create-one", name="Original Template"):
    response = client.post(
        f"/api/workflow-templates/?operation_id={operation_id}",
        json={
            "name": name,
            "description": "A template",
            "category": "automation",
            "complexity": "intermediate",
            "tags": ["one"],
            "steps": [{
                "step_id": "s1", "name": "Step One",
                "step_type": "agent_execution",
                "parameters": [{"name": "input"}],
                "depends_on": [],
            }],
        })
    assert response.status_code == 200, response.text
    return response.json()["template_id"]


def test_create_template_with_audit_and_no_raw_content(env, caplog):
    response = env.client(env.actors["lead-1"]).post(
        "/api/workflow-templates/?operation_id=create-one",
        json={
            "name": "SECRET_TEMPLATE_NAME",
            "description": "SECRET_DESCRIPTION",
            "category": "automation",
            "complexity": "intermediate",
            "tags": ["secret-tag"],
            "steps": [{
                "step_id": "s1", "name": "SECRET_STEP",
                "step_type": "agent_execution",
                "parameters": [{"name": "SECRET_PARAMETER"}],
                "depends_on": [],
            }],
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["verification"]["status"] == "verified"
    assert body["operation_id"] == "workflow-template:create:create-one"
    template_id = body["template_id"]
    payload = _payload(env, template_id)
    assert payload["name"] == "SECRET_TEMPLATE_NAME"
    assert payload["steps"][0]["step_id"] == "s1"

    audits = _audits(env, "workflow-template:create:create-one")
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "workflow_template_created"
    assert audit.user_id == "lead-1"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == template_id
    for secret in (
        "SECRET_TEMPLATE_NAME", "SECRET_DESCRIPTION",
        "secret-tag", "SECRET_STEP", "SECRET_PARAMETER",
    ):
        assert secret not in (audit.metadata_json or "")
        assert secret not in (audit.description or "")
        assert secret not in caplog.text


def test_member_cannot_create_or_update(env):
    client = env.client(env.actors["member-1"])
    assert client.post("/api/workflow-templates/", json={
        "name": "Denied", "description": "d"}).status_code == 403
    template_id = _create(env.client(env.actors["lead-1"]))
    assert client.put(
        f"/api/workflow-templates/{template_id}",
        json={"name": "Denied"}).status_code == 403


def test_create_replay_changed_material_and_missing_target(env):
    client = env.client(env.actors["admin-1"])
    template_id = _create(client, operation_id="create-replay")
    replay = client.post(
        "/api/workflow-templates/?operation_id=create-replay",
        json={
            "name": "Original Template",
            "description": "A template",
            "category": "automation",
            "complexity": "intermediate",
            "tags": ["one"],
            "steps": [{
                "step_id": "s1", "name": "Step One",
                "step_type": "agent_execution",
                "parameters": [{"name": "input"}],
                "depends_on": [],
            }],
        })
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = client.post(
        "/api/workflow-templates/?operation_id=create-replay",
        json={"name": "Different", "description": "d"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    (env.directory / f"{template_id}.json").unlink()
    missing = client.post(
        "/api/workflow-templates/?operation_id=create-replay",
        json={
            "name": "Original Template",
            "description": "A template",
            "category": "automation",
            "complexity": "intermediate",
            "tags": ["one"],
            "steps": [{
                "step_id": "s1", "name": "Step One",
                "step_type": "agent_execution",
                "parameters": [{"name": "input"}],
                "depends_on": [],
            }],
        })
    assert missing.status_code == 503, missing.text
    assert missing.json()["detail"]["error"]["code"] == (
        "WORKFLOW_TEMPLATE_COMMITTED_UNVERIFIED")


def test_update_template_with_audit_and_preserved_material(env):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    before = _payload(env, template_id)
    response = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=update-one",
        json={"name": "Renamed Template", "tags": ["two", "three"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["template"]["name"] == "Renamed Template"
    assert body["template"]["tags"] == ["two", "three"]
    assert body["template"]["description"] == before["description"]
    assert body["template"]["steps"][0]["step_id"] == "s1"
    assert body["verification"]["status"] == "verified"

    audit = _audits(env, "workflow-template:update:update-one")[0]
    assert audit.action == "workflow_template_updated"
    metadata = json.loads(audit.metadata_json)
    assert metadata["target_id"] == template_id
    assert "Renamed" not in (audit.metadata_json or "")


def test_matching_update_is_no_change(env):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    before = len(_audits(env))
    response = client.put(
        f"/api/workflow-templates/{template_id}",
        json={"name": "Original Template"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification"]["status"] == "no_change"
    assert body["verification"]["effect"] == "none"
    assert len(_audits(env)) == before


def test_create_existing_id_is_conflict(env, monkeypatch):
    client = env.client(env.actors["lead-1"])
    fixed = WorkflowTemplate(
        name="Fixed", description="existing", category="automation",
        complexity="intermediate")
    fixed.template_id = "fixed-template"
    monkeypatch.setattr(service, "_build_template", lambda payload: fixed)
    path = env.directory / "fixed-template.json"
    path.write_text(json.dumps(
        service._stable_payload(fixed), indent=2))
    before = path.read_text()

    response = client.post(
        "/api/workflow-templates/?operation_id=create-collision",
        json={"name": "Fixed", "description": "new"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "TEMPLATE_EXISTS"
    assert path.read_text() == before
    assert _audits(env) == []


def test_create_audit_rollback_removes_new_file(env, monkeypatch):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    response = env.client(env.actors["lead-1"]).post(
        "/api/workflow-templates/?operation_id=create-rollback",
        json={"name": "Rollback", "description": "d"})
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "WORKFLOW_TEMPLATE_TRANSACTION_ROLLED_BACK")
    assert detail["verification"]["effect"] == "none"
    assert list(env.directory.glob("template_*.json")) == []
    assert _audits(env) == []


def test_update_missing_and_empty_body(env):
    client = env.client(env.actors["lead-1"])
    assert client.put(
        "/api/workflow-templates/missing-id",
        json={"name": "Nope"}).status_code == 404
    template_id = _create(client)
    assert client.put(
        f"/api/workflow-templates/{template_id}",
        json={}).status_code == 422
    assert _payload(env, template_id)["name"] == "Original Template"


def test_stale_peer_edit_before_claim_refuses(env, monkeypatch):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    original = service._current_template
    calls = {"count": 0}

    def peer_then_load(directory, target_id):
        calls["count"] += 1
        if calls["count"] == 2 and target_id == template_id:
            _write_peer(env, template_id, "Peer Name")
        return original(directory, target_id)

    monkeypatch.setattr(service, "_current_template", peer_then_load)
    response = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=stale",
        json={"name": "Loser"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    assert _payload(env, template_id)["name"] == "Peer Name"
    assert _audits(env, "workflow-template:update:stale") == []


def test_update_replay_changed_material_and_later_revision(env):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    first = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=update-replay",
        json={"name": "Replay Name"})
    assert first.status_code == 200, first.text
    replay = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=update-replay",
        json={"name": "Replay Name"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 2  # create + update

    changed = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=update-replay",
        json={"name": "Different Name"})
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    _write_peer(env, template_id, "Later Name")
    later = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=update-replay",
        json={"name": "Replay Name"})
    assert later.status_code == 503, later.text
    assert later.json()["detail"]["error"]["code"] == (
        "WORKFLOW_TEMPLATE_COMMITTED_UNVERIFIED")


@pytest.mark.parametrize("change", ["deactivate", "demote"])
def test_authority_change_before_claim_refuses(env, monkeypatch, change):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    original = service._current_template
    changed = {"done": False}

    def load_then_change(directory, target_id):
        row = original(directory, target_id)
        if not changed["done"] and target_id == template_id:
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate"
                    else {"role": "member"})
                peer.execute(update(User).where(
                    User.id == "lead-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_current_template", load_then_change)
    response = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=authority",
        json={"name": "Nope"})
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _payload(env, template_id)["name"] == "Original Template"
    assert _audits(env, "workflow-template:update:authority") == []


def test_audit_rollback_restores_prior_template(env, monkeypatch):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    prior = (env.directory / f"{template_id}.json").read_text()
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    response = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=rollback",
        json={"name": "Rollback Name"})
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "WORKFLOW_TEMPLATE_TRANSACTION_ROLLED_BACK")
    assert detail["verification"]["effect"] == "none"
    assert (env.directory / f"{template_id}.json").read_text() == prior
    assert _audits(env, "workflow-template:update:rollback") == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)

    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = client.put(
        f"/api/workflow-templates/{template_id}?operation_id=readback",
        json={"name": "Readback Name"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "WORKFLOW_TEMPLATE_COMMITTED_UNVERIFIED")
    assert detail["verification"]["effect"] == "committed"
    assert _payload(env, template_id)["name"] == "Readback Name"
    assert len(_audits(env, "workflow-template:update:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-TEMPLATE-SECRET")

        db.commit = lost_commit
        result = service.update_template(
            db, actor=env.actors["lead-1"], template_id=template_id,
            updates={"name": "Lost Name"},
            operation_id="lost-confirmation", manager=env.manager)
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == (
        "workflow-template:update:lost-confirmation")
    assert "SYNTHETIC-TEMPLATE-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-TEMPLATE-SECRET" not in caplog.text


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "resource",
    "success",
    "security_level",
    "metadata_target_id",
    "metadata_prior_digest",
    "metadata_result_digest",
    "metadata_request_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    client = env.client(env.actors["lead-1"])
    template_id = _create(client)
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "member-1"
        elif field == "tenant_id":
            row.tenant_id = "t2"
        elif field == "resource":
            row.resource = "workflow_template:other"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = client.put(
        f"/api/workflow-templates/{template_id}"
        f"?operation_id=audit-{field}",
        json={"name": f"Audit {field}"})
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "WORKFLOW_TEMPLATE_COMMITTED_UNVERIFIED")
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_path_traversal_template_id_is_not_found(env):
    response = env.client(env.actors["lead-1"]).put(
        "/api/workflow-templates/..%2F..%2Fetc%2Fpasswd",
        json={"name": "Nope"})
    assert response.status_code == 404, response.text
    assert _audits(env) == []


def test_anonymous_requests_are_refused(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.post(
        "/api/workflow-templates/",
        json={"name": "Anon", "description": "d"}).status_code == 401
    assert _audits(env) == []
