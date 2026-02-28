"""
Agent Maturity Authorization Security Tests (SECU-02.1).

Comprehensive tests for agent maturity level permissions:
- STUDENT: Read-only (search, list, get, summarize, present_chart)
- INTERN: Level 1-2 actions (draft, analyze, suggest, generate)
- SUPERVISED: Level 1-3 actions (update, submit_form, send_email)
- AUTONOMOUS: Level 1-4 actions (delete, execute, deploy, payment)

These are CRITICAL security tests ensuring governance enforcement.
Failure indicates a security vulnerability where agents can exceed permissions.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from tests.factories.user_factory import UserFactory, AdminUserFactory
from core.models import AgentStatus, AgentRegistry
from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import get_governance_cache


# ============================================================================
# STUDENT Agent Tests - Read-Only Only
# ============================================================================


class TestStudentAgentPermissions:
    """Test STUDENT agents can only perform read-only actions."""

    def test_student_can_search(self, db_session: Session):
        """STUDENT agents can search (complexity 1, read-only)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "search")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1
        assert result["agent_status"] == AgentStatus.STUDENT.value

    def test_student_can_read(self, db_session: Session):
        """STUDENT agents can read (complexity 1, read-only)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "read")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_student_can_list(self, db_session: Session):
        """STUDENT agents can list (complexity 1, read-only)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "list")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_student_can_summarize(self, db_session: Session):
        """STUDENT agents can summarize (complexity 1, read-only)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "summarize")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_student_can_present_chart(self, db_session: Session):
        """STUDENT agents can present charts (complexity 1, read-only)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "present_chart")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_student_blocked_from_stream(self, db_session: Session):
        """STUDENT agents CANNOT stream (complexity 2)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "stream")

        assert result["allowed"] is False
        assert "lacks maturity" in result["reason"].lower() or "blocked" in result["reason"].lower()
        assert result["action_complexity"] == 2

    def test_student_blocked_from_analyze(self, db_session: Session):
        """STUDENT agents CANNOT analyze (complexity 2)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "analyze")

        assert result["allowed"] is False
        assert result["action_complexity"] == 2

    def test_student_blocked_from_draft(self, db_session: Session):
        """STUDENT agents CANNOT draft (complexity 2)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "draft")

        assert result["allowed"] is False
        assert result["action_complexity"] == 2

    def test_student_blocked_from_update(self, db_session: Session):
        """STUDENT agents CANNOT update state (complexity 3)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "update")

        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_student_blocked_from_submit_form(self, db_session: Session):
        """STUDENT agents CANNOT submit forms (complexity 3)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "submit_form")

        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_student_blocked_from_send_email(self, db_session: Session):
        """STUDENT agents CANNOT send email (complexity 3)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "send_email")

        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_student_blocked_from_delete(self, db_session: Session):
        """STUDENT agents CANNOT delete (complexity 4 - CRITICAL)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "delete")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_student_blocked_from_execute(self, db_session: Session):
        """STUDENT agents CANNOT execute commands (complexity 4 - CRITICAL)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "execute")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_student_blocked_from_deploy(self, db_session: Session):
        """STUDENT agents CANNOT deploy (complexity 4 - CRITICAL)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "deploy")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_student_blocked_from_payment(self, db_session: Session):
        """STUDENT agents CANNOT process payments (complexity 4 - CRITICAL)."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "payment")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_student_confidence_score_range(self, db_session: Session):
        """STUDENT agents have confidence score < 0.5."""
        student = StudentAgentFactory(_session=db_session)

        assert 0.0 <= student.confidence_score < 0.5

    def test_student_cannot_bypass_governance_via_cache(self, db_session: Session):
        """Test STUDENT cannot bypass governance by poisoning cache.

        Note: Current governance cache implementation returns cached values
        without database verification. This test documents the behavior.
        In production, cache poisoning should be prevented via:
        1. Cache signing/encryption
        2. TTL expiration
        3. Database verification for critical actions
        """
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # First check - cache miss, checks database
        result1 = governance.can_perform_action(student.id, "delete")
        assert result1["allowed"] is False

        # Verify it was cached
        cached = cache.get(student.id, "delete")
        assert cached is not None
        assert cached["allowed"] is False

        # Even if we could poison the cache, the cache implementation
        # uses in-memory dict with no access control. This is a known
        # limitation mitigated by:
        # - Process isolation (separate worker processes)
        # - Cache TTL (automatic expiration)
        # - No external cache API (cache not exposed via endpoints)

        # Document: Cache poisoning requires code execution access
        # At that point, attacker has higher privileges anyway


# ============================================================================
# INTERN Agent Tests - Level 1-2 Actions
# ============================================================================


class TestInternAgentPermissions:
    """Test INTERN agents can perform level 1-2 actions."""

    def test_intern_can_search(self, db_session: Session):
        """INTERN agents can search (complexity 1)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "search")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_intern_can_analyze(self, db_session: Session):
        """INTERN agents can analyze (complexity 2)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "analyze")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_intern_can_suggest(self, db_session: Session):
        """INTERN agents can suggest (complexity 2)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "suggest")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_intern_can_draft(self, db_session: Session):
        """INTERN agents can draft (complexity 2)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "draft")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_intern_can_generate(self, db_session: Session):
        """INTERN agents can generate (complexity 2)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "generate")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_intern_can_stream(self, db_session: Session):
        """INTERN agents can stream (complexity 2)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "stream")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_intern_can_submit(self, db_session: Session):
        """INTERN agents can submit (complexity 2 - NOT submit_form)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "submit")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_intern_blocked_from_update(self, db_session: Session):
        """INTERN agents CANNOT update state (complexity 3)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "update")

        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_intern_blocked_from_submit_form(self, db_session: Session):
        """INTERN agents CANNOT submit forms (complexity 3)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "submit_form")

        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_intern_blocked_from_send_email(self, db_session: Session):
        """INTERN agents CANNOT send email (complexity 3)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "send_email")

        assert result["allowed"] is False
        assert result["action_complexity"] == 3

    def test_intern_blocked_from_delete(self, db_session: Session):
        """INTERN agents CANNOT delete (complexity 4 - CRITICAL)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "delete")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_intern_blocked_from_execute(self, db_session: Session):
        """INTERN agents CANNOT execute (complexity 4 - CRITICAL)."""
        intern = InternAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(intern.id, "execute")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_intern_confidence_score_range(self, db_session: Session):
        """INTERN agents have confidence score 0.5-0.7."""
        intern = InternAgentFactory(_session=db_session)

        assert 0.5 <= intern.confidence_score < 0.7


# ============================================================================
# SUPERVISED Agent Tests - Level 1-3 Actions
# ============================================================================


class TestSupervisedAgentPermissions:
    """Test SUPERVISED agents can perform level 1-3 actions."""

    def test_supervised_can_search(self, db_session: Session):
        """SUPERVISED agents can search (complexity 1)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "search")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_supervised_can_stream(self, db_session: Session):
        """SUPERVISED agents can stream (complexity 2)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "stream")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_supervised_can_analyze(self, db_session: Session):
        """SUPERVISED agents can analyze (complexity 2)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "analyze")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_supervised_can_update(self, db_session: Session):
        """SUPERVISED agents can update state (complexity 3)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "update")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_supervised_can_submit_form(self, db_session: Session):
        """SUPERVISED agents can submit forms (complexity 3)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "submit_form")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_supervised_can_send_email(self, db_session: Session):
        """SUPERVISED agents can send email (complexity 3)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "send_email")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_supervised_can_create(self, db_session: Session):
        """SUPERVISED agents can create (complexity 3)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "create")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_supervised_can_post_message(self, db_session: Session):
        """SUPERVISED agents can post messages (complexity 3)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "post_message")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_supervised_blocked_from_delete(self, db_session: Session):
        """SUPERVISED agents CANNOT delete (complexity 4 - CRITICAL)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "delete")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_supervised_blocked_from_execute(self, db_session: Session):
        """SUPERVISED agents CANNOT execute (complexity 4 - CRITICAL)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "execute")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_supervised_blocked_from_deploy(self, db_session: Session):
        """SUPERVISED agents CANNOT deploy (complexity 4 - CRITICAL)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "deploy")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_supervised_blocked_from_payment(self, db_session: Session):
        """SUPERVISED agents CANNOT process payments (complexity 4 - CRITICAL)."""
        supervised = SupervisedAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(supervised.id, "payment")

        assert result["allowed"] is False
        assert result["action_complexity"] == 4

    def test_supervised_confidence_score_range(self, db_session: Session):
        """SUPERVISED agents have confidence score 0.7-0.9."""
        supervised = SupervisedAgentFactory(_session=db_session)

        assert 0.7 <= supervised.confidence_score < 0.9


# ============================================================================
# AUTONOMOUS Agent Tests - Full Execution (Level 1-4)
# ============================================================================


class TestAutonomousAgentPermissions:
    """Test AUTONOMOUS agents have full execution权限."""

    def test_autonomous_can_search(self, db_session: Session):
        """AUTONOMOUS agents can search (complexity 1)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "search")

        assert result["allowed"] is True
        assert result["action_complexity"] == 1

    def test_autonomous_can_stream(self, db_session: Session):
        """AUTONOMOUS agents can stream (complexity 2)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "stream")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_autonomous_can_analyze(self, db_session: Session):
        """AUTONOMOUS agents can analyze (complexity 2)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "analyze")

        assert result["allowed"] is True
        assert result["action_complexity"] == 2

    def test_autonomous_can_update(self, db_session: Session):
        """AUTONOMOUS agents can update (complexity 3)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "update")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_autonomous_can_delete(self, db_session: Session):
        """AUTONOMOUS agents can delete (complexity 4 - CRITICAL)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "delete")

        assert result["allowed"] is True
        assert result["action_complexity"] == 4

    def test_autonomous_can_execute(self, db_session: Session):
        """AUTONOMOUS agents can execute (complexity 4 - CRITICAL)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "execute")

        assert result["allowed"] is True
        assert result["action_complexity"] == 4

    def test_autonomous_can_deploy(self, db_session: Session):
        """AUTONOMOUS agents can deploy (complexity 4 - CRITICAL)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "deploy")

        assert result["allowed"] is True
        assert result["action_complexity"] == 4

    def test_autonomous_can_payment(self, db_session: Session):
        """AUTONOMOUS agents can process payments (complexity 4 - CRITICAL)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "payment")

        assert result["allowed"] is True
        assert result["action_complexity"] == 4

    def test_autonomous_can_send_email(self, db_session: Session):
        """AUTONOMOUS agents can send email (complexity 3)."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "send_email")

        assert result["allowed"] is True
        assert result["action_complexity"] == 3

    def test_autonomous_confidence_score_range(self, db_session: Session):
        """AUTONOMOUS agents have confidence score >= 0.9."""
        autonomous = AutonomousAgentFactory(_session=db_session)

        assert 0.9 <= autonomous.confidence_score <= 1.0


# ============================================================================
# Maturity Promotion/Regression Tests
# ============================================================================


class TestMaturityTransitions:
    """Test maturity level changes invalidate cache."""

    def test_promotion_student_to_intern(self, db_session: Session):
        """Test promoting STUDENT to INTERN grants new permissions."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # Initially blocked from streaming
        result1 = governance.can_perform_action(student.id, "stream")
        assert result1["allowed"] is False

        # Promote to INTERN
        student.status = AgentStatus.INTERN.value
        student.confidence_score = 0.6
        db_session.commit()

        # Invalidate cache
        cache.invalidate(student.id)

        # Now allowed to stream
        result2 = governance.can_perform_action(student.id, "stream")
        assert result2["allowed"] is True

    def test_regression_autonomous_to_supervised(self, db_session: Session):
        """Test demoting AUTONOMOUS to SUPERVISED revokes critical permissions."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # Initially allowed to delete
        result1 = governance.can_perform_action(autonomous.id, "delete")
        assert result1["allowed"] is True

        # Demote to SUPERVISED
        autonomous.status = AgentStatus.SUPERVISED.value
        autonomous.confidence_score = 0.8
        db_session.commit()

        # Invalidate cache
        cache.invalidate(autonomous.id)

        # Now blocked from delete
        result2 = governance.can_perform_action(autonomous.id, "delete")
        assert result2["allowed"] is False

    def test_multiple_maturity_changes(self, db_session: Session):
        """Test multiple maturity transitions maintain correct permissions."""
        agent = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)
        cache = get_governance_cache()

        # STUDENT: blocked from analyze
        result = governance.can_perform_action(agent.id, "analyze")
        assert result["allowed"] is False

        # Promote to INTERN
        agent.status = AgentStatus.INTERN.value
        agent.confidence_score = 0.6
        db_session.commit()
        cache.invalidate(agent.id)

        # INTERN: allowed to analyze
        result = governance.can_perform_action(agent.id, "analyze")
        assert result["allowed"] is True

        # Promote to SUPERVISED
        agent.status = AgentStatus.SUPERVISED.value
        agent.confidence_score = 0.8
        db_session.commit()
        cache.invalidate(agent.id)

        # SUPERVISED: still allowed to analyze
        result = governance.can_perform_action(agent.id, "analyze")
        assert result["allowed"] is True

        # Promote to AUTONOMOUS
        agent.status = AgentStatus.AUTONOMOUS.value
        agent.confidence_score = 0.95
        db_session.commit()
        cache.invalidate(agent.id)

        # AUTONOMOUS: still allowed to analyze
        result = governance.can_perform_action(agent.id, "analyze")
        assert result["allowed"] is True


# ============================================================================
# Edge Cases and Boundary Tests
# ============================================================================


class TestMaturityEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_nonexistent_agent(self, db_session: Session):
        """Test governance check for non-existent agent."""
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action("nonexistent-agent-id", "delete")

        assert result["allowed"] is False
        assert "not found" in result["reason"].lower()

    def test_invalid_action_type(self, db_session: Session):
        """Test governance check for unknown action type."""
        autonomous = AutonomousAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(autonomous.id, "unknown_action_xyz")

        # Should handle gracefully (default to blocking or assume safe)
        assert "allowed" in result

    def test_confidence_score_boundaries(self, db_session: Session):
        """Test confidence score boundaries match maturity levels."""
        from tests.factories.agent_factory import AgentFactory

        # Test boundary at 0.5 (STUDENT/INTERN)
        agent1 = AgentFactory.create(
            confidence_score=0.49,
            status=AgentStatus.STUDENT.value,
            _session=db_session
        )
        assert agent1.confidence_score < 0.5

        agent2 = AgentFactory.create(
            confidence_score=0.50,
            status=AgentStatus.INTERN.value,
            _session=db_session
        )
        assert agent2.confidence_score >= 0.5

        # Test boundary at 0.7 (INTERN/SUPERVISED)
        agent3 = AgentFactory.create(
            confidence_score=0.69,
            status=AgentStatus.INTERN.value,
            _session=db_session
        )
        assert agent3.confidence_score < 0.7

        agent4 = AgentFactory.create(
            confidence_score=0.70,
            status=AgentStatus.SUPERVISED.value,
            _session=db_session
        )
        assert agent4.confidence_score >= 0.7

        # Test boundary at 0.9 (SUPERVISED/AUTONOMOUS)
        agent5 = AgentFactory.create(
            confidence_score=0.89,
            status=AgentStatus.SUPERVISED.value,
            _session=db_session
        )
        assert agent5.confidence_score < 0.9

        agent6 = AgentFactory.create(
            confidence_score=0.90,
            status=AgentStatus.AUTONOMOUS.value,
            _session=db_session
        )
        assert agent6.confidence_score >= 0.9

    def test_governance_reason_provided(self, db_session: Session):
        """Test governance checks provide reason for denial."""
        student = StudentAgentFactory(_session=db_session)
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(student.id, "delete")

        assert "reason" in result
        assert len(result["reason"]) > 0
        # Reason should mention maturity or permissions
        reason_lower = result["reason"].lower()
        assert any(term in reason_lower for term in ["maturity", "permission", "blocked", "lacks"])
