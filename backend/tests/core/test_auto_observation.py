"""
Tests for automated student observation triggers:
- dispatch_observation_event relevance filtering + fan-out
- HITL approval/rejection auto-observes
- workflow completion auto-observes
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import AgentRegistry, AgentStatus, HITLAction, User
from core.student_learning_service import StudentLearningService, auto_observe


def _make_student(db_session, capabilities=None, workspace_id="default"):
    agent = AgentRegistry(
        id=f"obs-{uuid.uuid4().hex[:8]}",
        name="Observer",
        category="General",
        description="observer test agent",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status="student",
        confidence_score=0.1,
        capabilities=capabilities,
        configuration={},
        workspace_id=workspace_id,
        tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


class TestDispatchObservationEvent:
    def test_fans_out_to_relevant_students_only(self, db_session):
        email_student = _make_student(db_session, capabilities=["send_email", "draft_email"])
        cal_student = _make_student(db_session, capabilities=["schedule_meeting"])
        service = StudentLearningService(db_session)

        count = service.dispatch_observation_event(
            workspace_id="default",
            observation_type="hitl_approval",
            summary="A human approved 'send_email'",
            action_type="send_email",
        )

        assert count == 1
        db_session.refresh(email_student)
        db_session.refresh(cal_student)
        assert email_student.configuration["learning"]["log"]
        assert not cal_student.configuration.get("learning", {}).get("log")

    def test_generalist_students_observe_everything(self, db_session):
        generalist = _make_student(db_session, capabilities=None)
        service = StudentLearningService(db_session)

        count = service.dispatch_observation_event(
            workspace_id="default",
            observation_type="hitl_approval",
            summary="A human approved 'delete_record'",
            action_type="delete_record",
        )
        assert count == 1
        db_session.refresh(generalist)
        assert generalist.configuration["learning"]["log"][0]["summary"].startswith("A human approved")

    def test_non_students_excluded(self, db_session):
        intern = AgentRegistry(
            id=f"int-{uuid.uuid4().hex[:8]}", name="I", category="General",
            description="intern", module_path="core.generic_agent", class_name="GenericAgent",
            status="intern", confidence_score=0.6, configuration={}, capabilities=None,
            workspace_id="default", tenant_id="default",
        )
        db_session.add(intern)
        db_session.commit()

        count = StudentLearningService(db_session).dispatch_observation_event(
            workspace_id="default",
            observation_type="hitl_approval",
            summary="A human approved 'send_email'",
            action_type="send_email",
        )
        assert count == 0

    def test_workspace_scoped(self, db_session):
        _make_student(db_session, workspace_id="other-ws")
        service = StudentLearningService(db_session)

        count = service.dispatch_observation_event(
            workspace_id="default",
            observation_type="workflow_execution",
            summary="Workflow completed",
        )
        assert count == 0


class TestAutoObserveFunction:
    @pytest.mark.asyncio
    async def test_auto_observe_opens_own_session(self, db_session):
        student = _make_student(db_session)
        dispatch_mock = MagicMock(return_value=1)
        session_ctx = MagicMock()
        session_ctx.close = MagicMock()

        with patch("core.database.SessionLocal", return_value=session_ctx), \
             patch.object(StudentLearningService, "dispatch_observation_event", dispatch_mock):
            await auto_observe(
                workspace_id="default",
                observation_type="hitl_approval",
                summary="A human approved 'send_email'",
                action_type="send_email",
            )

        dispatch_mock.assert_called_once()
        assert dispatch_mock.call_args.kwargs["observation_type"] == "hitl_approval"
        session_ctx.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_observe_never_raises(self):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
            await auto_observe("default", "x", "y")  # must not raise


class TestHitlTriggersObservation:
    @pytest.mark.asyncio
    async def test_approval_fires_observation_event(self, db_session):
        from core.hitl_service import HITLService

        user = User(id="u-obs-1", email="observer@example.com", first_name="O", last_name="B", role="user", status="active")
        db_session.add(user)
        action = HITLAction(
            id="act-obs-1", workspace_id="default", agent_id="a1",
            action_type="send_email", platform="internal", params={},
            status="pending", reason="needs review",
        )
        db_session.add(action)
        db_session.commit()

        auto_mock = AsyncMock()
        with patch("core.hitl_service.get_db_session", return_value=db_session), \
             patch("core.student_learning_service.auto_observe", auto_mock):
            result = await HITLService().resolve_action(
                action_id="act-obs-1", resolution="approved", resolver_id="u-obs-1"
            )
            await asyncio.sleep(0.05)

        assert result["status"] == "approved"
        auto_mock.assert_awaited_once()
        kwargs = auto_mock.await_args.kwargs
        assert kwargs["observation_type"] == "hitl_approval"
        assert kwargs["action_type"] == "send_email"
        assert "approved" in kwargs["summary"]

    @pytest.mark.asyncio
    async def test_rejection_fires_correction_observation(self, db_session):
        from core.hitl_service import HITLService

        user = User(id="u-obs-2", email="observer2@example.com", first_name="O", last_name="B", role="user", status="active")
        db_session.add(user)
        action = HITLAction(
            id="act-obs-2", workspace_id="default", agent_id="a1",
            action_type="bulk_delete", platform="internal", params={},
            status="pending", reason="too risky",
        )
        db_session.add(action)
        db_session.commit()

        auto_mock = AsyncMock()
        with patch("core.hitl_service.get_db_session", return_value=db_session), \
             patch("core.student_learning_service.auto_observe", auto_mock):
            result = await HITLService().resolve_action(
                action_id="act-obs-2", resolution="rejected", resolver_id="u-obs-2"
            )
            await asyncio.sleep(0.05)

        assert result["status"] == "rejected"
        auto_mock.assert_awaited_once()
        kwargs = auto_mock.await_args.kwargs
        assert kwargs["observation_type"] == "hitl_rejection"
        assert kwargs["action_type"] == "bulk_delete"
