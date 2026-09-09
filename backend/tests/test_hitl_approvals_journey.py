# -*- coding: utf-8 -*-
"""HITL approvals journey (2026-09-08 pass).

The web Approvals page + chat widget drive HITL decisions through
/api/agents/approvals/* — a surface that NEVER existed on the backend
(the real surface is /api/agent-governance/* with a different shape), so
the UI approval journey 404'd end to end. Governance-configured
`required_role` was persisted on interventions but never enforced. And
the messaging dispatcher's intervention approval crashed on construction
(`InterventionService(db)` against a class with no __init__) and let any
messaging user approve proposals.

Locks:
1. InterventionService enforces the per-action required_role (case-
   insensitive, fail-closed on unknown roles, verified approver).
2. New alias surface GET /api/agents/approvals/pending (plain array) and
   POST /api/agents/approvals/{id} {decision, modified_params} with a
   supervisor gate; modified params persist to the action row.
3. /api/agent-governance/reject/{id} gets the same supervisor gate as
   approve.
4. Messaging dispatcher: proposals and interventions may only be decided
   by supervisors, via the shared singleton (construction bug gone).
"""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auth import get_current_user as auth_get_current_user
from core.database import Base, get_db
from core.models import HITLAction, HITLActionStatus, User, UserRole


@pytest.fixture()
def hitl_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for uid, role in (
        ("member-1", "member"),
        ("lead-1", "team_lead"),
        ("admin-1", "admin"),
        ("super-1", "super_admin"),
    ):
        db.add(
            User(
                id=uid,
                email=f"{uid}@example.com",
                hashed_password="x",
                first_name="T",
                last_name="U",
                role=role,
                status="active",
                is_active=True,
            )
        )
    db.commit()
    yield db
    db.close()


@pytest.fixture()
def svc(hitl_db, monkeypatch):
    from core.intervention_service import InterventionService

    @contextmanager
    def _session():
        yield hitl_db

    monkeypatch.setattr("core.intervention_service.get_db_session", _session)
    return InterventionService()


def _request(svc, **kw):
    params = {
        "workspace_id": "ws-1",
        "action_type": "send_email",
        "platform": "governance_policy",
        "params": {"to": "x@y.com", "subject": "hi"},
        "reason": "Needs review",
    }
    params.update(kw)
    return asyncio.run(svc.request_intervention(**params))["action_id"]


# ============================================================================
# 1. required_role enforcement in the service
# ============================================================================


class TestRequiredRoleEnforcement:
    def test_approve_denied_below_required_role(self, svc, hitl_db):
        action_id = _request(svc, required_role="admin")
        result = asyncio.run(svc.approve_intervention(action_id, "lead-1"))
        assert result["success"] is False, "team_lead approved an admin-required action"
        action = hitl_db.query(HITLAction).filter(HITLAction.id == action_id).first()
        assert action.status == HITLActionStatus.PENDING.value

    def test_approve_allowed_at_required_role(self, svc, hitl_db):
        action_id = _request(svc, required_role="admin")
        result = asyncio.run(svc.approve_intervention(action_id, "admin-1"))
        assert result["success"] is True, result
        action = hitl_db.query(HITLAction).filter(HITLAction.id == action_id).first()
        assert action.status == HITLActionStatus.APPROVED.value
        assert action.reviewed_by == "admin-1"

    def test_required_role_matching_is_case_insensitive(self, svc):
        action_id = _request(svc, required_role="TEAM_LEAD")
        result = asyncio.run(svc.approve_intervention(action_id, "lead-1"))
        assert result["success"] is True, result

    def test_unknown_required_role_fails_closed(self, svc, hitl_db):
        action_id = _request(svc, required_role="grand_wizard")
        result = asyncio.run(svc.approve_intervention(action_id, "super-1"))
        assert result["success"] is False, "unreadable policy must not approve"
        action = hitl_db.query(HITLAction).filter(HITLAction.id == action_id).first()
        assert action.status == HITLActionStatus.PENDING.value

    def test_unverified_approver_denied(self, svc, hitl_db):
        action_id = _request(svc)
        result = asyncio.run(svc.approve_intervention(action_id, "ghost-user"))
        assert result["success"] is False, "approver with no user row approved"

    def test_reject_enforces_required_role(self, svc, hitl_db):
        action_id = _request(svc, required_role="admin")
        result = asyncio.run(svc.reject_intervention(action_id, "lead-1", "no"))
        assert result["success"] is False
        action = hitl_db.query(HITLAction).filter(HITLAction.id == action_id).first()
        assert action.status == HITLActionStatus.PENDING.value

    def test_reject_allowed_at_required_role(self, svc, hitl_db):
        action_id = _request(svc, required_role="admin")
        result = asyncio.run(svc.reject_intervention(action_id, "admin-1", "not today"))
        assert result["success"] is True, result
        action = hitl_db.query(HITLAction).filter(HITLAction.id == action_id).first()
        assert action.status == HITLActionStatus.REJECTED.value

    def test_cannot_reject_non_pending_action(self, svc, hitl_db):
        action_id = _request(svc)
        asyncio.run(svc.approve_intervention(action_id, "lead-1"))
        result = asyncio.run(svc.reject_intervention(action_id, "lead-1", "too late"))
        assert result["success"] is False

    def test_modified_params_persist_on_approve(self, svc, hitl_db):
        action_id = _request(svc)
        modified = {"to": "corrected@y.com", "subject": "corrected"}
        result = asyncio.run(
            svc.approve_intervention(action_id, "lead-1", modified_params=modified)
        )
        assert result["success"] is True, result
        action = hitl_db.query(HITLAction).filter(HITLAction.id == action_id).first()
        assert action.params == modified


# ============================================================================
# 2. The /api/agents/approvals/* surface the frontend actually calls
# ============================================================================


def make_alias_client(hitl_db, role="team_lead", user_id="lead-1"):
    from api.approvals_routes import router as approvals_router

    app = FastAPI()
    app.include_router(approvals_router)
    user = hitl_db.query(User).filter(User.id == user_id).first()
    app.dependency_overrides[auth_get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: hitl_db
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def alias_svc(hitl_db, monkeypatch):
    @contextmanager
    def _session():
        yield hitl_db

    monkeypatch.setattr("core.intervention_service.get_db_session", _session)
    return True


class TestApprovalsAliasSurface:
    def test_pending_returns_plain_array(self, hitl_db, alias_svc):
        hitl_db.add(
            HITLAction(
                workspace_id="ws-1",
                action_type="send_email",
                platform="governance_policy",
                params={"to": "x@y.com"},
                reason="Needs review",
                status=HITLActionStatus.PENDING.value,
            )
        )
        hitl_db.commit()
        client = make_alias_client(hitl_db)
        resp = client.get("/api/agents/approvals/pending")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list), f"expected array, got {type(body)}"
        assert any(a["action_type"] == "send_email" for a in body)

    def test_decide_approved(self, hitl_db, alias_svc):
        action = HITLAction(
            workspace_id="ws-1",
            action_type="send_email",
            platform="governance_policy",
            params={"to": "x@y.com"},
            reason="r",
            status=HITLActionStatus.PENDING.value,
        )
        hitl_db.add(action)
        hitl_db.commit()
        client = make_alias_client(hitl_db)
        resp = client.post(f"/api/agents/approvals/{action.id}", json={"decision": "approved"})
        assert resp.status_code == 200, resp.text
        # GlobalChatWidget contract: decisions are confirmed via data.success
        body = resp.json()
        assert body.get("success") is True
        hitl_db.refresh(action)
        assert action.status == HITLActionStatus.APPROVED.value

    def test_decide_rejected(self, hitl_db, alias_svc):
        action = HITLAction(
            workspace_id="ws-1",
            action_type="send_email",
            platform="governance_policy",
            params={},
            reason="r",
            status=HITLActionStatus.PENDING.value,
        )
        hitl_db.add(action)
        hitl_db.commit()
        client = make_alias_client(hitl_db)
        resp = client.post(f"/api/agents/approvals/{action.id}", json={"decision": "rejected"})
        assert resp.status_code == 200, resp.text
        hitl_db.refresh(action)
        assert action.status == HITLActionStatus.REJECTED.value

    def test_decide_member_denied(self, hitl_db, alias_svc):
        client = make_alias_client(hitl_db, role="member", user_id="member-1")
        resp = client.post("/api/agents/approvals/some-action", json={"decision": "approved"})
        assert resp.status_code == 403

    def test_decide_respects_required_role(self, hitl_db, alias_svc):
        action = HITLAction(
            workspace_id="ws-1",
            action_type="send_email",
            platform="governance_policy",
            params={},
            reason="r",
            context_snapshot={"required_role": "admin"},
            status=HITLActionStatus.PENDING.value,
        )
        hitl_db.add(action)
        hitl_db.commit()
        client = make_alias_client(hitl_db, role="team_lead", user_id="lead-1")
        resp = client.post(f"/api/agents/approvals/{action.id}", json={"decision": "approved"})
        assert resp.status_code == 403, "team_lead decided an admin-required action"
        hitl_db.refresh(action)
        assert action.status == HITLActionStatus.PENDING.value

    def test_modified_params_applied(self, hitl_db, alias_svc):
        action = HITLAction(
            workspace_id="ws-1",
            action_type="send_email",
            platform="governance_policy",
            params={"to": "original@y.com"},
            reason="r",
            status=HITLActionStatus.PENDING.value,
        )
        hitl_db.add(action)
        hitl_db.commit()
        client = make_alias_client(hitl_db)
        resp = client.post(
            f"/api/agents/approvals/{action.id}",
            json={"decision": "approved", "modified_params": {"to": "fixed@y.com"}},
        )
        assert resp.status_code == 200, resp.text
        hitl_db.refresh(action)
        assert action.params == {"to": "fixed@y.com"}

    def test_pending_requires_auth(self):
        from api.approvals_routes import router as approvals_router

        app = FastAPI()
        app.include_router(approvals_router)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/agents/approvals/pending")
        assert resp.status_code in (401, 403)


# ============================================================================
# 3. reject route gets the same gate as approve
# ============================================================================


class TestGovernanceRejectGate:
    def _client(self, role):
        from api.agent_governance_routes import router

        app = FastAPI()
        app.include_router(router)
        user = MagicMock()
        user.id = "u-1"
        user.role = role
        app.dependency_overrides[auth_get_current_user] = lambda: user
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        app.dependency_overrides[get_db] = lambda: db
        return TestClient(app, raise_server_exceptions=False)

    def test_reject_member_denied(self):
        client = self._client(UserRole.MEMBER.value)
        resp = client.post("/api/agent-governance/reject/appr1?reason=nope")
        assert resp.status_code == 403, "any user can reject approvals"

    def test_reject_supervisor_allowed(self):
        client = self._client(UserRole.TEAM_LEAD.value)
        with patch("api.agent_governance_routes.intervention_service") as svc:
            svc.reject_intervention = AsyncMock(return_value={"success": True})
            resp = client.post("/api/agent-governance/reject/appr1?reason=nope")
        assert resp.status_code == 200, resp.text
        svc.reject_intervention.assert_awaited_once()


# ============================================================================
# 4. Messaging dispatcher: supervisor-only decisions, working service call
# ============================================================================


@pytest.fixture()
def msg_env(hitl_db, monkeypatch):
    @contextmanager
    def _session():
        yield hitl_db

    monkeypatch.setattr("core.intervention_service.get_db_session", _session)
    from core.messaging_action_dispatcher import MessagingActionDispatcher

    return MessagingActionDispatcher(db=hitl_db)


class TestMessagingDispatcherGates:
    def test_member_cannot_approve_proposal(self, msg_env, hitl_db):
        from core.models import AgentProposal

        proposal = AgentProposal(
            id="prop-1",
            agent_id="a1",
            tenant_id="t1",
            user_id="member-1",
            title="t",
            proposal_type="action",
            status="pending_approval",
        )
        hitl_db.add(proposal)
        hitl_db.commit()
        result = asyncio.run(
            msg_env._handle_proposal(hitl_db, "t1", "member-1", "approve_proposal", "prop-1", {})
        )
        assert result.get("success") is False, "member approved a proposal from chat"
        hitl_db.refresh(proposal)
        assert proposal.status == "pending_approval"

    def test_supervisor_can_approve_proposal(self, msg_env, hitl_db):
        from core.models import AgentProposal

        proposal = AgentProposal(
            id="prop-2",
            agent_id="a1",
            tenant_id="t1",
            user_id="lead-1",
            title="t",
            proposal_type="action",
            status="pending_approval",
        )
        hitl_db.add(proposal)
        hitl_db.commit()
        lead = hitl_db.query(User).filter(User.id == "lead-1").first()
        result = asyncio.run(
            msg_env._handle_proposal(hitl_db, "t1", lead, "approve_proposal", "prop-2", {})
        )
        assert result.get("success") is True, result
        hitl_db.refresh(proposal)
        assert proposal.status == "approved"

    def test_intervention_approve_uses_working_service_and_gates(self, msg_env, hitl_db):
        action = HITLAction(
            workspace_id="t1",
            action_type="send_email",
            platform="governance_policy",
            params={},
            reason="r",
            status=HITLActionStatus.PENDING.value,
        )
        hitl_db.add(action)
        hitl_db.commit()
        result = asyncio.run(msg_env._handle_intervention(hitl_db, "t1", "member-1", action.id))
        assert result.get("success") is False, "member approved an intervention from chat"
        result = asyncio.run(msg_env._handle_intervention(hitl_db, "t1", "lead-1", action.id))
        assert result.get("success") is True, result
