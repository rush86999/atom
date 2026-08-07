"""
Bug-hunt tests for core/proactive_messaging_service.py.

These tests are deliberately isolated: each spins up its own in-memory SQLite
database (via core.database.Base) and mocks external integrations
(agent_integration_gateway), so no real services or network are involved.

Each test asserts the *correct* behaviour and therefore FAILS against the
current (buggy) implementation. Tests are tagged with a ``BUG:`` docstring.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
try:
    # Python 3.8+
    from unittest.mock import AsyncMock
except ImportError:  # pragma: no cover
    AsyncMock = None

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
)
from core.proactive_messaging_service import ProactiveMessagingService


def _fresh_session():
    """Create a brand-new in-memory SQLite session with all tables."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _make_agent(db, status, name="Agent"):
    agent = AgentRegistry(
        name=name,
        category="testing",
        module_path="test.module",
        class_name="Agent",
        description="test agent",
        status=status,
        confidence_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _make_user(db, email="approver@example.com"):
    user = User(
        email=email,
        first_name="App",
        last_name="Rover",
        role=UserRole.MEMBER.value,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# BUG A
# ---------------------------------------------------------------------------


class TestApproveScheduledInternMessageTypeError:
    """approve_message crashes on any INTERN message that has a scheduled_for."""

    def test_approve_scheduled_intern_message_does_not_crash(self):
        """BUG: approve_message raises TypeError comparing offset-naive
        scheduled_for (tzinfo stripped by SQLite on refresh) against offset-aware
        datetime.now(timezone.utc) at line 219, crashing the approval flow for
        every INTERN message with a scheduled_for (past OR future)."""
        db = _fresh_session()
        try:
            intern = _make_agent(db, AgentStatus.INTERN.value, "Intern")
            approver = _make_user(db)
            service = ProactiveMessagingService(db)

            # INTERN -> stays PENDING, with a scheduled_for in the past.
            scheduled_for = datetime.now(timezone.utc) - timedelta(hours=1)
            message = service.create_proactive_message(
                agent_id=intern.id,
                platform="slack",
                recipient_id="C123",
                content="scheduled intern message",
                scheduled_for=scheduled_for,
            )
            assert message.status == ProactiveMessageStatus.PENDING.value

            # Mock the gateway so the past-due send (now triggered by the fix)
            # succeeds rather than stranding the message. execute_action is
            # awaited inside _send_message, so it must be an AsyncMock.
            gateway_mock = MagicMock()
            gateway_mock.execute_action = (
                AsyncMock(return_value={"status": "success", "message_id": "plat-1"})
                if AsyncMock
                else MagicMock(return_value={"status": "success", "message_id": "plat-1"})
            )

            # Approving must not raise TypeError. With the bug, the naive-vs-
            # aware comparison raises before the send can happen.
            with patch(
                "core.proactive_messaging_service.agent_integration_gateway",
                gateway_mock,
            ):
                approved = service.approve_message(
                    message_id=message.id,
                    approver_user_id=approver.id,
                )

            # Past-due + successful send => SENT; approver recorded.
            assert approved.approved_by == approver.id
            assert gateway_mock.execute_action.called
            assert approved.status == ProactiveMessageStatus.SENT.value
        finally:
            db.close()

    def test_approve_future_scheduled_intern_message_does_not_crash(self):
        """BUG: same TypeError as above but for a FUTURE scheduled_for. The
        comparison is evaluated before its result could short-circuit, so a
        future-scheduled INTERN message cannot be approved either (it should be
        approved and left for send_scheduled_messages)."""
        db = _fresh_session()
        try:
            intern = _make_agent(db, AgentStatus.INTERN.value, "Intern2")
            approver = _make_user(db, "approver2@example.com")
            service = ProactiveMessagingService(db)

            scheduled_for = datetime.now(timezone.utc) + timedelta(hours=2)
            message = service.create_proactive_message(
                agent_id=intern.id,
                platform="slack",
                recipient_id="C456",
                content="future scheduled intern message",
                scheduled_for=scheduled_for,
            )
            assert message.status == ProactiveMessageStatus.PENDING.value

            approved = service.approve_message(
                message_id=message.id,
                approver_user_id=approver.id,
            )

            # Should be APPROVED (and NOT sent yet, because it is in the future).
            assert approved.status == ProactiveMessageStatus.APPROVED.value
            assert approved.sent_at is None
        finally:
            db.close()


# ---------------------------------------------------------------------------
# BUG B
# ---------------------------------------------------------------------------


class TestApproveImmediateSendWithoutEventLoop:
    """approve_message silently never sends when there is no running event loop."""

    def test_approve_immediate_message_actually_sends(self):
        """BUG: approve_message relies on asyncio.create_task to send a no-schedule
        INTERN message immediately (line 219-224). When invoked outside a running
        event loop (the common sync/celery/CLI case) create_task raises
        RuntimeError, which is swallowed; the gateway is never called and the
        message is stranded in APPROVED with sent_at=None despite the docstring
        stating it should be sent. The log message even claims it was "queued
        for background send" but no such queue exists."""
        db = _fresh_session()
        try:
            intern = _make_agent(db, AgentStatus.INTERN.value, "Intern3")
            approver = _make_user(db, "approver3@example.com")
            service = ProactiveMessagingService(db)

            message = service.create_proactive_message(
                agent_id=intern.id,
                platform="slack",
                recipient_id="C789",
                content="approve and send immediately",
            )
            assert message.status == ProactiveMessageStatus.PENDING.value

            gateway_mock = MagicMock()
            gateway_mock.execute_action = (
                AsyncMock(return_value={"status": "success", "message_id": "plat-1"})
                if AsyncMock
                else MagicMock(return_value={"status": "success", "message_id": "plat-1"})
            )

            # Ensure we exercise the no-running-loop code path: prior tests in
            # this module may have left a (closed) loop on the policy, so reset
            # to a clean policy and confirm there is no running loop.
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            assert asyncio.get_event_loop_policy().get_event_loop().is_running() is False

            with patch(
                "core.proactive_messaging_service.agent_integration_gateway",
                gateway_mock,
            ):
                approved = service.approve_message(
                    message_id=message.id,
                    approver_user_id=approver.id,
                )

            # Correct behaviour: the message must actually be sent.
            assert gateway_mock.execute_action.called, (
                "approve_message should deliver the message to the gateway when "
                "scheduled_for is None, but it never does outside an event loop"
            )
            assert approved.status == ProactiveMessageStatus.SENT.value
            assert approved.sent_at is not None
        finally:
            db.close()
