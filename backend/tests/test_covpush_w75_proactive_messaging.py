"""Coverage wave 75 — core/proactive_messaging_service.py (67% → 95%+).

Closes the remaining surface: agent-not-found, INTERN approval flow
(approve/reject 404+400, approver-not-found), naive scheduled_for
normalization, no-event-loop synchronous send (success + failure),
cancel of SENT/CANCELLED, pending/history filters, _send_message full
matrix (not-found/not-approved/success-with-workspace-context/failure/
exception), and send_scheduled_messages counting. Real in-memory SQLite;
gateway fully mocked (zero network).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,
    AgentStatus,
    ProactiveMessageStatus,
    User,
    UserRole,
    UserStatus,
)
from core.proactive_messaging_service import (
    AgentProactiveMessage,
    ProactiveMessagingService,
)

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user(db):
    u = User(email="approver@example.com", first_name="App", last_name="Rover",
             role=UserRole.MEMBER.value, status=UserStatus.ACTIVE.value)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _agent(db, status):
    a = AgentRegistry(
        name=f"Agent {status}", category="testing", module_path="test.proactive",
        class_name="ProactiveAgent", description="proactive test agent",
        status=status, confidence_score=0.8,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@pytest.fixture
def intern_agent(db):
    return _agent(db, AgentStatus.INTERN.value)


@pytest.fixture
def supervised_agent(db):
    return _agent(db, AgentStatus.SUPERVISED.value)


@pytest.fixture
def autonomous_agent(db):
    return _agent(db, AgentStatus.AUTONOMOUS.value)


@pytest.fixture
def student_agent(db):
    return _agent(db, AgentStatus.STUDENT.value)


def _pending(db, agent, **kwargs):
    msg = AgentProactiveMessage(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_maturity_level=agent.status,
        platform=kwargs.get("platform", "slack"),
        recipient_id=kwargs.get("recipient_id", "C1"),
        content=kwargs.get("content", "Hello"),
        status=ProactiveMessageStatus.PENDING.value,
        governance_metadata={},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def run(coro):
    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class TestCreate:
    def test_agent_not_found(self, db):
        svc = ProactiveMessagingService(db)
        with pytest.raises(Exception) as ei:
            svc.create_proactive_message(
                "missing", "slack", "C1", "hi")
        assert ei.value.status_code == 404

    def test_student_blocked(self, db, student_agent):
        svc = ProactiveMessagingService(db)
        with pytest.raises(Exception) as ei:
            svc.create_proactive_message(
                student_agent.id, "slack", "C1", "hi")
        assert ei.value.status_code == 403

    def test_intern_pending(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        msg = svc.create_proactive_message(
            intern_agent.id, "slack", "C1", "hi",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1))
        assert msg.status == ProactiveMessageStatus.PENDING.value

    def test_supervised_auto_approved(self, db, supervised_agent):
        svc = ProactiveMessagingService(db)
        msg = svc.create_proactive_message(
            supervised_agent.id, "slack", "C1", "hi")
        assert msg.status == ProactiveMessageStatus.APPROVED.value
        assert msg.approved_at is not None

    def test_autonomous_send_now_no_loop_sync_send(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={
                "status": "success", "message_id": "mid-1"})
            msg = svc.create_proactive_message(
                autonomous_agent.id, "slack", "C1", "hi", send_now=True)
        db.refresh(msg)
        assert msg.status == ProactiveMessageStatus.SENT.value
        assert msg.platform_message_id == "mid-1"

    def test_autonomous_send_now_sync_failure_swallowed(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(side_effect=RuntimeError("gateway down"))
            msg = svc.create_proactive_message(
                autonomous_agent.id, "slack", "C1", "hi", send_now=True)
        db.refresh(msg)
        assert msg.status == ProactiveMessageStatus.FAILED.value
        assert "gateway down" in msg.error_message

    def test_send_now_skipped_when_scheduled(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        msg = svc.create_proactive_message(
            autonomous_agent.id, "slack", "C1", "hi", send_now=True,
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2))
        assert msg.status == ProactiveMessageStatus.APPROVED.value

    def test_send_now_wrapper_catches_send_exception(self, db, autonomous_agent):
        # _send_message itself raising (beyond its own error handling) must be
        # contained by the no-loop sync wrapper
        svc = ProactiveMessagingService(db)
        with patch.object(svc, "_send_message", new=AsyncMock(side_effect=RuntimeError("boom"))):
            msg = svc.create_proactive_message(
                autonomous_agent.id, "slack", "C1", "hi", send_now=True)
        assert msg.status == ProactiveMessageStatus.APPROVED.value


class TestApprove:
    def test_approve_not_found(self, db):
        svc = ProactiveMessagingService(db)
        with pytest.raises(Exception) as ei:
            svc.approve_message("nope", "u1")
        assert ei.value.status_code == 404

    def test_approve_non_pending_rejected(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        msg.status = ProactiveMessageStatus.APPROVED.value
        db.commit()
        with pytest.raises(Exception) as ei:
            svc.approve_message(msg.id, user.id)
        assert ei.value.status_code == 400

    def test_approve_approver_not_found(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        with pytest.raises(Exception) as ei:
            svc.approve_message(msg.id, "ghost-user")
        assert ei.value.status_code == 404

    def test_approve_sends_immediately(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            out = svc.approve_message(msg.id, user.id)
        assert out.status == ProactiveMessageStatus.SENT.value
        assert out.approved_by == user.id
        assert out.sent_at is not None

    def test_approve_future_schedule_no_send(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        msg.scheduled_for = datetime.now(timezone.utc) + timedelta(hours=5)
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            out = svc.approve_message(msg.id, user.id)
        gw.execute_action.assert_not_awaited()
        assert out.status == ProactiveMessageStatus.APPROVED.value

    def test_approve_naive_scheduled_for_normalized(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        # SQLite read-back returns naive datetimes; approve must normalize
        msg.scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        msg.scheduled_for = msg.scheduled_for.replace(tzinfo=None)
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            out = svc.approve_message(msg.id, user.id)
        assert out.status == ProactiveMessageStatus.SENT.value

    def test_approve_sync_send_failure_logged(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(side_effect=RuntimeError("no loop"))
            out = svc.approve_message(msg.id, user.id)
        # _send_message itself marks the message FAILED on gateway errors
        assert out.status == ProactiveMessageStatus.FAILED.value
        assert "no loop" in out.error_message

    def test_approve_wrapper_catches_send_exception(self, db, intern_agent, user):
        # _send_message raising (beyond its own error handling) must be
        # contained by the no-loop sync wrapper in approve_message
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        with patch.object(svc, "_send_message", new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = svc.approve_message(msg.id, user.id)
        assert out.status == ProactiveMessageStatus.APPROVED.value


class TestReject:
    def test_reject_not_found(self, db):
        svc = ProactiveMessagingService(db)
        with pytest.raises(Exception) as ei:
            svc.reject_message("nope", "u1", "spam")
        assert ei.value.status_code == 404

    def test_reject_non_pending(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        msg.status = ProactiveMessageStatus.SENT.value
        db.commit()
        with pytest.raises(Exception) as ei:
            svc.reject_message(msg.id, user.id, "too late")
        assert ei.value.status_code == 400

    def test_reject_success(self, db, intern_agent, user):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        out = svc.reject_message(msg.id, user.id, "not relevant")
        assert out.status == ProactiveMessageStatus.CANCELLED.value
        assert out.rejection_reason == "not relevant"


class TestCancel:
    def test_cancel_not_found(self, db):
        svc = ProactiveMessagingService(db)
        with pytest.raises(Exception) as ei:
            svc.cancel_message("nope")
        assert ei.value.status_code == 404

    def test_cancel_sent_forbidden(self, db, supervised_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, supervised_agent)
        msg.status = ProactiveMessageStatus.SENT.value
        db.commit()
        with pytest.raises(Exception) as ei:
            svc.cancel_message(msg.id)
        assert ei.value.status_code == 400

    def test_cancel_cancelled_forbidden(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        msg.status = ProactiveMessageStatus.CANCELLED.value
        db.commit()
        with pytest.raises(Exception) as ei:
            svc.cancel_message(msg.id)
        assert ei.value.status_code == 400

    def test_cancel_pending_success(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        out = svc.cancel_message(msg.id)
        assert out.status == ProactiveMessageStatus.CANCELLED.value


class TestQueries:
    def test_get_pending_filters(self, db, intern_agent, supervised_agent):
        svc = ProactiveMessagingService(db)
        _pending(db, intern_agent, platform="slack")
        _pending(db, intern_agent, platform="discord", recipient_id="C2")
        _pending(db, supervised_agent, platform="slack", recipient_id="C3")
        assert len(svc.get_pending_messages()) == 3
        assert len(svc.get_pending_messages(agent_id=intern_agent.id)) == 2
        assert len(svc.get_pending_messages(platform="slack")) == 2
        assert len(svc.get_pending_messages(platform="slack", agent_id=supervised_agent.id)) == 1

    def test_get_message_history_filters(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        m1 = _pending(db, intern_agent, platform="slack")
        m2 = _pending(db, intern_agent, platform="discord", recipient_id="R2")
        m2.status = ProactiveMessageStatus.SENT.value
        db.commit()
        all_hist = svc.get_message_history()
        assert len(all_hist) == 2
        by_agent = svc.get_message_history(agent_id=intern_agent.id)
        assert len(by_agent) == 2
        by_recipient = svc.get_message_history(recipient_id="R2")
        assert len(by_recipient) == 1
        by_status = svc.get_message_history(status=ProactiveMessageStatus.SENT.value)
        assert len(by_status) == 1
        by_platform = svc.get_message_history(platform="discord")
        assert len(by_platform) == 1
        assert svc.get_message_history(agent_id="other") == []

    def test_get_message(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        assert svc.get_message(msg.id).id == msg.id
        assert svc.get_message("missing") is None


class TestSendMessage:
    def test_send_missing_message(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        out = run(svc._send_message("ghost"))
        assert out["status"] == "error"

    def test_send_not_approved(self, db, intern_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, intern_agent)
        out = run(svc._send_message(msg.id))
        assert out["status"] == "error"
        assert "not approved" in out["message"]

    def test_send_success_uses_agent_workspace_context(self, db, autonomous_agent):
        autonomous_agent.context = {"workspace_id": "ws-42"}
        db.commit()
        svc = ProactiveMessagingService(db)
        msg = _pending(db, autonomous_agent)
        msg.status = ProactiveMessageStatus.APPROVED.value
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={
                "status": "success", "message_id": "m-99"})
            out = run(svc._send_message(msg.id))
        assert out["status"] == "success"
        args, _ = gw.execute_action.await_args
        assert args[2]["workspace_id"] == "ws-42"
        db.refresh(msg)
        assert msg.status == ProactiveMessageStatus.SENT.value
        assert msg.platform_message_id == "m-99"

    def test_send_failure_marks_failed(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, autonomous_agent)
        msg.status = ProactiveMessageStatus.APPROVED.value
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={
                "status": "error", "error": "rate limited"})
            out = run(svc._send_message(msg.id))
        assert out["status"] == "error"
        db.refresh(msg)
        assert msg.status == ProactiveMessageStatus.FAILED.value
        assert "rate limited" in msg.error_message

    def test_send_exception_marks_failed(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, autonomous_agent)
        msg.status = ProactiveMessageStatus.APPROVED.value
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(side_effect=RuntimeError("boom"))
            out = run(svc._send_message(msg.id))
        assert out["status"] == "error"
        db.refresh(msg)
        assert msg.status == ProactiveMessageStatus.FAILED.value

    def test_send_context_error_falls_back_to_default(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, autonomous_agent)
        msg.status = ProactiveMessageStatus.APPROVED.value
        db.commit()
        # non-dict context → .get() raises → service falls back to "default"
        autonomous_agent.context = "not-a-dict"
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            out = run(svc._send_message(msg.id))
        assert out["status"] == "success"
        args, _ = gw.execute_action.await_args
        assert args[2]["workspace_id"] == "default"


class TestSendScheduled:
    def test_sends_due_approved(self, db, autonomous_agent):
        svc = ProactiveMessagingService(db)
        msg = _pending(db, autonomous_agent)
        msg.status = ProactiveMessageStatus.APPROVED.value
        msg.scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={"status": "success"})
            counts = run(svc.send_scheduled_messages())
        assert counts == {"sent": 1, "failed": 0}
        db.refresh(msg)
        assert msg.status == ProactiveMessageStatus.SENT.value

    def test_counts_failures(self, db, autonomous_agent, supervised_agent):
        svc = ProactiveMessagingService(db)
        for agent in (autonomous_agent, supervised_agent):
            msg = _pending(db, agent)
            msg.status = ProactiveMessageStatus.APPROVED.value
            msg.scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=10)
            db.commit()
        with patch("core.proactive_messaging_service.agent_integration_gateway") as gw:
            gw.execute_action = AsyncMock(return_value={
                "status": "error", "error": "down"})
            counts = run(svc.send_scheduled_messages())
        assert counts == {"sent": 0, "failed": 2}
