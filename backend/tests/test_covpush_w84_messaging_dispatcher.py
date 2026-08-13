# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/messaging_action_dispatcher (standalone, mocked
governance/intervention services, real in-memory SQLite for User/AgentProposal).

- dispatch_action: missing action_id, provided db, session-managed db
  (get_db_session context), passthrough of _execute_dispatch results.
- _execute_dispatch: unknown action_type, user-not-found, proposal
  approve/reject (±missing proposal, reason from payload value), intervention
  approval (approve_intervention call arity — bug-fix regression test:
  dispatcher previously passed (action_id, tenant_id, user_id) to a
  two-argument API → TypeError on every intervention_approve), feedback
  thumbs up/down (incl. AttributeError → service unavailable), unknown
  feedback subtype, inner exception → generic error envelope.
- _map_to_gov_action: approve/delete/update/read.
- get_messaging_action_dispatcher: singleton + lock path + db injection.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.messaging_action_dispatcher import MessagingActionDispatcher
from core.models import AgentProposal, AgentRegistry, User


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1", tenant_id="t1"):
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="admin",
        status="active",
    )
    db.add(user)
    db.commit()
    return user


def _make_agent(db, agent_id="agent-1"):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id="t1",
        category="Test",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _make_proposal(db, proposal_id="prop-1", tenant_id="t1", agent_id="agent-1"):
    _make_agent(db, agent_id=agent_id)
    proposal = AgentProposal(
        id=proposal_id,
        tenant_id=tenant_id,
        user_id="user-1",
        agent_id=agent_id,
        title="Test proposal",
        proposal_type="action",
        proposal_data={"action": "send_email", "params": {}},
        status="pending_approval",
    )
    db.add(proposal)
    db.commit()
    return proposal


@pytest.fixture(autouse=True)
def _patch_services():
    with patch("core.messaging_action_dispatcher.AgentGovernanceService") as gov_cls, \
            patch("core.messaging_action_dispatcher.InterventionService") as int_cls:
        gov = gov_cls.return_value
        gov.submit_thumbs_feedback = AsyncMock()
        int_cls.return_value.approve_intervention = AsyncMock(return_value=True)
        yield {"gov": gov, "gov_cls": gov_cls, "int_cls": int_cls}


# ============================================================================
# dispatch_action
# ============================================================================

class TestDispatchAction:
    async def test_missing_action_id_empty(self):
        result = await MessagingActionDispatcher(db=MagicMock()).dispatch_action(
            "slack", "t1", "u1", "", {"x": 1})
        assert result["success"] is False
        assert "action_id" in result["error"]

    async def test_missing_action_id_none(self):
        result = await MessagingActionDispatcher(db=MagicMock()).dispatch_action(
            "slack", "t1", "u1", None, {})
        assert result["success"] is False

    async def test_uses_provided_db(self):
        dispatcher = MessagingActionDispatcher(db="fake-db")
        with patch.object(dispatcher, "_execute_dispatch",
                          new=AsyncMock(return_value={"success": True})) as exec_mock:
            result = await dispatcher.dispatch_action("slack", "t1", "u1", "a:b", {})
        exec_mock.assert_awaited_once_with("fake-db", "slack", "t1", "u1", "a:b", {})
        assert result == {"success": True}

    async def test_uses_session_db_when_none(self):
        dispatcher = MessagingActionDispatcher()
        fake_db = MagicMock()
        with patch("core.messaging_action_dispatcher.get_db_session") as gds, \
                patch.object(dispatcher, "_execute_dispatch",
                             new=AsyncMock(return_value={"success": True})) as exec_mock:
            gds.return_value.__enter__ = MagicMock(return_value=fake_db)
            gds.return_value.__exit__ = MagicMock(return_value=False)
            result = await dispatcher.dispatch_action("slack", "t1", "u1", "a:b", {})
        exec_mock.assert_awaited_once_with(fake_db, "slack", "t1", "u1", "a:b", {})
        assert result == {"success": True}


# ============================================================================
# _execute_dispatch
# ============================================================================

class TestExecuteDispatch:
    async def test_user_not_found(self, db):
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action("slack", "t1", "ghost", "approve_proposal:x", {})
        assert result == {"success": False, "error": "User not found or access denied"}

    async def test_unknown_action_type(self, db):
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action("slack", "t1", "user-1", "mystery:1", {})
        assert result == {"success": False, "error": "Unknown action: mystery"}

    async def test_proposal_approve(self, db, _patch_services):
        _make_user(db)
        _make_proposal(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "approve_proposal:prop-1", {"value": "Looks good"})
        assert result == {"success": True, "message": "Proposal approved"}
        proposal = db.query(AgentProposal).filter_by(id="prop-1").first()
        assert proposal.status == "approved"
        assert proposal.approver_type == "user"
        assert proposal.approver_id == "user-1"
        assert proposal.approval_reason == "Looks good"
        assert proposal.reviewed_at is not None

    async def test_proposal_approve_default_reason(self, db, _patch_services):
        _make_user(db)
        _make_proposal(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "approve_proposal:prop-1", {})
        assert result["success"] is True
        proposal = db.query(AgentProposal).filter_by(id="prop-1").first()
        assert proposal.approval_reason == "Approved"

    async def test_proposal_reject(self, db, _patch_services):
        _make_user(db)
        _make_proposal(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "reject_proposal:prop-1", {})
        assert result == {"success": True, "message": "Proposal rejected"}
        proposal = db.query(AgentProposal).filter_by(id="prop-1").first()
        assert proposal.status == "rejected"
        assert proposal.approval_reason == "Rejected"

    async def test_proposal_not_found(self, db, _patch_services):
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "approve_proposal:nope", {})
        assert result == {"success": False, "error": "Proposal not found"}

    async def test_intervention_approve_success(self, db, _patch_services):
        """Regression: dispatcher used to pass (intervention_id, tenant_id,
        user_id) to approve_intervention(action_id, approver_id) — a TypeError
        on every intervention_approve action."""
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "intervention_approve:act-1", {})
        assert result == {"success": True, "message": "Intervention approved"}
        _patch_services["int_cls"].return_value.approve_intervention.assert_awaited_once_with(
            "act-1", "user-1")

    async def test_intervention_approve_failure(self, db, _patch_services):
        _make_user(db)
        _patch_services["int_cls"].return_value.approve_intervention = \
            AsyncMock(return_value=False)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "intervention_approve:act-1", {})
        assert result == {"success": False, "message": "Approval failed"}

    async def test_feedback_thumbs_up(self, db, _patch_services):
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "feedback_thumbs", {"value": "up"})
        assert result == {"success": True, "message": "Feedback recorded"}
        _patch_services["gov"].submit_thumbs_feedback.assert_awaited_once_with(
            agent_id=None, user_id="user-1", tenant_id="t1",
            original_output="Referenced interactive message", thumbs_up=True)

    async def test_feedback_thumbs_up_true_value(self, db, _patch_services):
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "feedback_thumbs", {"value": "true"})
        assert result["success"] is True

    async def test_feedback_thumbs_down(self, db, _patch_services):
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "feedback_thumbs", {"value": "down"})
        assert result["success"] is True
        call_kwargs = _patch_services["gov"].submit_thumbs_feedback.await_args.kwargs
        assert call_kwargs["thumbs_up"] is False

    async def test_feedback_service_unavailable(self, db, _patch_services):
        _make_user(db)
        _patch_services["gov"].submit_thumbs_feedback = AsyncMock(
            side_effect=AttributeError("no method"))
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "feedback_thumbs", {"value": "up"})
        assert result == {"success": False, "error": "Feedback service unavailable"}

    async def test_feedback_unknown_subtype(self, db, _patch_services):
        _make_user(db)
        dispatcher = MessagingActionDispatcher(db=db)
        result = await dispatcher.dispatch_action(
            "slack", "t1", "user-1", "feedback_rage", {"value": "up"})
        assert result == {"success": False, "error": "Unsupported feedback type: rage"}

    async def test_inner_exception_wrapped(self, db, _patch_services):
        _make_user(db)
        _make_proposal(db)
        dispatcher = MessagingActionDispatcher(db=db)
        with patch("core.messaging_action_dispatcher.datetime") as dt:
            dt.now.side_effect = RuntimeError("clock broke")
            result = await dispatcher.dispatch_action(
                "slack", "t1", "user-1", "approve_proposal:prop-1", {})
        assert result["success"] is False
        assert result["error"] == "clock broke"


# ============================================================================
# _map_to_gov_action
# ============================================================================

class TestMapToGovAction:
    def test_approve(self):
        assert MessagingActionDispatcher()._map_to_gov_action("approve_proposal") == "approve"

    def test_delete(self):
        assert MessagingActionDispatcher()._map_to_gov_action("delete_agent") == "delete"

    def test_update(self):
        assert MessagingActionDispatcher()._map_to_gov_action("update_agent") == "update"

    def test_read_default(self):
        assert MessagingActionDispatcher()._map_to_gov_action("view_stats") == "read"


# ============================================================================
# get_messaging_action_dispatcher singleton
# ============================================================================

class TestGetDispatcher:
    def test_singleton(self):
        import core.messaging_action_dispatcher as mod
        with patch.object(mod, "_dispatcher", None), \
                patch.object(mod, "_dispatcher_lock", MagicMock()):
            d1 = mod.get_messaging_action_dispatcher()
            d2 = mod.get_messaging_action_dispatcher()
            assert d1 is d2

    def test_singleton_returns_existing(self):
        import core.messaging_action_dispatcher as mod
        existing = MagicMock()
        with patch.object(mod, "_dispatcher", existing):
            assert mod.get_messaging_action_dispatcher() is existing

    def test_injects_db(self):
        import core.messaging_action_dispatcher as mod
        fake_db = MagicMock()
        with patch.object(mod, "_dispatcher", None), \
                patch.object(mod, "_dispatcher_lock", MagicMock()):
            d = mod.get_messaging_action_dispatcher(fake_db)
            assert d._db is fake_db

    def test_uses_lock(self):
        import core.messaging_action_dispatcher as mod
        fake_db = MagicMock()
        with patch.object(mod, "_dispatcher", None):
            d = mod.get_messaging_action_dispatcher(fake_db)
            assert d._db is fake_db
