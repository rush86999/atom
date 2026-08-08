"""
TDD bug test: AgentGovernanceService maturity lookup is case-sensitive.

BUG: ``maturity_order.index(agent.status)`` compares the DB status string
verbatim. When an agent's status is stored with a non-lowercase spelling
(e.g. "AUTONOMOUS" written by an API/client), the lookup misses and the
agent is silently treated as STUDENT (index 0) — a fully-trusted agent is
denied HIGH-complexity actions.

FIX: normalize with ``.lower()`` before the index lookup.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, Base


@pytest.fixture
def db_session():
    """In-memory SQLite session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_agent(db_session, status: str) -> AgentRegistry:
    """Create an agent with the given (raw, unnormalized) status string."""
    agent = AgentRegistry(
        id=f"agent-{uuid.uuid4()}",
        name="Case Test Agent",
        category="testing",
        module_path="test.module",
        class_name="TestCaseAgent",
        description="Agent for maturity case-sensitivity test",
        status=status,
        workspace_id="default",
        confidence_score=0.95,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


class TestMaturityStatusCaseNormalization:
    """Non-lowercase stored statuses must resolve to the right tier."""

    def test_uppercase_autonomous_allowed_high_complexity(self, db_session):
        """'AUTONOMOUS' (uppercase) must not be downgraded to STUDENT."""
        agent = make_agent(db_session, "AUTONOMOUS")
        service = AgentGovernanceService(db_session, workspace_id="default")

        result = service.can_perform_action(
            agent.id,
            "create_workflow",  # complexity 3 -> SUPERVISED floor
            _skip_budget=True,
        )

        assert result["allowed"] is True, (
            "uppercase AUTONOMOUS status was treated as STUDENT: "
            f"{result['reason']}"
        )

    def test_uppercase_supervised_allowed_medium_complexity(self, db_session):
        """'SUPERVISED' (uppercase) must still pass complexity-2 actions."""
        agent = make_agent(db_session, "SUPERVISED")
        service = AgentGovernanceService(db_session, workspace_id="default")

        result = service.can_perform_action(
            agent.id,
            "stream_response",  # complexity 2 -> INTERN floor
            _skip_budget=True,
        )

        assert result["allowed"] is True, (
            "uppercase SUPERVISED status was treated as STUDENT: "
            f"{result['reason']}"
        )

    def test_uppercase_student_still_blocked_high_complexity(self, db_session):
        """'STUDENT' (uppercase) must still be blocked from complexity-3."""
        agent = make_agent(db_session, "STUDENT")
        service = AgentGovernanceService(db_session, workspace_id="default")

        result = service.can_perform_action(
            agent.id,
            "create_workflow",
            _skip_budget=True,
        )

        assert result["allowed"] is False, (
            "uppercase STUDENT status was granted HIGH complexity actions"
        )

    def test_uppercase_supervised_requires_approval_at_complexity_3(self, db_session):
        """'SUPERVISED' (uppercase) must still trigger the HITL approval gate."""
        agent = make_agent(db_session, "SUPERVISED")
        service = AgentGovernanceService(db_session, workspace_id="default")

        result = service.can_perform_action(
            agent.id,
            "create_workflow",  # complexity 3 == SUPERVISED floor
            _skip_budget=True,
        )

        assert result["allowed"] is True
        assert result["requires_human_approval"] is True, (
            "uppercase SUPERVISED status skipped the approval gate"
        )

    def test_uppercase_paused_agent_still_blocked(self, db_session):
        """'PAUSED' (uppercase) must still be blocked from all actions."""
        agent = make_agent(db_session, "PAUSED")
        service = AgentGovernanceService(db_session, workspace_id="default")

        result = service.can_perform_action(
            agent.id,
            "read_document",
            _skip_budget=True,
        )

        assert result["allowed"] is False, (
            "uppercase PAUSED status was treated as an active agent"
        )

    def test_lowercase_autonomous_regression(self, db_session):
        """Lowercase 'autonomous' behavior is unchanged (regression guard)."""
        agent = make_agent(db_session, AgentStatus.AUTONOMOUS.value)
        service = AgentGovernanceService(db_session, workspace_id="default")

        result = service.can_perform_action(
            agent.id,
            "create_workflow",
            _skip_budget=True,
        )

        assert result["allowed"] is True
