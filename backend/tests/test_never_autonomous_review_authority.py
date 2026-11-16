"""Reviewer authority for never-autonomous TASK admissions.

A durable ``never_autonomous_task`` row is a human admission for ONE exact
task execution. Flipping its status to ``approved`` is not authority: the
persisted reviewer must still be a real, active principal in the row's exact
canonical tenant/workspace, must be the persisted owner or an authorized
supervisor, and must satisfy BOTH persisted ``required_role`` locations. The
server-owned execution/task/rule/profile binding is immutable.

These are mounted-surface and real-scratch-DB regressions, not status-only
fixtures:

* ``POST /api/agent-governance/approve/{id}`` with a foreign team_lead must
  not mutate the row and must not create a cold-resume receipt.
* The valid owner / in-scope supervisor path still approves and resumes.
* Both ``/api/agents/approvals/{id}`` aliases reject binding rewrites and
  unqualified reviewers before any status write.
* ``find_approved_task_admission`` rejects missing/unknown/inactive/foreign
  reviewers and malformed/rewritten receipts even when status is approved or
  executed.
* Warm Generic/Meta/task-workflow admission re-reads the exact authorized
  receipt instead of trusting the polling boolean.

Run with an absolute scratch DB (never the live dev DB):

    TESTING=1 PYTEST_VERSION=ci PYTHON_DOTENV_DISABLED=1 \
    DATABASE_URL=sqlite:////absolute/path/atom_review_authority.db \
    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python -m pytest \
      tests/test_never_autonomous_review_authority.py -q
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("TESTING", "1")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.autonomy_policy as ap
from core.agent_governance_service import AgentGovernanceService
from core.auth import get_current_user
from core.database import get_db
from core.models import (
    AgentRegistry,
    Base,
    HITLAction,
    HITLActionStatus,
    Tenant,
    User,
    Workspace,
)
from core.task_classification import (
    bind_task_profile,
    build_task_profile,
    reset_task_profile,
)

FINANCE_JAN = (
    "Analyse the January finance invoice expense and accounting records "
    "and summarize the reconciled totals for the finance team"
)
FINANCE_FEB = (
    "Analyse the February finance invoice expense and accounting records "
    "and summarize the reconciled totals for the finance team"
)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'review-authority.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    seed = Session()
    seed.add_all([
        Tenant(id="default", name="Personal", subdomain="personal"),
        Workspace(id="ws-test", name="Test", tenant_id="default"),
        Workspace(id="ws-other", name="Other", tenant_id="default"),
    ])
    seed.add_all([
        User(
            id="lead-1", tenant_id="default", workspace_id="ws-test",
            email="lead@example.com", first_name="Lead", last_name="One",
            role="team_lead", status="active", is_active=True),
        User(
            id="member-1", tenant_id="default", workspace_id="ws-test",
            email="member@example.com", first_name="Member", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="supervisor-1", tenant_id="default", workspace_id="ws-test",
            email="supervisor@example.com", first_name="Supervisor",
            last_name="One", role="team_lead", status="active",
            is_active=True),
        User(
            id="admin-1", tenant_id="default", workspace_id="ws-test",
            email="admin@example.com", first_name="Admin", last_name="One",
            role="admin", status="active", is_active=True),
        User(
            id="lead-other", tenant_id="default", workspace_id="ws-other",
            email="other@example.com", first_name="Other", last_name="Lead",
            role="team_lead", status="active", is_active=True),
        User(
            id="inactive-lead", tenant_id="default", workspace_id="ws-test",
            email="inactive@example.com", first_name="Inactive",
            last_name="Lead", role="team_lead", status="inactive",
            is_active=False),
        User(
            id="personal", tenant_id=None, workspace_id=None,
            email="personal@example.com", first_name="Personal",
            last_name="Owner", role="team_lead", status="active",
            is_active=True),
        User(
            id="personal-other", tenant_id=None, workspace_id=None,
            email="personal-other@example.com", first_name="Personal",
            last_name="Other", role="team_lead", status="active",
            is_active=True),
    ])
    seed.add(AgentRegistry(
        id="agent-lead-1",
        name="Lead One Agent",
        category="Operations",
        role="agent",
        type="personal",
        capabilities=[],
        module_path="operations.test",
        class_name="TestAgent",
        user_id="lead-1",
        status="autonomous",
        confidence_score=0.95,
        configuration={},
        tenant_id="default",
        workspace_id="ws-test",
    ))
    seed.commit()
    seed.close()

    @contextlib.contextmanager
    def service_session():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    # Every status writer in this test uses the SAME scratch store.
    monkeypatch.setattr(
        "core.intervention_service.get_db_session", service_session)
    monkeypatch.setattr(
        "core.generic_agent.get_db_session", service_session)
    monkeypatch.setattr(
        "core.workflow_engine.get_db_session", service_session)
    monkeypatch.setattr(
        "core.hitl_service.get_db_session", service_session)
    monkeypatch.setattr("core.atom_meta_agent.SessionLocal", Session)

    yield SimpleNamespace(
        engine=engine, Session=Session, service_session=service_session)

    engine.dispose()


def _client(env, user_id: str, router_obj):
    db = env.Session()
    try:
        user = db.query(User).filter(User.id == user_id).one()
    finally:
        db.close()
    app = FastAPI()
    app.include_router(router_obj)

    def db_override():
        session = env.Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = db_override
    return TestClient(app, raise_server_exceptions=False)


def _row(env, action_id):
    db = env.Session()
    try:
        return db.query(HITLAction).filter(HITLAction.id == action_id).one()
    finally:
        db.close()


def _job(
    env, execution: str, task: str = FINANCE_JAN, *,
    user: str = "lead-1", workspace: str = "ws-test",
    tenant: str = "default", agent_id: str = "agent-lead-1",
):
    """Create the real pending task-admission row the runtime would file."""
    db = env.Session()
    try:
        rule = ap.create_never_rule(
            db, user,
            name=f"Always review finance {execution}",
            match={"domain": ["finance"]},
            tenant_id=tenant if tenant != "default" else None,
            workspace_id=workspace if workspace != "default" else None,
        )
        profile = build_task_profile(task, user_id=user)
        decision = ap.evaluate_task_admission(
            db, profile, task_material=task, agent_id=agent_id,
            user_id=user, execution_id=execution, tenant_id=tenant,
            workspace_id=workspace)
        assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW
        gov = AgentGovernanceService(
            db, workspace_id=workspace, tenant_id=tenant)
        action_id = gov.request_approval(
            agent_id=agent_id,
            action_type=ap.NEVER_TASK_ADMISSION_ACTION,
            params=ap.task_admission_params(
                decision, execution_id=execution, profile=profile,
                extra={"task_input": task}),
            reason=decision.get("reason") or (
                "A never-autonomous task rule matched this task."),
            execution_context={
                "execution_id": execution,
                "workspace_id": workspace,
                "tenant_id": tenant,
                "user_id": user,
            },
            user_id=user,
        )
        return SimpleNamespace(
            action_id=action_id, decision=decision, profile=profile,
            rule=rule, task=task, execution=execution, user=user,
            workspace=workspace, tenant=tenant, agent_id=agent_id,
        )
    finally:
        db.close()


def _evaluate(env, job):
    db = env.Session()
    try:
        profile = build_task_profile(job.task, user_id=job.user)
        return ap.evaluate_task_admission(
            db, profile, task_material=job.task, agent_id=job.agent_id,
            user_id=job.user, execution_id=job.execution,
            tenant_id=job.tenant, workspace_id=job.workspace)
    finally:
        db.close()


def _approve_row(env, action_id: str, reviewer: str):
    db = env.Session()
    try:
        db.query(User).filter(User.id == reviewer).one()
        row = db.query(HITLAction).filter(HITLAction.id == action_id).one()
        row.status = HITLActionStatus.APPROVED.value
        row.reviewed_by = reviewer
        row.reviewed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _set_required_role(env, action_id: str, *, column=None, snapshot=None):
    db = env.Session()
    try:
        row = db.query(HITLAction).filter(HITLAction.id == action_id).one()
        if column is not None:
            row.required_role = column
        if snapshot is not None:
            context = dict(row.context_snapshot or {})
            context["required_role"] = snapshot
            row.context_snapshot = context
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------- root counter


def test_foreign_team_lead_cannot_approve_and_cannot_mint_cold_clearance(env):
    """ROOT counter: a real active team_lead from ANOTHER workspace POSTs the
    mounted governance approve route for a real pending task admission."""
    from api.agent_governance_routes import router as governance_router

    job = _job(env, "exec-root-foreign")

    response = _client(env, "lead-other", governance_router).post(
        f"/api/agent-governance/approve/{job.action_id}")
    assert response.status_code == 404, response.text

    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.PENDING.value
    assert row.reviewed_by is None
    assert _evaluate(env, job).get("durable_admission") is None

    # The persisted owner in the SAME exact scope still approves normally.
    approved = _client(env, "lead-1", governance_router).post(
        f"/api/agent-governance/approve/{job.action_id}")
    assert approved.status_code == 200, approved.text
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "lead-1"
    receipt = _evaluate(env, job).get("durable_admission")
    assert receipt is not None
    assert receipt["hitl_action_id"] == job.action_id
    assert receipt["approved_by"] == "lead-1"


def test_in_scope_member_and_inactive_reviewer_are_refused(env):
    from api.approvals_routes import router as alias_router
    from core.intervention_service import intervention_service

    job = _job(env, "exec-in-scope")

    member = _client(env, "member-1", alias_router).post(
        f"/api/agents/approvals/{job.action_id}",
        json={"decision": "approved"})
    assert member.status_code == 403, member.text
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value

    inactive = asyncio.run(intervention_service.approve_intervention(
        job.action_id, "inactive-lead"))
    assert inactive.get("success") is False
    assert inactive.get("error_code") == "ACCOUNT_INACTIVE"
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value

    # An in-scope supervisor (not the owner) is a legitimate reviewer.
    supervisor = _client(env, "supervisor-1", alias_router).post(
        f"/api/agents/approvals/{job.action_id}",
        json={"decision": "approved"})
    assert supervisor.status_code == 200, supervisor.text
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "supervisor-1"
    receipt = _evaluate(env, job).get("durable_admission")
    assert receipt["approved_by"] == "supervisor-1"


def test_required_role_is_enforced_at_both_persisted_locations(env):
    from api.agent_governance_routes import router as governance_router

    job = _job(env, "exec-required-role")
    client = _client(env, "lead-1", governance_router)

    _set_required_role(env, job.action_id, column="admin")
    first = client.post(f"/api/agent-governance/approve/{job.action_id}")
    assert first.status_code == 403, first.text
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value

    _set_required_role(env, job.action_id, column="team_lead", snapshot="admin")
    second = client.post(f"/api/agent-governance/approve/{job.action_id}")
    assert second.status_code == 403, second.text
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value

    _set_required_role(
        env, job.action_id, column="team_lead", snapshot="team_lead")
    third = client.post(f"/api/agent-governance/approve/{job.action_id}")
    assert third.status_code == 200, third.text
    assert _row(env, job.action_id).status == HITLActionStatus.APPROVED.value


def test_reviewer_authority_fence_observes_peer_role_or_scope_change(env):
    from core.review_decision_authority import (
        authorize_task_admission_decision,
        claim_task_admission_reviewer,
    )

    for index, column, value in (
        ("role", "role", "member"),
        ("workspace", "workspace_id", "ws-other"),
    ):
        job = _job(env, f"exec-fence-{index}")
        db = env.Session()
        try:
            row = db.query(HITLAction).filter(
                HITLAction.id == job.action_id).one()
            check = authorize_task_admission_decision(
                db, row, "lead-1")
            assert check.get("ok") is True

            peer = env.Session()
            try:
                user = peer.query(User).filter(User.id == "lead-1").one()
                setattr(user, column, value)
                peer.commit()
            finally:
                peer.close()
            assert claim_task_admission_reviewer(
                db, check["authority"]) is False
            db.rollback()
        finally:
            db.close()
            # Restore the actor for the next iteration.
            restore = env.Session()
            try:
                user = restore.query(User).filter(User.id == "lead-1").one()
                user.role = "team_lead"
                user.workspace_id = "ws-test"
                restore.commit()
            finally:
                restore.close()
        assert _row(env, job.action_id).status == (
            HITLActionStatus.PENDING.value)


# ------------------------------------------------ load→claim decision race


def _after_load_peer(monkeypatch, hook):
    """Commit a peer Session mutation after authorize/load, before the claim.

    The decision writers import the authority seam inside the method, so
    patching the module attribute interleaves a REAL second SQLAlchemy
    Session exactly in the window the stale write used to win.
    """
    from core import review_decision_authority

    original = review_decision_authority.authorize_task_admission_decision

    def _wrapped(db, action, reviewer, **kwargs):
        check = original(db, action, reviewer, **kwargs)
        hook()
        return check

    monkeypatch.setattr(
        review_decision_authority,
        "authorize_task_admission_decision", _wrapped)


def _peer_decide(env, action_id: str, status: str, reviewer: str,
                 feedback=None):
    peer = env.Session()
    try:
        row = peer.query(HITLAction).filter(HITLAction.id == action_id).one()
        row.status = status
        row.reviewed_by = reviewer
        row.reviewed_at = datetime.now(timezone.utc)
        if feedback is not None:
            row.user_feedback = feedback
        peer.commit()
    finally:
        peer.close()


def _peer_rewrite_binding(env, action_id: str):
    peer = env.Session()
    try:
        row = peer.query(HITLAction).filter(HITLAction.id == action_id).one()
        params = dict(row.params or {})
        params["task_fingerprint"] = "0" * 64
        row.params = params
        peer.commit()
    finally:
        peer.close()


def test_peer_rejection_between_load_and_claim_wins(env, monkeypatch):
    """The reproduced race: a real second DB session rejects AFTER the
    approver loaded/authorized the pending row. The stale approval must not
    overwrite it; it answers a 409 conflict."""
    from core.intervention_service import intervention_service

    job = _job(env, "exec-race-reject")
    _after_load_peer(monkeypatch, lambda: _peer_decide(
        env, job.action_id, HITLActionStatus.REJECTED.value,
        "supervisor-1", "peer rejected"))

    stale = asyncio.run(intervention_service.approve_intervention(
        job.action_id, "lead-1"))

    assert stale.get("success") is False
    assert stale.get("http_status") == 409
    assert stale.get("error_code") == "TASK_ADMISSION_DECISION_CONFLICT"
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.REJECTED.value
    assert row.reviewed_by == "supervisor-1"
    assert row.user_feedback == "peer rejected"
    assert _evaluate(env, job).get("durable_admission") is None


def test_peer_approval_between_load_and_claim_beats_stale_rejection(
    env, monkeypatch,
):
    from core.intervention_service import intervention_service

    job = _job(env, "exec-race-approve")
    _after_load_peer(monkeypatch, lambda: _peer_decide(
        env, job.action_id, HITLActionStatus.APPROVED.value,
        "supervisor-1"))

    stale = asyncio.run(intervention_service.reject_intervention(
        job.action_id, "lead-1", "stale rejection"))

    assert stale.get("success") is False
    assert stale.get("http_status") == 409
    assert stale.get("error_code") == "TASK_ADMISSION_DECISION_CONFLICT"
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "supervisor-1"
    assert _evaluate(env, job).get("durable_admission") is not None


def test_peer_binding_rewrite_between_load_and_claim_blocks_stale_approval(
    env, monkeypatch,
):
    from core.intervention_service import intervention_service

    job = _job(env, "exec-race-binding")
    _after_load_peer(
        monkeypatch, lambda: _peer_rewrite_binding(env, job.action_id))

    stale = asyncio.run(intervention_service.approve_intervention(
        job.action_id, "lead-1"))

    assert stale.get("success") is False
    assert stale.get("http_status") == 409
    assert stale.get("error_code") == "TASK_ADMISSION_DECISION_CONFLICT"
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.PENDING.value
    assert row.reviewed_by is None
    assert row.params["task_fingerprint"] == "0" * 64
    assert _evaluate(env, job).get("durable_admission") is None


def test_two_loaded_reviewers_only_one_decision_claim_wins(env):
    """Two real sessions load/authorize the same pending row; exactly one
    conditional decision claim may win."""
    from core.review_decision_authority import (
        authorize_task_admission_decision,
        claim_task_admission_decision,
    )

    job = _job(env, "exec-race-one-winner")
    first = env.Session()
    second = env.Session()
    try:
        row_first = first.query(HITLAction).filter(
            HITLAction.id == job.action_id).one()
        row_second = second.query(HITLAction).filter(
            HITLAction.id == job.action_id).one()
        assert authorize_task_admission_decision(
            first, row_first, "lead-1").get("ok") is True
        assert authorize_task_admission_decision(
            second, row_second, "supervisor-1").get("ok") is True
        # End the second reader's read transaction so the winner's commit is
        # visible to its claim instead of being hidden by SQLite's snapshot.
        second.commit()

        assert claim_task_admission_decision(
            first, row_first,
            status=HITLActionStatus.APPROVED.value,
            reviewer_id="lead-1") is True
        first.commit()

        assert claim_task_admission_decision(
            second, row_second,
            status=HITLActionStatus.REJECTED.value,
            reviewer_id="supervisor-1") is False
        second.rollback()
    finally:
        first.close()
        second.close()

    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "lead-1"
    assert _evaluate(env, job).get("durable_admission") is not None


def test_messaging_writer_cannot_overwrite_peer_decision_after_load(
    env, monkeypatch,
):
    from core.hitl_service import HITLService

    job = _job(env, "exec-race-hitl-service")
    _after_load_peer(monkeypatch, lambda: _peer_decide(
        env, job.action_id, HITLActionStatus.REJECTED.value,
        "supervisor-1", "peer rejected"))

    stale = asyncio.run(HITLService().resolve_action(
        job.action_id, "approved", "lead-1"))

    assert stale.get("message") == "Action already resolved"
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.REJECTED.value
    assert row.reviewed_by == "supervisor-1"


def test_mounted_legacy_route_returns_conflict_on_peer_approval(
    env, monkeypatch,
):
    from api.agent_routes import router as legacy_router

    job = _job(env, "exec-race-route")
    _after_load_peer(monkeypatch, lambda: _peer_decide(
        env, job.action_id, HITLActionStatus.APPROVED.value,
        "supervisor-1"))

    response = _client(env, "admin-1", legacy_router).post(
        f"/api/agents/approvals/{job.action_id}",
        json={"decision": "rejected", "feedback": "stale route reject"})

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == (
        "TASK_ADMISSION_DECISION_CONFLICT")
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "supervisor-1"


def test_reject_also_requires_scope_and_owner_or_supervisor(env):
    from core.intervention_service import intervention_service

    job = _job(env, "exec-reject-scope")
    refused = asyncio.run(intervention_service.reject_intervention(
        job.action_id, "lead-other", "not mine"))
    assert refused.get("success") is False
    assert refused.get("http_status") == 404
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value

    rejected = asyncio.run(intervention_service.reject_intervention(
        job.action_id, "lead-1", "owner says no"))
    assert rejected.get("success") is True
    assert _row(env, job.action_id).status == HITLActionStatus.REJECTED.value


def test_messaging_2fa_writer_also_refuses_foreign_reviewer(env):
    from core.hitl_service import HITLService

    job = _job(env, "exec-hitl-service")
    with pytest.raises(ValueError, match="outside your workspace"):
        asyncio.run(HITLService().resolve_action(
            job.action_id, "approved", "lead-other"))
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value

    result = asyncio.run(HITLService().resolve_action(
        job.action_id, "approved", "lead-1"))
    assert result == {"status": "approved"}
    row = _row(env, job.action_id)
    assert row.status == HITLActionStatus.APPROVED.value
    assert row.reviewed_by == "lead-1"
    assert _evaluate(env, job).get("durable_admission") is not None


# ------------------------------------------------------- immutable binding


def test_modified_params_cannot_rewrite_task_binding_on_either_alias(env):
    from api.agent_routes import router as legacy_router
    from api.approvals_routes import router as alias_router
    from core.intervention_service import intervention_service

    for index, (router_obj, actor) in enumerate((
        (legacy_router, "admin-1"), (alias_router, "lead-1"),
    )):
        job = _job(env, f"exec-immutable-{index}")
        response = _client(env, actor, router_obj).post(
            f"/api/agents/approvals/{job.action_id}",
            json={
                "decision": "approved",
                "modified_params": {"task_fingerprint": "deadbeef"},
            })
        assert response.status_code == 409, response.text
        row = _row(env, job.action_id)
        assert row.status == HITLActionStatus.PENDING.value
        assert row.params["task_fingerprint"] == job.decision[
            "task_fingerprint"]

    job = _job(env, "exec-immutable-service")
    refused = asyncio.run(intervention_service.approve_intervention(
        job.action_id, "lead-1",
        modified_params={"rule_bindings": []}))
    assert refused.get("success") is False
    assert refused.get("error_code") == "TASK_ADMISSION_REVIEW_IMMUTABLE"
    assert _row(env, job.action_id).status == HITLActionStatus.PENDING.value


# ------------------------------------------------------- cold receipt read


def _insert_receipt(
    env, *, execution: str, task: str = FINANCE_JAN,
    owner: str = "lead-1", workspace="ws-test", tenant="default",
    agent_id: str = "agent-lead-1", status: str = "approved",
    reviewed_by="lead-1", reviewed_at=True, mutator=None,
):
    db = env.Session()
    try:
        # A global (owner-level) rule keeps the receipt/evaluation scope the
        # variable under test instead of the rule's own scope filter.
        ap.create_never_rule(
            db, owner, name=f"Always review finance {execution}",
            match={"domain": ["finance"]})
        profile = build_task_profile(task, user_id=owner)
        decision = ap.evaluate_task_admission(
            db, profile, task_material=task, agent_id=agent_id,
            user_id=owner, execution_id=execution, tenant_id=tenant,
            workspace_id=workspace)
        assert decision["outcome"] == ap.NEVER_OUTCOME_REVIEW, decision
        params = ap.task_admission_params(
            decision, execution_id=execution, profile=profile,
            extra={"task_input": task})
        if mutator is not None:
            mutator(params)
        action_id = f"hitl-cold-{execution}"
        db.add(HITLAction(
            id=action_id,
            workspace_id=workspace,
            tenant_id=tenant,
            agent_id=agent_id,
            action_type=ap.NEVER_TASK_ADMISSION_ACTION,
            platform="internal",
            params=params,
            status=status,
            reason=decision.get("reason"),
            user_id=owner,
            reviewed_by=reviewed_by,
            reviewed_at=(
                datetime.now(timezone.utc) if reviewed_at else None),
        ))
        db.commit()
        return SimpleNamespace(
            action_id=action_id, task=task, execution=execution,
            user=owner, workspace=workspace, tenant=tenant,
            agent_id=agent_id, decision=decision)
    finally:
        db.close()


def _evaluate_scope(env, job, workspace, tenant):
    db = env.Session()
    try:
        profile = build_task_profile(job.task, user_id=job.user)
        return ap.evaluate_task_admission(
            db, profile, task_material=job.task, agent_id=job.agent_id,
            user_id=job.user, execution_id=job.execution,
            tenant_id=tenant, workspace_id=workspace)
    finally:
        db.close()


@pytest.mark.parametrize("case", [
    "missing_reviewer",
    "unknown_reviewer",
    "inactive_reviewer",
    "foreign_reviewer",
    "executed_missing_reviewer",
    "missing_reviewed_at",
    "column_required_role",
    "snapshot_required_role",
    "missing_task_profile",
    "rewritten_rule_binding",
    "owner_mismatch",
    "scope_mismatch",
])
def test_cold_receipt_rejects_unqualified_reviewer_or_malformed_binding(
    env, case,
):
    execution = f"exec-cold-{case}"
    kwargs = {}
    mutator = None
    if case == "missing_reviewer":
        kwargs["reviewed_by"] = None
    elif case == "unknown_reviewer":
        kwargs["reviewed_by"] = "ghost"
    elif case == "inactive_reviewer":
        kwargs["reviewed_by"] = "inactive-lead"
    elif case == "foreign_reviewer":
        kwargs["reviewed_by"] = "lead-other"
    elif case == "executed_missing_reviewer":
        kwargs["status"] = "executed"
        kwargs["reviewed_by"] = "ghost"
    elif case == "missing_reviewed_at":
        kwargs["reviewed_at"] = False
    elif case == "missing_task_profile":
        def mutator(params):
            params.pop("task_profile", None)
        kwargs["mutator"] = mutator
    elif case == "rewritten_rule_binding":
        def mutator(params):
            params["rule_bindings"] = [{"id": "fake-rule", "revision": 99}]
        kwargs["mutator"] = mutator
    elif case == "scope_mismatch":
        kwargs["workspace"] = "ws-other"

    job = _insert_receipt(env, execution=execution, **kwargs)
    if case == "owner_mismatch":
        db = env.Session()
        try:
            row = db.query(HITLAction).filter(
                HITLAction.id == job.action_id).one()
            params = dict(row.params or {})
            params["owner_user_id"] = "member-1"
            profile = dict(params.get("task_profile") or {})
            profile["owner_user_id"] = "member-1"
            params["task_profile"] = profile
            row.params = params
            row.user_id = "member-1"
            db.commit()
        finally:
            db.close()
    if case in ("column_required_role", "snapshot_required_role"):
        _set_required_role(
            env, job.action_id,
            column="admin" if case == "column_required_role" else "team_lead",
            snapshot=(
                "team_lead" if case == "column_required_role" else "admin"))

    if case == "scope_mismatch":
        # The receipt lives in ws-other; this evaluation is ws-test.
        assert _evaluate_scope(
            env, job, "ws-test", "default").get("durable_admission") is None
        return
    assert _evaluate(env, job).get("durable_admission") is None


def test_cold_receipt_accepts_only_the_exact_authorized_owner(env):
    job = _insert_receipt(env, execution="exec-cold-valid")
    receipt = _evaluate(env, job).get("durable_admission")
    assert receipt is not None
    assert receipt["hitl_action_id"] == job.action_id
    assert receipt["approved_by"] == "lead-1"

    # The same approval cannot be reused by a different execution.
    other = SimpleNamespace(
        **{**job.__dict__, "execution": "exec-cold-other"})
    assert _evaluate(env, other).get("durable_admission") is None

    # ``executed`` stays accepted when the human provenance is real.
    executed = _insert_receipt(
        env, execution="exec-cold-executed", status="executed")
    assert _evaluate(env, executed).get("durable_admission") is not None


def test_personal_null_scope_receipt_is_the_default_scope(env):
    """Personal Edition persists NULL; the literal "default" is the same
    scope. A real active owner must still validate."""
    job = _insert_receipt(
        env, execution="exec-personal", owner="personal",
        workspace=None, tenant=None, reviewed_by="personal")
    receipt = _evaluate(env, job).get("durable_admission")
    assert receipt is not None
    assert receipt["approved_by"] == "personal"

    foreign = _insert_receipt(
        env, execution="exec-personal-foreign", owner="personal",
        workspace=None, tenant=None, reviewed_by="inactive-lead")
    assert _evaluate(env, foreign).get("durable_admission") is None


# ---------------------------------------------------------- warm re-reads


def _approve_during_wait(env, reviewer: str):
    async def _wait(action_id: str) -> bool:
        _approve_row(env, action_id, reviewer)
        return True

    return _wait


def _finance_rule(env, user: str = "lead-1"):
    db = env.Session()
    try:
        return ap.create_never_rule(
            db, user, name=f"Always review finance {uuid.uuid4().hex}",
            match={"domain": ["finance"]})
    finally:
        db.close()


def test_warm_generic_reads_the_exact_authorized_receipt(env):
    from core.generic_agent import GenericAgent

    _finance_rule(env)
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = "agent-lead-1"
    agent.workspace_id = "ws-test"
    agent.tenant_id = "default"

    # A status-only approval by a foreign reviewer must not clear the task.
    context = {"user_id": "lead-1", "workspace_id": "ws-test",
               "tenant_id": "default", "execution_id": "exec-warm-foreign"}
    profile = build_task_profile(FINANCE_JAN, user_id="lead-1")
    token = bind_task_profile(context, profile)
    try:
        agent._wait_for_approval = _approve_during_wait(env, "lead-other")
        blocked = asyncio.run(
            agent._admit_never_autonomous_task(FINANCE_JAN, context))
        assert blocked is not None
        assert blocked["status"] == "awaiting_approval"
        assert "could not be verified" in blocked["output"]
        assert ap.NEVER_CLEARANCE_CONTEXT_KEY not in context

        # The real owner's approval is the exact receipt and clears it.
        context["execution_id"] = "exec-warm-owner"
        profile2 = build_task_profile(FINANCE_FEB, user_id="lead-1")
        reset_task_profile(token)
        token = bind_task_profile(context, profile2)
        agent._wait_for_approval = _approve_during_wait(env, "lead-1")
        assert asyncio.run(
            agent._admit_never_autonomous_task(FINANCE_FEB, context)) is None
        db = env.Session()
        try:
            decision = ap.evaluate_task_admission(
                db, profile2, task_material=FINANCE_FEB,
                agent_id="agent-lead-1", user_id="lead-1",
                execution_id="exec-warm-owner",
                tenant_id="default", workspace_id="ws-test")
        finally:
            db.close()
        assert ap.has_never_autonomous_clearance(
            context, decision=decision) is True
    finally:
        reset_task_profile(token)


def test_warm_meta_reads_the_exact_authorized_receipt(env):
    from core.atom_meta_agent import AtomMetaAgent

    _finance_rule(env)
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.workspace_id = "ws-test"
    agent.tenant_id = "default"
    agent.user = None

    context = {"user_id": "lead-1", "workspace_id": "ws-test",
               "tenant_id": "default", "execution_id": "exec-meta-foreign"}
    profile = build_task_profile(FINANCE_JAN, user_id="lead-1")
    token = bind_task_profile(context, profile)
    try:
        agent._wait_for_approval = _approve_during_wait(env, "lead-other")
        blocked = asyncio.run(
            agent._admit_never_autonomous_task(FINANCE_JAN, context))
        assert blocked is not None
        assert blocked["status"] == "awaiting_approval"
        assert ap.NEVER_CLEARANCE_CONTEXT_KEY not in context

        context["execution_id"] = "exec-meta-owner"
        profile2 = build_task_profile(FINANCE_FEB, user_id="lead-1")
        reset_task_profile(token)
        token = bind_task_profile(context, profile2)
        agent._wait_for_approval = _approve_during_wait(env, "lead-1")
        assert asyncio.run(
            agent._admit_never_autonomous_task(FINANCE_FEB, context)) is None
        assert ap.NEVER_CLEARANCE_CONTEXT_KEY in context
    finally:
        reset_task_profile(token)


@pytest.mark.asyncio
async def test_warm_workflow_reads_the_exact_authorized_receipt(env, monkeypatch):
    from core.workflow_engine import WorkflowEngine

    _finance_rule(env)
    engine = WorkflowEngine()
    state_manager = SimpleNamespace(
        update_execution_status=_async_noop(),
        get_execution_state=_async_none(),
    )
    engine.state_manager = state_manager
    monkeypatch.setattr(
        engine, "_notify_workflow_paused", lambda *a, **k: None)
    conn = SimpleNamespace(notify_workflow_status=_async_noop())
    monkeypatch.setattr("core.workflow_engine.get_connection_manager",
                        lambda: conn)

    workflow = {
        "id": "wf-review-authority",
        "name": "January finance reconciliation analysis",
        "description": "Reconcile finance invoice accounting records",
        "agent_id": "agent-lead-1",
        "steps": [{"id": "s1", "service": "ai", "action": "analyze"}],
    }
    profile = build_task_profile(FINANCE_JAN, user_id="lead-1")
    token = bind_task_profile(None, profile)
    try:
        assert await engine._admit_never_autonomous_task(
            "exec-wf-authority", workflow, {"steps": {}}, "lead-1",
            "ws-test", "default") == "paused"
        db = env.Session()
        try:
            rows = db.query(HITLAction).filter(
                HITLAction.action_type == ap.NEVER_TASK_ADMISSION_ACTION
            ).all()
            assert len(rows) == 1
            action_id = rows[0].id
        finally:
            db.close()

        # A foreign status-only approval is not a receipt: the workflow
        # pauses again and mints no clearance.
        _approve_row(env, action_id, "lead-other")
        ap.clear_current_never_autonomous_clearance()
        assert await engine._admit_never_autonomous_task(
            "exec-wf-authority", workflow, {"steps": {}}, "lead-1",
            "ws-test", "default") == "paused"
        assert ap.current_never_autonomous_clearance() is None

        # The exact owner approval is the durable receipt and resumes.
        db = env.Session()
        try:
            row = db.query(HITLAction).filter(
                HITLAction.id == action_id).one()
            row.reviewed_by = "lead-1"
            row.reviewed_at = datetime.now(timezone.utc)
            db.commit()
        finally:
            db.close()
        assert await engine._admit_never_autonomous_task(
            "exec-wf-authority", workflow, {"steps": {}}, "lead-1",
            "ws-test", "default") is None
        assert ap.current_never_autonomous_clearance() is not None
    finally:
        ap.clear_current_never_autonomous_clearance()
        reset_task_profile(token)


def _async_noop():
    async def _noop(*args, **kwargs):
        return None

    return _noop


def _async_none():
    async def _none(*args, **kwargs):
        return None

    return _none
