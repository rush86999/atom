"""
Tests for student learning pathways (core/student_learning_service.py) and
the teach_student governance contract.
"""

import uuid

import pytest
from unittest.mock import MagicMock

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, HITLAction, WorkflowExecutionLog
from core.student_learning_service import StudentLearningService


def _make_student(db_session, status="student", confidence=0.1, capabilities=None):
    agent = AgentRegistry(
        id=f"student-{uuid.uuid4().hex[:8]}",
        name="Learner",
        category="General",
        description="test student",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=status,
        confidence_score=confidence,
        capabilities=capabilities or ["send_email"],
        configuration={},
        workspace_id="default",
        tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


class TestTeacherPathway:
    def test_teacher_lesson_boosts_confidence_and_logs(self, db_session):
        student = _make_student(db_session)
        service = StudentLearningService(db_session)

        result = service.learn_from_teacher(student.id, "atom_main", "Always double-check invoice totals", topic="invoices")

        assert result["status"] == "ok"
        assert result["confidence_boost"] == pytest.approx(0.05)
        db_session.refresh(student)
        assert student.confidence_score == pytest.approx(0.15)
        entry = student.configuration["learning"]["log"][0]
        assert entry["source"] == "teacher"
        assert entry["teacher_agent_id"] == "atom_main"
        assert entry["topic"] == "invoices"
        assert student.configuration["learning"]["pathways_used"] == ["teacher"]

    def test_teaching_cannot_cross_learning_ceiling(self, db_session):
        student = _make_student(db_session, confidence=0.43)
        service = StudentLearningService(db_session)

        result = service.learn_from_teacher(student.id, "atom_main", "final lesson")

        db_session.refresh(student)
        assert student.confidence_score == pytest.approx(0.45)
        assert result["at_learning_ceiling"] is True
        # Still a STUDENT — promotion belongs to training/graduation only
        assert student.status == "student"

    def test_non_student_agents_do_not_learn(self, db_session):
        intern = _make_student(db_session, status="intern")
        service = StudentLearningService(db_session)

        result = service.learn_from_teacher(intern.id, "atom_main", "lesson")

        assert result["status"] == "error"
        assert result["reason"] == "student_not_found"

    def test_missing_student_returns_error(self, db_session):
        service = StudentLearningService(db_session)
        result = service.learn_from_teacher("nope", "atom_main", "lesson")
        assert result["status"] == "error"


class TestObservationPathway:
    def test_observation_boost_is_smaller(self, db_session):
        student = _make_student(db_session, capabilities=["send_email"])
        service = StudentLearningService(db_session)

        result = service.learn_from_observation(student.id, "hitl_approval", "A human approved 'send_email'")

        assert result["status"] == "ok"
        assert result["confidence_boost"] == pytest.approx(0.01)
        db_session.refresh(student)
        entry = student.configuration["learning"]["log"][0]
        assert entry["source"] == "observation"
        assert entry["observation_type"] == "hitl_approval"

    def test_both_pathways_recorded(self, db_session):
        student = _make_student(db_session)
        service = StudentLearningService(db_session)
        service.learn_from_teacher(student.id, "atom_main", "lesson")
        service.learn_from_observation(student.id, "workflow_execution", "watched a step complete")

        db_session.refresh(student)
        assert student.configuration["learning"]["pathways_used"] == ["observation", "teacher"]

    def test_observe_workspace_absorbs_approvals_and_runs(self, db_session):
        student = _make_student(db_session)
        db_session.add(HITLAction(
            workspace_id="default",
            agent_id="some-agent",
            action_type="send_email",
            platform="internal",
            params={},
            status="approved",
            reason="looked safe",
        ))
        db_session.add(WorkflowExecutionLog(
            execution_id="exec-1",
            workflow_id="wf-1",
            step_id="s1",
            step_type="action",
            status="completed",
        ))
        db_session.commit()

        service = StudentLearningService(db_session)
        result = service.observe_workspace(student.id, workspace_id="default", limit=10)

        assert result["status"] == "ok"
        assert result["observations_absorbed"] == 2
        db_session.refresh(student)
        log = student.configuration["learning"]["log"]
        assert {e["observation_type"] for e in log} == {"hitl_approval", "workflow_execution"}


class TestTeachGovernance:
    """Teaching must be permitted regardless of the teacher's own maturity."""

    @pytest.mark.parametrize("teacher_status", ["student", "intern", "supervised", "autonomous"])
    def test_teach_student_allowed_at_every_maturity(self, db_session, teacher_status):
        teacher = _make_student(db_session, status=teacher_status)
        gov = AgentGovernanceService(db_session, workspace_id="default", tenant_id="default")

        decision = gov.can_perform_action(agent_id=teacher.id, action_type="teach_student")

        assert decision["allowed"] is True, f"teach_student must be allowed at {teacher_status}: {decision}"

    def test_suggest_still_requires_intern(self, db_session):
        """The meta agent's INTER floor for suggestions stays enforced."""
        student = _make_student(db_session, status="student")
        intern = _make_student(db_session, status="intern")
        gov = AgentGovernanceService(db_session, workspace_id="default", tenant_id="default")

        assert gov.can_perform_action(agent_id=student.id, action_type="suggest")["allowed"] is False
        assert gov.can_perform_action(agent_id=intern.id, action_type="suggest")["allowed"] is True
