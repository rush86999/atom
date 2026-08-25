# -*- coding: utf-8 -*-
"""Round 82 — journey gap fixes found while tracing user/agent journeys.

Covers four severed/buggy journey links:

A2. Feedback polarity: ``POST /api/reasoning/feedback`` forwards
    thumbs_up/thumbs_down but ``AgentGovernanceService._adjudicate_feedback``
    ALWAYS applied the negative branch — a trusted user's thumbs-up LOWERED
    agent confidence by 0.10. Approval tokens must raise confidence; an
    untrusted thumbs-up must not penalize at all. Polarity must survive even
    when a comment overrides ``user_correction`` (route stores feedback_type
    inside input_context).

R2. ``fleet_router_automation._admin_recipient`` queried UPPERCASE role
    strings ("SUPER_ADMIN") while the DB stores lowercase enum values — the
    lookup always returned None so fleet-router notifications were never
    delivered.

R1. ``budget_enforcement_service._send_enforcement_notification`` filtered
    admins to ["admin", "owner", "billing_admin"] — "billing_admin" is not a
    UserRole value, and the actual bootstrap role workspace_admin (plus
    super_admin) was missing, so enforcement mail fell back to "any tenant
    user".

R3. ``overage_service._send_expiry_notification`` matched ``User.role ==
    "admin"`` exactly — bootstrap admins are workspace_admin, so fleet-expiry
    notifications went nowhere.
"""
import json
import uuid
from unittest.mock import AsyncMock

import pytest

from core.agent_governance_service import AgentGovernanceService
from core.fleet_orchestration.fleet_router_automation import _admin_recipient
from core.models import (
    AgentFeedback,
    AgentRegistry,
    FeedbackStatus,
    User,
    UserRole,
    Workspace,
)
from core.budget_enforcement_service import BudgetEnforcementService
from core.fleet_orchestration.overage_service import OverageService

from tests.factories.agent_factory import InternAgentFactory
from tests.factories.user_factory import UserFactory


# ============================================================================
# A2 — feedback polarity
# ============================================================================


class TestFeedbackPolarity:
    @pytest.mark.asyncio
    async def test_trusted_thumbs_up_raises_confidence(self, db_session):
        """A trusted reviewer's thumbs_up must INCREASE confidence (+0.05)."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.55)
        admin = UserFactory(
            _session=db_session, role=UserRole.WORKSPACE_ADMIN.value
        )

        service = AgentGovernanceService(db_session)
        await service.submit_feedback(
            agent_id=agent.id,
            user_id=admin.id,
            original_output="step output",
            user_correction="thumbs_up",
        )

        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.60)

    @pytest.mark.asyncio
    async def test_trusted_thumbs_down_lowers_confidence(self, db_session):
        """A trusted reviewer's thumbs_down must DECREASE confidence (-0.10)."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.55)
        admin = UserFactory(
            _session=db_session, role=UserRole.WORKSPACE_ADMIN.value
        )

        service = AgentGovernanceService(db_session)
        feedback = await service.submit_feedback(
            agent_id=agent.id,
            user_id=admin.id,
            original_output="step output",
            user_correction="thumbs_down",
        )

        db_session.refresh(agent)
        assert agent.confidence_score == pytest.approx(0.45)
        assert feedback.status == FeedbackStatus.ACCEPTED.value

    @pytest.mark.asyncio
    async def test_untrusted_thumbs_up_does_not_penalize(self, db_session):
        """An untrusted member's thumbs_up stays pending WITHOUT penalizing."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.55)
        member = UserFactory(_session=db_session, role=UserRole.MEMBER.value)

        service = AgentGovernanceService(db_session)
        feedback = await service.submit_feedback(
            agent_id=agent.id,
            user_id=member.id,
            original_output="step output",
            user_correction="thumbs_up",
        )

        db_session.refresh(agent)
        assert feedback.status == FeedbackStatus.PENDING.value
        # No penalty: approval from an untrusted user must not lower trust.
        assert agent.confidence_score == pytest.approx(0.55)

    @pytest.mark.asyncio
    async def test_comment_with_approval_context_is_positive(self, db_session):
        """When a comment replaces user_correction, polarity comes from
        input_context.feedback_type (stored by /api/reasoning/feedback)."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.55)
        admin = UserFactory(
            _session=db_session, role=UserRole.WORKSPACE_ADMIN.value
        )

        context = {
            "run_id": "run-1",
            "step_index": 1,
            "feedback_type": "thumbs_up",
            "step_content": {},
        }
        feedback = AgentFeedback(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=admin.id,
            original_output='"thought"',
            user_correction="great work, keep going",
            input_context=json.dumps(context),
            status="PENDING",
        )
        db_session.add(feedback)
        db_session.commit()

        service = AgentGovernanceService(db_session)
        await service._adjudicate_feedback(feedback)

        db_session.refresh(agent)
        assert feedback.status == FeedbackStatus.ACCEPTED.value
        assert agent.confidence_score == pytest.approx(0.60)


class TestReasoningRouteStoresPolarity:
    def test_route_stores_feedback_type_alongside_comment(self):
        """POST /api/reasoning/feedback with comment + thumbs_up must keep the
        feedback_type discoverable inside input_context."""
        from datetime import datetime, timezone
        from unittest.mock import MagicMock, patch

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.reasoning_routes import router
        from core.auth import get_current_user
        from core.database import get_db

        user = MagicMock()
        user.id = "user-1"
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: user

        gov = MagicMock()
        gov.submit_feedback = AsyncMock(return_value=MagicMock(id="fb-1"))
        with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov):
            client = TestClient(app)
            resp = client.post(
                "/api/reasoning/feedback",
                json={
                    "agent_id": "agent-1",
                    "run_id": "run-1",
                    "step_index": 0,
                    "step_content": {"thought": "x"},
                    "feedback_type": "thumbs_up",
                    "comment": "nice reasoning",
                },
            )
        assert resp.status_code == 200
        ctx = json.loads(gov.submit_feedback.call_args.kwargs["input_context"])
        assert ctx["feedback_type"] == "thumbs_up"


# ============================================================================
# R2 — fleet router automation admin recipient
# ============================================================================


class _FakeSessionFactory:
    """Wraps a session so ``with SessionLocal() as db:`` works."""

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    def __enter__(self):
        return self._session

    def __exit__(self, *args):
        return False


class TestFleetAdminRecipient:
    def test_lowercase_roles_match(self, db_session, monkeypatch):
        """DB stores lowercase enum values; recipient lookup must find them."""
        admin = UserFactory(
            _session=db_session, role=UserRole.WORKSPACE_ADMIN.value
        )
        monkeypatch.setattr(
            "core.database.SessionLocal", _FakeSessionFactory(db_session)
        )
        assert _admin_recipient() == admin.id


# ============================================================================
# R1 — budget enforcement notification recipients
# ============================================================================


class TestBudgetEnforcementRecipients:
    @pytest.mark.asyncio
    async def test_workspace_admin_receives_enforcement_notice(self, db_session):
        """workspace_admin (the bootstrap role) must be a recipient.

        Member row is inserted FIRST so the old ``limit(1) any-user``
        fallback deterministically picked the wrong recipient.
        """
        member = UserFactory(
            _session=db_session, role=UserRole.MEMBER.value, tenant_id="default"
        )
        ws_admin = UserFactory(
            _session=db_session,
            role=UserRole.WORKSPACE_ADMIN.value,
            tenant_id="default",
        )
        db_session.add(Workspace(name="ws", tenant_id="default"))
        db_session.commit()

        svc = BudgetEnforcementService(db=db_session)
        svc.notification_service = AsyncMock()

        sent = await svc._send_enforcement_notification(
            tenant_id="default",
            mode="soft_stop",
            current_spend=120.0,
            budget_limit=100.0,
            utilization_percent=120.0,
            details="",
        )

        assert sent is True
        recipients = [
            call.args[0]
            for call in svc.notification_service.send_notification.await_args_list
        ]
        assert recipients == [str(ws_admin.id)]
        assert str(member.id) not in recipients


# ============================================================================
# R3 — overage expiry notification
# ============================================================================


@pytest.mark.asyncio
class TestOverageExpiryRecipient:
    async def test_workspace_admin_gets_expiry_notice(self, db_session):
        """Exact-match 'admin' missed the bootstrap workspace_admin role."""
        ws_admin = UserFactory(
            _session=db_session,
            role=UserRole.WORKSPACE_ADMIN.value,
            tenant_id="default",
        )
        db_session.commit()

        svc = OverageService(db_session)
        svc.notification_service = AsyncMock()

        await svc._send_expiry_notification(
            tenant_id="default", chain_id="c-1", base_limit=5, previous_size=9
        )

        svc.notification_service.send_notification.assert_awaited_once()
        assert (
            svc.notification_service.send_notification.await_args.kwargs["user_id"]
            == str(ws_admin.id)
        )
