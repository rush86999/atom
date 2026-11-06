"""Failure-first contracts for the two Auto-Dev tool-mutation decisions.

The decision surface is tenant-scoped TEAM_LEAD+ review. Each decision binds
the exact reviewed mutation material, writes one durable ``AuditLog`` receipt in
the same transaction, replays idempotently, refuses stale/competing decisions,
and cannot be overwritten by the parallel sandbox writer.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.evolution_review_write_service as service
from api.autodev_review_routes import router as review_router
from core.auth import get_current_tenant, get_current_user
from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
from core.auto_dev.models import ToolMutation
from core.database import Base, get_db
from core.models import AuditLog, Tenant, User


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/evolution-review.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    tenants = [
        Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one"),
        Tenant(id="tenant-2", name="Tenant Two", subdomain="tenant-two"),
    ]
    users = [
        User(
            id="lead-1", tenant_id="tenant-1", email="lead@example.com",
            first_name="Lead", last_name="One", role="team_lead",
            status="active", is_active=True),
        User(
            id="member-1", tenant_id="tenant-1", email="member@example.com",
            first_name="Member", last_name="One", role="member",
            status="active", is_active=True),
        User(
            id="viewer-1", tenant_id="tenant-1", email="viewer@example.com",
            first_name="Viewer", last_name="One", role="viewer",
            status="active", is_active=True),
        User(
            id="guest-1", tenant_id="tenant-1", email="guest@example.com",
            first_name="Guest", last_name="One", role="guest",
            status="active", is_active=True),
        User(
            id="admin-1", tenant_id="tenant-1", email="admin@example.com",
            first_name="Admin", last_name="One", role="admin",
            status="active", is_active=True),
        User(
            id="foreign-lead", tenant_id="tenant-2",
            email="foreign@example.com", first_name="Foreign",
            last_name="Lead", role="team_lead", status="active",
            is_active=True),
    ]
    mutations = [
        ToolMutation(
            id="m-pending", tenant_id="tenant-1", tool_name="outlook.search",
            parent_tool_id=None,
            mutated_code="def run(value):\n    return value + 1\n",
            sandbox_status="pending", execution_error=None),
        ToolMutation(
            id="m-passed", tenant_id="tenant-1", tool_name="outlook.send",
            parent_tool_id="parent-1",
            mutated_code="def run():\n    return 'sent'\n",
            sandbox_status="passed", execution_error=None),
        ToolMutation(
            id="m-failed", tenant_id="tenant-1", tool_name="outlook.sync",
            parent_tool_id=None,
            mutated_code="def run(:\n    pass\n",
            sandbox_status="failed",
            execution_error="SyntaxError: invalid syntax"),
        ToolMutation(
            id="m-foreign", tenant_id="tenant-2", tool_name="crm.search",
            parent_tool_id=None,
            mutated_code="def run():\n    return 2\n",
            sandbox_status="pending", execution_error=None),
        ToolMutation(
            id="m-secret", tenant_id="tenant-1", tool_name="secret.tool",
            parent_tool_id=None,
            mutated_code="SECRET_CODE_MATERIAL = True\n",
            sandbox_status="failed",
            execution_error="SECRET_ERROR_TEXT"),
    ]
    seed.add_all(tenants + users + mutations)
    seed.commit()
    seed.close()

    tenant_one = Session().query(Tenant).filter(
        Tenant.id == "tenant-1").one()
    tenant_two = Session().query(Tenant).filter(
        Tenant.id == "tenant-2").one()
    actors = {
        row.id: row for row in Session().query(User).filter(
            User.id.in_([
                "lead-1", "member-1", "viewer-1", "guest-1", "admin-1",
                "foreign-lead",
            ])).all()
    }
    app = FastAPI()
    app.include_router(review_router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_user] = lambda: actors["lead-1"]
    app.dependency_overrides[get_current_tenant] = lambda: tenant_one

    def client(user=None, tenant=None):
        app.dependency_overrides[get_current_user] = (
            lambda: user or actors["lead-1"])
        app.dependency_overrides[get_current_tenant] = (
            lambda: tenant or tenant_one)
        return TestClient(app, raise_server_exceptions=False)

    def add_mutation(mutation_id, *, status="pending", tenant_id="tenant-1"):
        db = Session()
        try:
            db.add(ToolMutation(
                id=mutation_id, tenant_id=tenant_id,
                tool_name="generated.tool", parent_tool_id=None,
                mutated_code=f"def run():\n    return {mutation_id!r}\n",
                sandbox_status=status, execution_error=None))
            db.commit()
        finally:
            db.close()

    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, tenant_one=tenant_one, tenant_two=tenant_two,
        add_mutation=add_mutation)


def _mutation(env, mutation_id):
    db = env.Session()
    try:
        return db.query(ToolMutation).filter(
            ToolMutation.id == mutation_id).first()
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


def _operation_id(env, suffix):
    return f"autodev:tool-mutation:{suffix}"


def test_team_lead_approve_pending_verifies_and_audits(env):
    response = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=approve-one")
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == "approved"
    assert body["verification"]["status"] == "verified"
    assert body["operation_id"] == _operation_id(env, "approve-one")

    row = _mutation(env, "m-pending")
    assert row.sandbox_status == "approved"
    audits = _audits(env, _operation_id(env, "approve-one"))
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "tool_mutation_approved"
    assert audit.user_id == "lead-1"
    assert audit.tenant_id == "tenant-1"
    assert audit.workspace_id is None
    assert audit.success is True
    metadata = json.loads(audit.metadata_json)
    assert metadata["decision"] == "approved"
    assert metadata["prior_status"] == "pending"
    assert metadata["result_status"] == "approved"
    assert metadata["target_id"] == "m-pending"
    assert metadata["tenant_id"] == "tenant-1"
    assert "SECRET_CODE_MATERIAL" not in audit.metadata_json
    assert "def run" not in audit.metadata_json
    assert "SECRET_CODE_MATERIAL" not in response.text


@pytest.mark.parametrize("mutation_id,status", [
    ("m-pending", "pending"),
    ("m-passed", "passed"),
    ("m-failed", "failed"),
])
def test_reject_allowed_prior_states(env, mutation_id, status):
    response = env.client().post(
        f"/api/autodev/mutations/{mutation_id}/reject"
        f"?operation_id=reject-{mutation_id}")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "rejected"
    row = _mutation(env, mutation_id)
    assert row.sandbox_status == "rejected"
    assert len(_audits(env, _operation_id(env, f"reject-{mutation_id}"))) == 1


def test_approve_passed_allowed_but_failed_refused(env):
    allowed = env.client().post(
        "/api/autodev/mutations/m-passed/approve?operation_id=approve-passed")
    assert allowed.status_code == 200, allowed.text
    assert _mutation(env, "m-passed").sandbox_status == "approved"

    refused = env.client().post(
        "/api/autodev/mutations/m-failed/approve?operation_id=approve-failed")
    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["verification"]["effect"] == "none"
    assert detail["error"]["code"] == "CONFLICT"
    assert _mutation(env, "m-failed").sandbox_status == "failed"
    assert _audits(env, _operation_id(env, "approve-failed")) == []


@pytest.mark.parametrize("actor_id", ["member-1", "viewer-1", "guest-1"])
def test_non_review_roles_cannot_decide(env, actor_id):
    response = env.client(user=env.actors[actor_id]).post(
        "/api/autodev/mutations/m-pending/approve?operation_id=role-denied")
    assert response.status_code == 403, response.text
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


def test_admin_can_decide(env):
    response = env.client(user=env.actors["admin-1"]).post(
        "/api/autodev/mutations/m-pending/approve?operation_id=admin-approve")
    assert response.status_code == 200, response.text
    assert _mutation(env, "m-pending").sandbox_status == "approved"


def test_anonymous_cannot_decide(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    env.app.dependency_overrides.pop(get_current_tenant, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    response = client.post(
        "/api/autodev/mutations/m-pending/approve?operation_id=anonymous")
    assert response.status_code in (401, 403), response.text
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


def test_missing_and_foreign_target_are_not_found(env):
    missing = env.client().post(
        "/api/autodev/mutations/does-not-exist/approve"
        "?operation_id=missing-target")
    assert missing.status_code == 404, missing.text
    foreign = env.client().post(
        "/api/autodev/mutations/m-foreign/approve"
        "?operation_id=foreign-target")
    assert foreign.status_code == 404, foreign.text
    assert _mutation(env, "m-foreign").sandbox_status == "pending"
    assert _audits(env) == []


def test_foreign_tenant_actor_is_refused(env):
    response = env.client(
        user=env.actors["foreign-lead"],
        tenant=env.tenant_one,
    ).post(
        "/api/autodev/mutations/m-pending/approve"
        "?operation_id=foreign-actor")
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AUTHORITY_CHANGED"
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


def test_competing_decision_is_refused(env):
    approved = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=winner")
    assert approved.status_code == 200, approved.text
    competing = env.client().post(
        "/api/autodev/mutations/m-pending/reject?operation_id=loser")
    assert competing.status_code == 409, competing.text
    detail = competing.json()["detail"]
    assert detail["error"]["code"] == "ALREADY_REVIEWED"
    assert detail["verification"]["effect"] == "none"
    assert _mutation(env, "m-pending").sandbox_status == "approved"
    assert len(_audits(env)) == 1


def test_same_operation_replay_is_idempotent(env):
    first = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=replay-one")
    assert first.status_code == 200, first.text
    replay = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=replay-one")
    assert replay.status_code == 200, replay.text
    body = replay.json()["data"]
    assert body["verification"]["status"] == "already_applied"
    assert body["verification"]["replay"] == "do_not_repeat"
    assert _mutation(env, "m-pending").sandbox_status == "approved"
    assert len(_audits(env)) == 1

    changed = env.client().post(
        "/api/autodev/mutations/m-pending/reject?operation_id=replay-one")
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"
    assert _mutation(env, "m-pending").sandbox_status == "approved"
    assert len(_audits(env)) == 1


def test_replay_after_material_reset_is_committed_unverified(env):
    first = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=reset-replay")
    assert first.status_code == 200, first.text
    db = env.Session()
    try:
        db.execute(update(ToolMutation).where(
            ToolMutation.id == "m-pending").values(
                mutated_code="def run():\n    return 'peer edit'\n"))
        db.commit()
    finally:
        db.close()

    replay = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=reset-replay")
    assert replay.status_code == 503, replay.text
    detail = replay.json()["detail"]
    assert detail["error"]["code"] == "TOOL_MUTATION_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert _mutation(env, "m-pending").sandbox_status == "approved"
    assert len(_audits(env)) == 1


def test_stale_material_before_claim_is_refused(env, monkeypatch):
    original = service._claim_actor

    def claim_then_change(db, actor):
        peer = env.Session()
        try:
            peer.execute(update(ToolMutation).where(
                ToolMutation.id == "m-pending").values(
                    tool_name="peer.renamed"))
            peer.commit()
        finally:
            peer.close()
        return original(db, actor)

    monkeypatch.setattr(service, "_claim_actor", claim_then_change)
    response = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=stale-material")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "STALE_TARGET"
    assert detail["verification"]["effect"] == "none"
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


def test_authority_changed_before_claim_is_refused(env, monkeypatch):
    original = service._claim_actor

    def claim_then_demote(db, actor):
        peer = env.Session()
        try:
            peer.execute(update(User).where(
                User.id == "lead-1").values(role="member"))
            peer.commit()
        finally:
            peer.close()
        return original(db, actor)

    monkeypatch.setattr(service, "_claim_actor", claim_then_demote)
    response = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=demoted")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "AUTHORITY_CHANGED"
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_sandbox_never_overwrites_a_review_decision(env, decision):
    target = "m-pending" if decision == "approved" else "m-failed"
    endpoint = "approve" if decision == "approved" else "reject"
    response = env.client().post(
        f"/api/autodev/mutations/{target}/{endpoint}"
        f"?operation_id=sandbox-{decision}")
    assert response.status_code == 200, response.text
    before = _mutation(env, target)
    assert before.sandbox_status == decision
    before_error = before.execution_error

    async def execute_raw_python(**kwargs):
        raise AssertionError("sandbox must not run after review")

    sandbox = SimpleNamespace(execute_raw_python=execute_raw_python)
    engine = AlphaEvolverEngine(db=env.Session(), sandbox=sandbox)
    result = __import__("asyncio").run(engine.sandbox_execute_mutation(
        target, "tenant-1", {}))

    assert result["skipped"] is True
    assert result["reason"] == "review_decision_present"
    assert result["status"] == decision
    after = _mutation(env, target)
    assert after.sandbox_status == decision
    assert after.execution_error == before_error


def test_sandbox_guard_does_not_record_a_racing_review(env):
    from core.auth import get_current_tenant as tenant_dep
    from core.auth import get_current_user as user_dep

    env.add_mutation("m-race", status="pending")

    async def execute_raw_python(**kwargs):
        # A reviewer wins the race while the sandbox is running.
        client = env.client(
            user=env.actors["lead-1"], tenant=env.tenant_one)
        response = client.post(
            "/api/autodev/mutations/m-race/approve?operation_id=race-review")
        assert response.status_code == 200, response.text
        return {
            "status": "success", "output": "ok",
            "execution_seconds": 0.1, "environment": "scratch",
        }

    sandbox = SimpleNamespace(execute_raw_python=execute_raw_python)
    engine = AlphaEvolverEngine(db=env.Session(), sandbox=sandbox)
    result = __import__("asyncio").run(engine.sandbox_execute_mutation(
        "m-race", "tenant-1", {}))

    assert result["skipped"] is True
    assert result["reason"] == "review_decision_present"
    assert result["status"] == "approved"
    row = _mutation(env, "m-race")
    assert row.sandbox_status == "approved"
    assert row.execution_error is None


def test_sandbox_pending_and_failed_writes_are_guarded(env):
    from unittest.mock import AsyncMock, MagicMock

    env.add_mutation("m-sandbox-pass", status="pending")
    env.add_mutation("m-sandbox-fail", status="pending")
    env.add_mutation("m-sandbox-retry", status="failed")

    success = MagicMock()
    success.execute_raw_python = AsyncMock(return_value={
        "status": "success", "output": "ok",
        "execution_seconds": 0.5, "environment": "scratch",
    })
    engine = AlphaEvolverEngine(db=env.Session(), sandbox=success)
    passed = __import__("asyncio").run(engine.sandbox_execute_mutation(
        "m-sandbox-pass", "tenant-1", {}))
    assert passed["success"] is True
    assert passed["skipped"] is False
    row = _mutation(env, "m-sandbox-pass")
    assert row.sandbox_status == "passed"
    assert row.execution_error is None

    failure = MagicMock()
    failure.execute_raw_python = AsyncMock(return_value={
        "status": "failed", "output": "SyntaxError: bad",
        "execution_seconds": 0.2, "environment": "scratch",
    })
    engine = AlphaEvolverEngine(db=env.Session(), sandbox=failure)
    failed = __import__("asyncio").run(engine.sandbox_execute_mutation(
        "m-sandbox-fail", "tenant-1", {}))
    assert failed["success"] is False
    assert failed["proxy_signals"]["syntax_error"] is True
    row = _mutation(env, "m-sandbox-fail")
    assert row.sandbox_status == "failed"
    assert row.execution_error == "SyntaxError: bad"

    retry = MagicMock()
    retry.execute_raw_python = AsyncMock(return_value={
        "status": "success", "output": "ok",
        "execution_seconds": 0.3, "environment": "scratch",
    })
    engine = AlphaEvolverEngine(db=env.Session(), sandbox=retry)
    retried = __import__("asyncio").run(engine.sandbox_execute_mutation(
        "m-sandbox-retry", "tenant-1", {}))
    assert retried["success"] is True
    row = _mutation(env, "m-sandbox-retry")
    assert row.sandbox_status == "passed"
    assert row.execution_error is None


def test_confirmed_audit_rollback_reports_effect_none(env, monkeypatch):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    response = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=rollback")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "TOOL_MUTATION_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert detail["verification"]["status"] == "refused"
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


def test_post_commit_readback_failure_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = env.client().post(
        "/api/autodev/mutations/m-pending/approve?operation_id=readback")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "TOOL_MUTATION_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert detail["operation_id"] == _operation_id(env, "readback")
    assert detail["audit_id"] == _operation_id(env, "readback")
    assert _mutation(env, "m-pending").sandbox_status == "approved"
    assert len(_audits(env, _operation_id(env, "readback"))) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-TOOL-SECRET")

        db.commit = lost_commit
        result = service.review_tool_mutation(
            db, actor=env.actors["lead-1"], tenant_id="tenant-1",
            mutation_id="m-pending", decision="approved",
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == _operation_id(env, "lost-confirmation")
    assert "SYNTHETIC-TOOL-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-TOOL-SECRET" not in caplog.text
    assert _mutation(env, "m-pending").sandbox_status == "pending"
    assert _audits(env) == []


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "workspace_id",
    "success",
    "security_level",
    "resource",
    "metadata_decision",
    "metadata_prior_status",
    "metadata_target_id",
    "metadata_actor_id",
    "metadata_code_digest",
    "metadata_material_digest",
    "metadata_result_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    mutation_id = f"m-audit-{field}"
    env.add_mutation(mutation_id)
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "member-1"
        elif field == "tenant_id":
            row.tenant_id = "tenant-2"
        elif field == "workspace_id":
            row.workspace_id = "workspace-x"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "resource":
            row.resource = "tool_mutation:other"
        elif field == "metadata_decision":
            metadata["decision"] = "rejected"
        elif field == "metadata_prior_status":
            metadata["prior_status"] = "passed"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other-target"
        elif field == "metadata_actor_id":
            metadata["actor_id"] = "member-1"
        elif field == "metadata_code_digest":
            metadata["code_digest"] = "wrong-code-digest"
        elif field == "metadata_material_digest":
            metadata["material_digest"] = "wrong-material-digest"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result-digest"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = env.client().post(
        f"/api/autodev/mutations/{mutation_id}/approve"
        f"?operation_id=audit-{field}")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "TOOL_MUTATION_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"
    assert _mutation(env, mutation_id).sandbox_status == "approved"


def test_decision_receipt_omits_code_and_execution_error(env):
    response = env.client().post(
        "/api/autodev/mutations/m-secret/reject?operation_id=secret-reject")
    assert response.status_code == 200, response.text
    assert "SECRET_CODE_MATERIAL" not in response.text
    assert "SECRET_ERROR_TEXT" not in response.text
    audits = _audits(env, _operation_id(env, "secret-reject"))
    assert len(audits) == 1
    assert "SECRET_CODE_MATERIAL" not in (audits[0].metadata_json or "")
    assert "SECRET_ERROR_TEXT" not in (audits[0].metadata_json or "")
    assert "SECRET_CODE_MATERIAL" not in (audits[0].description or "")
    assert "SECRET_ERROR_TEXT" not in (audits[0].description or "")
