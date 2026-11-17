"""Owner-scoped audit reads + correction-request linkage (F1/F2/F3).

Real SQLite tables + a real bearer JWT (``core.auth.get_current_user`` runs
against the same overridden session). The route still re-reads the ``User``
row, so a stale token/role/workspace is never authority.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import audit_routes, reasoning_routes
from core.auth import create_access_token, get_current_user
from core.database import get_db as core_get_db
from core.models import (
    AgentExecution,
    AgentFeedback,
    AgentReasoningStep,
    AgentRegistry,
    AuditLog,
    RevokedToken,
    TokenUsage,
    User,
    UserRole,
    UserStatus,
)


def _event(
    *,
    row_id: str,
    user_id: str | None,
    workspace_id: str | None,
    execution_id: str | None,
    action: str = "tool:read",
    agent_id: str | None = "agent-1",
    event_type: str = "agent_action",
    success: bool = True,
    metadata: dict | None = None,
) -> AuditLog:
    meta = dict(metadata or {})
    if agent_id:
        meta.setdefault("agent_id", agent_id)
    if execution_id:
        meta["agent_execution_id"] = execution_id
    return AuditLog(
        id=row_id,
        event_type=event_type,
        security_level="low",
        threat_level="none",
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
        workspace_id=workspace_id,
        resource=agent_id,
        action=action,
        description=f"event {action}",
        metadata_json=json.dumps(meta),
        success=success,
    )


@pytest.fixture()
def audit_app(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Tripwire: this suite must never write to the live dev DB. The fixture
    # owns an in-memory engine; a URL change here is a test bug, not a target.
    assert "memory" in str(engine.url).lower()
    for table in (
        User.__table__,
        RevokedToken.__table__,
        AgentRegistry.__table__,
        AgentExecution.__table__,
        AgentReasoningStep.__table__,
        AgentFeedback.__table__,
        TokenUsage.__table__,
        AuditLog.__table__,
    ):
        table.create(engine, checkfirst=True)

    session = sessionmaker(bind=engine)()
    session.add_all([
        User(
            id="member", email="member@test.local", first_name="M",
            last_name="B", hashed_password="h", role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value, workspace_id="ws-1", tenant_id="t-1",
        ),
        User(
            id="member2", email="member2@test.local", first_name="M",
            last_name="2", hashed_password="h", role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value, workspace_id="ws-1", tenant_id="t-1",
        ),
        User(
            id="lead", email="lead@test.local", first_name="L",
            last_name="D", hashed_password="h", role=UserRole.TEAM_LEAD.value,
            status=UserStatus.ACTIVE.value, workspace_id="ws-1", tenant_id="t-1",
        ),
        User(
            id="foreign", email="foreign@test.local", first_name="F",
            last_name="W", hashed_password="h", role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value, workspace_id="ws-2", tenant_id="t-2",
        ),
        User(
            id="personal", email="personal@test.local", first_name="P",
            last_name="N", hashed_password="h", role=UserRole.MEMBER.value,
            status=UserStatus.ACTIVE.value, workspace_id=None, tenant_id=None,
        ),
        User(
            id="gone", email="gone@test.local", first_name="G",
            last_name="X", hashed_password="h", role=UserRole.MEMBER.value,
            status=UserStatus.SUSPENDED.value, workspace_id="ws-1", tenant_id="t-1",
        ),
        AgentRegistry(
            id="agent-1", name="Bookkeeper", category="Finance",
            module_path="agents.bookkeeper", class_name="Bookkeeper",
            workspace_id=None, tenant_id=None,
        ),
    ])
    session.add_all([
        _event(row_id="ev-member-start", user_id="member", workspace_id="ws-1",
               execution_id="exec-member", action="execution_start",
               metadata={"task_input": "reconcile Q3"}),
        _event(row_id="ev-member-tool", user_id="member", workspace_id="ws-1",
               execution_id="exec-member",
               metadata={"args": {"api_key": "sk-live-SECRET-VALUE", "q": "payroll"}}),
        _event(row_id="ev-other", user_id="member2", workspace_id="ws-1",
               execution_id="exec-other",
               metadata={"prompt_excerpt": "OTHER-USER-PROMPT"}),
        _event(row_id="ev-foreign", user_id="foreign", workspace_id="ws-2",
               execution_id="exec-foreign",
               metadata={"prompt_excerpt": "FOREIGN-WORKSPACE-PROMPT"}),
        _event(row_id="ev-unbound", user_id=None, workspace_id="default",
               execution_id="exec-unbound",
               metadata={"prompt_excerpt": "UNBOUND-HISTORICAL-ROW"}),
        _event(row_id="ev-personal", user_id="personal", workspace_id="default",
               execution_id="exec-personal",
               metadata={"task_input": "personal task"}),
        _event(row_id="ev-member-llm", user_id="member", workspace_id="ws-1",
               execution_id="exec-member", event_type="llm_call",
               action="llm_call:tier:auto",
               metadata={"model": "tier:auto", "provider": "route"}),
    ])
    session.add_all([
        AgentExecution(id="exec-member", agent_id="agent-1",
                       workspace_id="ws-1", tenant_id="t-1", status="completed",
                       metadata_json={}),
        AgentExecution(id="exec-other", agent_id="agent-1",
                       workspace_id="ws-1", tenant_id="t-1", status="completed"),
        AgentExecution(id="exec-foreign", agent_id="agent-1",
                       workspace_id="ws-2", tenant_id="t-2", status="completed"),
        AgentExecution(id="legacy-ws1", agent_id="agent-1",
                       workspace_id="ws-1", tenant_id="t-1", status="completed",
                       input_summary="legacy run"),
    ])
    session.add_all([
        AgentReasoningStep(
            id=str(uuid.uuid4()), execution_id="exec-member", step_number=0,
            step_type="action", requested_model="requested-x",
            resolved_model="served-y", verified="verified",
            verification_evidence="db read-back matched",
        ),
        AgentReasoningStep(
            id=str(uuid.uuid4()), execution_id="exec-member", step_number=1,
            step_type="action", verified="unverified",
        ),
        TokenUsage(
            id=str(uuid.uuid4()), execution_id="exec-member", agent_id="agent-1",
            workspace_id="ws-1", tenant_id="t-1", cost_usd=0.02,
            pricing_status="priced", total_tokens=10,
        ),
        TokenUsage(
            id=str(uuid.uuid4()), execution_id="exec-member", agent_id="agent-1",
            workspace_id="ws-1", tenant_id="t-1", cost_usd=None,
            pricing_status="unknown", total_tokens=5,
        ),
        TokenUsage(
            id=str(uuid.uuid4()), execution_id="exec-other", agent_id="agent-1",
            workspace_id="ws-1", tenant_id="t-1", cost_usd=0.5,
            pricing_status="priced", total_tokens=100,
        ),
    ])
    session.commit()

    app = FastAPI()
    app.include_router(audit_routes.router)
    app.include_router(reasoning_routes.router)
    app.dependency_overrides[core_get_db] = lambda: session

    # The audit writer intentionally opens its OWN durable session. Point that
    # at this in-memory test world so the correction receipt is readable here
    # (production uses the real engine; no test row can reach it).
    from contextlib import contextmanager
    import core.database as core_database

    @contextmanager
    def _audit_session():
        yield session

    monkeypatch.setattr(core_database, "get_db_session", _audit_session)

    client = TestClient(app)
    yield SimpleNamespace(client=client, app=app, session=session, engine=engine)
    session.close()
    engine.dispose()


def _token(session, user_id: str) -> str:
    user = session.query(User).filter(User.id == user_id).one()
    return create_access_token({"sub": user.id}, user=user)


def _headers(session, user_id: str) -> dict:
    return {"Authorization": f"Bearer {_token(session, user_id)}"}


def _ids(resp) -> set:
    return {item["id"] for item in resp.json().get("items", [])}


# --------------------------------------------------------------------------- #
# F1: one general read scope for all four endpoints
# --------------------------------------------------------------------------- #
def test_member_reads_own_events_only_and_secrets_are_redacted(audit_app):
    resp = audit_app.client.get(
        "/api/audit/events", headers=_headers(audit_app.session, "member"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = _ids(resp)
    assert {"ev-member-start", "ev-member-tool", "ev-member-llm"} <= ids
    assert "ev-other" not in ids
    assert "ev-foreign" not in ids
    assert "ev-unbound" not in ids
    assert "ev-personal" not in ids
    assert body["read_scope"]["kind"] == "owner"
    # Read-side redaction reuses the existing helpers; no secret is echoed.
    assert "sk-live-SECRET-VALUE" not in resp.text
    tool = next(i for i in body["items"] if i["id"] == "ev-member-tool")
    assert "api_key" not in tool["metadata"]


def test_member_timeline_requires_provable_ownership(audit_app):
    ok = audit_app.client.get(
        "/api/audit/executions/exec-member",
        headers=_headers(audit_app.session, "member"),
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert {event["id"] for event in body["events"]} == {
        "ev-member-start", "ev-member-tool", "ev-member-llm"}
    assert "OTHER-USER-PROMPT" not in ok.text
    assert "FOREIGN-WORKSPACE-PROMPT" not in ok.text

    for foreign_execution in (
        "exec-other",          # same workspace, other user's run
        "exec-foreign",        # other workspace
        "exec-unbound",        # unbound historical rows
        "legacy-ws1",          # AgentExecution only, no ownership evidence
    ):
        resp = audit_app.client.get(
            f"/api/audit/executions/{foreign_execution}",
            headers=_headers(audit_app.session, "member"),
        )
        assert resp.status_code == 404, (foreign_execution, resp.text)


def test_member_execution_list_and_summary_are_owner_scoped(audit_app):
    headers = _headers(audit_app.session, "member")
    executions = audit_app.client.get("/api/audit/executions", headers=headers)
    assert executions.status_code == 200
    body = executions.json()
    assert [item["execution_id"] for item in body["items"]] == ["exec-member"]
    assert body["read_scope"]["kind"] == "owner"

    summary = audit_app.client.get("/api/audit/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total_events"] == 3
    assert summary.json()["read_scope"]["kind"] == "owner"


def test_supervisor_is_workspace_scoped_not_global(audit_app):
    headers = _headers(audit_app.session, "lead")
    events = audit_app.client.get("/api/audit/events", headers=headers)
    assert events.status_code == 200
    ids = _ids(events)
    assert {"ev-member-start", "ev-other"} <= ids
    assert "ev-foreign" not in ids
    assert events.json()["read_scope"]["kind"] == "workspace"

    own_workspace_foreign_user = audit_app.client.get(
        "/api/audit/executions/exec-other", headers=headers)
    assert own_workspace_foreign_user.status_code == 200
    other_workspace = audit_app.client.get(
        "/api/audit/executions/exec-foreign", headers=headers)
    assert other_workspace.status_code == 404
    # Legacy fallback stays available to a supervisor in the same workspace.
    fallback = audit_app.client.get(
        "/api/audit/executions/legacy-ws1", headers=headers)
    assert fallback.status_code == 200
    assert fallback.json()["found_events"] is False

    summary = audit_app.client.get("/api/audit/summary", headers=headers)
    assert summary.status_code == 200
    # ws-1 rows only: member start + member tool + other + member llm.
    assert summary.json()["total_events"] == 4


def test_cross_workspace_member_cannot_read_by_guess(audit_app):
    resp = audit_app.client.get(
        "/api/audit/executions/exec-member",
        headers=_headers(audit_app.session, "foreign"),
    )
    assert resp.status_code == 404
    resp = audit_app.client.get(
        "/api/audit/events", headers=_headers(audit_app.session, "foreign"))
    assert resp.status_code == 200
    assert _ids(resp) == {"ev-foreign"}


def test_stale_client_role_and_owner_fields_are_not_authority(audit_app):
    stale = SimpleNamespace(id="member", role=UserRole.SUPER_ADMIN.value,
                            workspace_id="ws-2", tenant_id="t-2")
    audit_app.app.dependency_overrides[get_current_user] = lambda: stale
    try:
        resp = audit_app.client.get("/api/audit/events")
        assert resp.status_code == 200
        assert _ids(resp) == {"ev-member-start", "ev-member-tool", "ev-member-llm"}
        assert "ev-foreign" not in _ids(resp)
        assert resp.json()["read_scope"]["kind"] == "owner"
    finally:
        audit_app.app.dependency_overrides.pop(get_current_user, None)


def test_deactivated_account_is_refused_by_fresh_authority(audit_app):
    stale = SimpleNamespace(id="gone", role=UserRole.TEAM_LEAD.value,
                            workspace_id="ws-1", tenant_id="t-1")
    audit_app.app.dependency_overrides[get_current_user] = lambda: stale
    try:
        resp = audit_app.client.get("/api/audit/events")
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "ACCOUNT_NOT_ACTIVE"
    finally:
        audit_app.app.dependency_overrides.pop(get_current_user, None)


def test_nonexistent_actor_is_401(audit_app):
    stale = SimpleNamespace(id="does-not-exist")
    audit_app.app.dependency_overrides[get_current_user] = lambda: stale
    try:
        assert audit_app.client.get("/api/audit/events").status_code == 401
    finally:
        audit_app.app.dependency_overrides.pop(get_current_user, None)


def test_execution_id_wildcards_do_not_broaden(audit_app):
    headers = _headers(audit_app.session, "lead")
    for value in ("%", "exec-1%", "exec%member", "exec/member", "exec-member["):
        resp = audit_app.client.get(
            "/api/audit/events", params={"execution_id": value}, headers=headers)
        assert resp.status_code == 422, (value, resp.text)
    for path in ("exec-member%25", "%25", "exec-member%25%25"):
        resp = audit_app.client.get(
            f"/api/audit/executions/{path}", headers=headers)
        assert resp.status_code == 404, (path, resp.text)
    # Exact match does not include the longer prefix-sharing id.
    audit_app.session.add(_event(
        row_id="ev-prefix", user_id="member", workspace_id="ws-1",
        execution_id="exec-member-extra", action="execution_start"))
    audit_app.session.commit()
    exact = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers)
    assert "ev-prefix" not in {e["id"] for e in exact.json()["events"]}


def test_personal_default_semantics_and_no_global_default_bypass(audit_app):
    personal_headers = _headers(audit_app.session, "personal")
    resp = audit_app.client.get("/api/audit/events", headers=personal_headers)
    assert resp.status_code == 200
    ids = _ids(resp)
    assert ids == {"ev-personal"}
    assert "ev-unbound" not in ids

    # A real-workspace member never inherits the shared default bucket.
    resp = audit_app.client.get(
        "/api/audit/events", headers=_headers(audit_app.session, "member"))
    assert "ev-personal" not in _ids(resp)
    assert "ev-unbound" not in _ids(resp)


# --------------------------------------------------------------------------- #
# F2: correction request is linked, truthful and never applied
# --------------------------------------------------------------------------- #
def _correction_payload(**overrides) -> dict:
    payload = {
        "agent_id": "agent-1",
        "run_id": "exec-member",
        "step_index": 1,
        "step_content": {"step": 1, "thought": "wrong tool args"},
        "feedback_type": "thumbs_down",
        "comment": "Wrong report opened",
        "execution_id": "exec-member",
        "subject_audit_id": "ev-member-tool",
        "subject_step_number": 1,
        "correction_requested": True,
        "correction_reason": "Wrong action taken",
    }
    payload.update(overrides)
    return payload


def test_correction_request_links_feedback_to_actual_audit_subject(audit_app):
    headers = _headers(audit_app.session, "member")
    resp = audit_app.client.post(
        "/api/reasoning/feedback", json=_correction_payload(), headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["correction_status"] == "recorded"
    assert data["applied"] is False
    assert data["verified"] is False
    assert data["correction_audit_id"]

    feedback = (
        audit_app.session.query(AgentFeedback)
        .filter(AgentFeedback.id == data["feedback_id"])
        .one()
    )
    assert feedback.user_id == "member"
    assert feedback.agent_execution_id == "exec-member"

    receipt = (
        audit_app.session.query(AuditLog)
        .filter(AuditLog.id == data["correction_audit_id"])
        .one()
    )
    assert receipt.action == "correction_requested"
    assert receipt.user_id == "member"
    assert receipt.workspace_id == "ws-1"
    meta = json.loads(receipt.metadata_json)
    assert meta["feedback_id"] == data["feedback_id"]
    assert meta["subject_audit_id"] == "ev-member-tool"
    assert meta["subject_execution_id"] == "exec-member"
    assert meta["applied"] is False
    assert meta["verified"] is False
    assert meta["status"] == "requested"

    # The timeline shows the receipt inline, still as requested — not applied.
    timeline = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers)
    receipt_event = next(
        e for e in timeline.json()["events"]
        if e["action"] == "correction_requested")
    assert receipt_event["correction"]["applied"] is False
    assert receipt_event["correction"]["verified"] is False
    assert receipt_event["correction"]["feedback_id"] == data["feedback_id"]


def test_correction_request_is_idempotent_on_replay(audit_app):
    headers = _headers(audit_app.session, "member")
    first = audit_app.client.post(
        "/api/reasoning/feedback", json=_correction_payload(), headers=headers)
    second = audit_app.client.post(
        "/api/reasoning/feedback", json=_correction_payload(), headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["correction_status"] == "already_recorded"
    assert (
        audit_app.session.query(AuditLog)
        .filter(AuditLog.action == "correction_requested")
        .count()
    ) == 1


def test_correction_request_cannot_target_foreign_audit_rows(audit_app):
    headers = _headers(audit_app.session, "member")
    before = audit_app.session.query(AgentFeedback).count()
    for overrides in (
        {"subject_audit_id": "ev-other"},       # same workspace, other user
        {"subject_audit_id": "ev-foreign"},     # other workspace
        {"subject_audit_id": "ev-unbound"},     # unbound historical row
        {"subject_audit_id": None, "execution_id": "exec-other"},
        {"subject_audit_id": "ev-prefix-does-not-exist"},
    ):
        resp = audit_app.client.post(
            "/api/reasoning/feedback",
            json=_correction_payload(**overrides),
            headers=headers,
        )
        assert resp.status_code in (404, 422), (overrides, resp.text)
    assert audit_app.session.query(AgentFeedback).count() == before


def test_correction_request_rejects_mismatched_identity_and_channel(audit_app):
    headers = _headers(audit_app.session, "member")
    cases = [
        {"execution_id": "exec-other"},                       # id mismatch
        {"agent_id": "someone-else"},                         # agent mismatch
        {"correction_channel": "unknown-channel"},
        {"correction_channel": "activity",
         "correction_target_id": "https://evil.example/x"},
        {"subject_audit_id": None, "execution_id": None},     # no subject
    ]
    for overrides in cases:
        resp = audit_app.client.post(
            "/api/reasoning/feedback",
            json=_correction_payload(**overrides),
            headers=headers,
        )
        assert resp.status_code == 422, (overrides, resp.text)


def test_correction_request_refuses_deactivated_actor(audit_app):
    stale = SimpleNamespace(id="gone", role=UserRole.MEMBER.value,
                            workspace_id="ws-1", tenant_id="t-1")
    audit_app.app.dependency_overrides[get_current_user] = lambda: stale
    try:
        resp = audit_app.client.post(
            "/api/reasoning/feedback", json=_correction_payload())
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "ACCOUNT_NOT_ACTIVE"
    finally:
        audit_app.app.dependency_overrides.pop(get_current_user, None)


def test_supported_channel_is_recorded_without_applying_it(audit_app):
    headers = _headers(audit_app.session, "member")
    resp = audit_app.client.post(
        "/api/reasoning/feedback",
        json=_correction_payload(
            correction_channel="activity",
            correction_target_id="goal-123",
        ),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["applied"] is False and data["verified"] is False
    assert data["channel"] == "activity"
    receipt = (
        audit_app.session.query(AuditLog)
        .filter(AuditLog.id == data["correction_audit_id"])
        .one()
    )
    meta = json.loads(receipt.metadata_json)
    assert meta["channel"] == "activity"
    assert meta["channel_target_id"] == "goal-123"
    assert meta["channel_status"] == "requested"


def test_correction_request_cannot_spoof_actor_or_survive_cold_read(audit_app):
    headers = _headers(audit_app.session, "member")
    payload = _correction_payload()
    payload["user_id"] = "lead"          # body field must not become authority
    payload["workspace_id"] = "ws-2"
    resp = audit_app.client.post(
        "/api/reasoning/feedback", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Cold read: a fresh session sees the durable feedback + receipt.
    audit_app.session.expire_all()
    fresh = sessionmaker(bind=audit_app.engine)()
    try:
        feedback = (
            fresh.query(AgentFeedback)
            .filter(AgentFeedback.id == data["feedback_id"])
            .one()
        )
        receipt = (
            fresh.query(AuditLog)
            .filter(AuditLog.id == data["correction_audit_id"])
            .one()
        )
        assert feedback.user_id == "member"
        assert receipt.user_id == "member"
        assert receipt.workspace_id == "ws-1"
        assert json.loads(receipt.metadata_json)["feedback_id"] == feedback.id
    finally:
        fresh.close()

    # The member can read the receipt back through the authorized timeline.
    timeline = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers).json()
    assert any(
        event["id"] == data["correction_audit_id"]
        for event in timeline["events"]
    )


def test_correction_audit_write_failure_is_reported_not_hidden(audit_app, monkeypatch):
    monkeypatch.setattr(
        reasoning_routes, "log_correction_request", lambda **kwargs: None)
    headers = _headers(audit_app.session, "member")
    resp = audit_app.client.post(
        "/api/reasoning/feedback", json=_correction_payload(), headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["correction_status"] == "feedback_recorded_audit_unavailable"
    assert data["correction_audit_id"] is None
    assert data["applied"] is False
    assert data["verified"] is False
    assert (
        audit_app.session.query(AgentFeedback)
        .filter(AgentFeedback.id == data["feedback_id"])
        .count()
    ) == 1


# --------------------------------------------------------------------------- #
# F3: evidence / identity / outcome honesty
# --------------------------------------------------------------------------- #
def test_llm_label_is_not_presented_as_served_model(audit_app):
    headers = _headers(audit_app.session, "member")
    timeline = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers).json()
    llm_event = next(e for e in timeline["events"] if e["event_type"] == "llm_call")
    identity = llm_event["model_identity"]
    assert identity["recorded_label"] == "tier:auto"
    assert identity["label_kind"] == "router_tier_or_alias"
    assert identity["served_model"] is None
    assert identity["provenance"] == "recorded_label_only"

    # Execution-level provenance is surfaced only from recorded server data.
    exec_identity = timeline["execution"]["model_identity"]
    assert exec_identity["requested_models"] == ["requested-x"]
    assert exec_identity["resolved_models"] == ["served-y"]
    assert exec_identity["execution_provenance"] is None


def test_verification_is_tri_state_and_not_green_from_run_success(audit_app):
    headers = _headers(audit_app.session, "member")
    timeline = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers).json()
    verification = timeline["execution"]["verification"]
    assert verification["status"] == "partially_verified"
    assert verification["counts"] == {
        "verified": 1, "unverified": 1, "failed_verification": 0}
    assert verification["evidence"][0]["evidence"] == "db read-back matched"
    assert timeline["execution"]["outcome"]["verification"] == "partially_verified"
    assert timeline["execution"]["outcome"]["status"] == "completed"


def test_cost_is_recorded_estimate_or_explicitly_unavailable(audit_app):
    headers = _headers(audit_app.session, "member")
    timeline = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers).json()
    usage = timeline["execution"]["usage"]
    assert usage["status"] == "partial"
    assert usage["basis"] == "recorded_usage_estimate"
    assert usage["unpriced_rows"] == 1
    assert "incomplete" in usage["note"]
    assert "invoice" not in usage["note"]

    executions = audit_app.client.get(
        "/api/audit/executions", headers=headers).json()
    assert executions["items"][0]["usage"]["status"] == "partial"

    # No TokenUsage rows for the legacy run → honest unavailable, not free.
    lead_headers = _headers(audit_app.session, "lead")
    legacy = audit_app.client.get(
        "/api/audit/executions/legacy-ws1", headers=lead_headers).json()
    assert legacy["execution"]["usage"]["status"] == "unavailable"
    assert legacy["execution"]["usage"]["cost_usd"] is None


def test_evidence_limits_are_explicit(audit_app):
    headers = _headers(audit_app.session, "member")
    timeline = audit_app.client.get(
        "/api/audit/executions/exec-member", headers=headers).json()
    limits = timeline["evidence_limits"]
    assert limits["signed"] is False
    assert limits["hash_chain"] is False
    assert "not tamper-evident" in limits["note"]
