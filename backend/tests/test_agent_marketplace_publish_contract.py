"""Failure-first contracts for verified agent-marketplace publication."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.agent_marketplace_write_service as service
from api.agent_marketplace_routes import router as marketplace_router
from core.auth import get_current_user
from core.database import Base, get_db
from core.models import (
    AgentRegistry,
    AgentTemplate,
    AuditLog,
    GoalRun,
    Playbook,
    Tenant,
    User,
    Workspace,
)


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/agent-marketplace.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        User(
            id="owner-1", tenant_id="t1", workspace_id="ws1",
            email="owner@example.com", first_name="Owner", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="admin-1", tenant_id="t1", workspace_id="ws1",
            email="admin@example.com", first_name="Admin", last_name="One",
            role="admin", status="active", is_active=True),
        User(
            id="member-1", tenant_id="t1", workspace_id="ws1",
            email="member@example.com", first_name="Member", last_name="One",
            role="member", status="active", is_active=True),
    ])
    seed.add_all([
        AgentRegistry(
            id="agent-quota", name="Quota Agent", category="Sales",
            specialty="sales", module_path="agents.sales",
            class_name="SalesAgent", status="supervised", user_id="owner-1",
            workspace_id="ws1", tenant_id="t1",
            configuration={"system_prompt": "SECRET_SYSTEM_PROMPT"}),
        AgentRegistry(
            id="agent-fresh", name="Fresh Agent", category="Sales",
            module_path="agents.sales", class_name="FreshAgent",
            status="student", user_id="owner-1", workspace_id="ws1",
            tenant_id="t1", configuration={}),
        AgentRegistry(
            id="agent-managed", name="Managed Agent", category="Sales",
            module_path="agents.sales", class_name="ManagedAgent",
            status="intern", user_id="owner-1", workspace_id="ws1",
            tenant_id="t1",
            configuration={"marketplace_managed": True,
                           "template_id": "remote-listing"}),
    ])
    seed.add(GoalRun(
        id="run-achieved", tenant_id="t1", workspace_id="ws1",
        goal_id="g1", agent_id="agent-quota", status="achieved",
        supervision_mode="shadow", role="sales",
        plan=[{"id": "s1", "kind": "canvas_work", "title": "Research"}],
        steps_executed=1, human_interventions=0, decision_log=[]))
    seed.add(Playbook(
        id="pb-1", tenant_id="t1", workspace_id="ws1", name="Quote process",
        description="How we quote", trigger_canvas_type="email",
        trigger_keywords=["quote"], approval_state="approved",
        steps=["Research", "Draft", "Review"]))
    seed.commit()
    seed.close()

    app = FastAPI()
    app.include_router(marketplace_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        scoped = FastAPI()
        scoped.include_router(marketplace_router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "owner-1": Session().query(User).filter(User.id == "owner-1").one(),
        "admin-1": Session().query(User).filter(User.id == "admin-1").one(),
        "member-1": Session().query(User).filter(User.id == "member-1").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors,
    )


def _templates(env, template_id=None):
    db = env.Session()
    try:
        query = db.query(AgentTemplate)
        if template_id is not None:
            query = query.filter(AgentTemplate.id == template_id)
        return query.all()
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


def _publish(client, agent_id="agent-quota", operation_id="publish-one",
             price=0.0, description="A listing"):
    return client.post(
        f"/api/agent-marketplace/agents/{agent_id}/publish"
        f"?operation_id={operation_id}",
        json={"price": price, "description": description})


def test_owner_publishes_listing_with_audit_and_no_raw_prompt(env, caplog):
    response = _publish(env.client(env.actors["owner-1"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["verification"]["status"] == "verified"
    assert body["operation_id"] == (
        "agent-marketplace:publish:publish-one")
    template_id = body["template_id"]
    listing = _templates(env, template_id)[0]
    assert listing.tenant_id == "t1"
    assert listing.author_id == "owner-1"
    assert listing.name == "Quota Agent"
    assert listing.price == 0.0
    assert listing.is_public is True and listing.is_approved is True
    assert listing.verified_record["runs"]["achieved"] == 1

    audit = _audits(env, "agent-marketplace:publish:publish-one")[0]
    assert audit.action == "agent_listing_published"
    assert audit.user_id == "owner-1"
    metadata = json.loads(audit.metadata_json)
    assert metadata["source_agent_id"] == "agent-quota"
    assert metadata["target_id"] == template_id
    for secret in ("SECRET_SYSTEM_PROMPT", "Quota Agent", "system_prompt"):
        assert secret not in (audit.metadata_json or "")
        assert secret not in (audit.description or "")
        assert secret not in caplog.text


def test_admin_can_publish_and_member_cannot(env):
    response = _publish(
        env.client(env.actors["admin-1"]), operation_id="admin-publish")
    assert response.status_code == 200, response.text
    assert _templates(env, response.json()["template_id"])[0].author_id == (
        "admin-1")

    denied = _publish(
        env.client(env.actors["member-1"]), operation_id="denied")
    assert denied.status_code == 403, denied.text
    assert len(_templates(env)) == 1
    assert len(_audits(env)) == 1


def test_missing_managed_and_paid_gate(env):
    owner = env.client(env.actors["owner-1"])
    assert _publish(owner, agent_id="missing", operation_id="missing").status_code == 404
    assert _publish(
        owner, agent_id="agent-managed",
        operation_id="managed").status_code == 409

    paid = _publish(
        owner, agent_id="agent-fresh", operation_id="paid-gate", price=5)
    assert paid.status_code == 409, paid.text
    detail = json.dumps(paid.json()["detail"])
    assert "achieved" in detail
    assert _templates(env) == []
    assert _audits(env) == []


def test_paid_publish_with_achieved_run_succeeds(env):
    response = _publish(
        env.client(env.actors["owner-1"]), operation_id="paid",
        price=19.0)
    assert response.status_code == 200, response.text
    assert response.json()["verified_record"]["runs"]["achieved"] == 1
    assert _templates(env, response.json()["template_id"])[0].price == 19.0


def test_replay_changed_material_and_missing_listing(env):
    client = env.client(env.actors["owner-1"])
    first = _publish(client, operation_id="replay")
    assert first.status_code == 200, first.text
    template_id = first.json()["template_id"]

    replay = _publish(client, operation_id="replay")
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = _publish(client, operation_id="replay", price=7)
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    db = env.Session()
    try:
        row = db.query(AgentTemplate).filter(
            AgentTemplate.id == template_id).one()
        db.delete(row)
        db.commit()
    finally:
        db.close()
    missing = _publish(client, operation_id="replay")
    assert missing.status_code == 503, missing.text
    assert missing.json()["detail"]["error"]["code"] == (
        "AGENT_MARKETPLACE_COMMITTED_UNVERIFIED")


def test_stale_source_before_claim_refuses(env, monkeypatch):
    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if not changed["done"] and agent_id == "agent-quota":
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == agent_id).values(
                        name="Peer Renamed Agent"))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _publish(
        env.client(env.actors["owner-1"]), operation_id="stale")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_SOURCE"
    assert _templates(env) == []
    assert _audits(env) == []


@pytest.mark.parametrize("change", ["deactivate", "demote"])
def test_authority_change_before_claim_refuses(env, monkeypatch, change):
    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if not changed["done"] and agent_id == "agent-quota":
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate"
                    else {"role": "member"})
                peer.execute(update(User).where(
                    User.id == "admin-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return row

    monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _publish(
        env.client(env.actors["admin-1"]), operation_id="authority")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert _templates(env) == []
    assert _audits(env) == []


def test_audit_rollback_reports_effect_none(env, monkeypatch):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    response = _publish(
        env.client(env.actors["owner-1"]), operation_id="rollback")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "AGENT_MARKETPLACE_TRANSACTION_ROLLED_BACK")
    assert detail["verification"]["effect"] == "none"
    assert _templates(env) == []
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = _publish(
        env.client(env.actors["owner-1"]), operation_id="readback")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "AGENT_MARKETPLACE_COMMITTED_UNVERIFIED")
    assert detail["verification"]["effect"] == "committed"
    assert len(_templates(env)) == 1
    assert len(_audits(env, "agent-marketplace:publish:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-LISTING-SECRET")

        db.commit = lost_commit
        result = service.publish_agent_listing(
            db, actor=env.actors["owner-1"], agent_id="agent-quota",
            price=0.0, description="A listing",
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == (
        "agent-marketplace:publish:lost-confirmation")
    assert "SYNTHETIC-LISTING-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-LISTING-SECRET" not in caplog.text
    assert _templates(env) == []


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "resource",
    "success",
    "security_level",
    "metadata_target_id",
    "metadata_source_agent_id",
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
            row.user_id = "member-1"
        elif field == "tenant_id":
            row.tenant_id = "t2"
        elif field == "resource":
            row.resource = "agent_template:other"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_source_agent_id":
            metadata["source_agent_id"] = "other"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = _publish(
        env.client(env.actors["owner-1"]),
        operation_id=f"audit-{field}")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == (
        "AGENT_MARKETPLACE_COMMITTED_UNVERIFIED")
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_anonymous_requests_are_refused(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.post(
        "/api/agent-marketplace/agents/agent-quota/publish",
        json={"price": 0}).status_code == 401
    assert _templates(env) == []
    assert _audits(env) == []
