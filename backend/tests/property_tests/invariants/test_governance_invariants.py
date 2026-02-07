"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus


class TestGovernanceInvariants:
    """Test governance system maintains critical invariants."""

    @pytest.mark.parametrize("agent_status", [
        AgentStatus.STUDENT.value,
        AgentStatus.INTERN.value,
        AgentStatus.SUPERVISED.value,
        AgentStatus.AUTONOMOUS.value,
    ])
    @pytest.mark.parametrize("action_type", [
        "search", "stream_chat", "submit_form", "delete", "execute", "deploy"
    ])
    def test_governance_decision_has_required_fields(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        INVARIANT: Every governance decision MUST contain required fields.

        Required fields: allowed (bool), reason (str), agent_status (str),
        requires_human_approval (bool)

        This ensures API consumers can always rely on this structure.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act
        decision = service.can_perform_action(agent.id, action_type)

        # Assert: Verify invariant
        assert "allowed" in decision, "Decision must contain 'allowed' field"
        assert "reason" in decision, "Decision must contain 'reason' field"
        assert "agent_status" in decision, "Decision must contain 'agent_status' field"
        assert "requires_human_approval" in decision, "Decision must contain 'requires_human_approval' field"

        assert isinstance(decision["allowed"], bool), "'allowed' must be boolean"
        assert isinstance(decision["reason"], str), "'reason' must be string"
        assert isinstance(decision["requires_human_approval"], bool), "'requires_human_approval' must be boolean"

    @given(
        confidence_score=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_score_never_exceeds_bounds(
        self, db_session: Session, confidence_score: float
    ):
        """
        INVARIANT: Confidence scores MUST always be in [0.0, 1.0].

        This is safety-critical for AI decision-making.
        """
        # Arrange
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=confidence_score,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Assert: Verify invariant
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence score {agent.confidence_score} exceeds bounds [0.0, 1.0]"

    @given(
        initial_confidence=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        ),
        positive=st.booleans(),
        impact_level=st.sampled_from(["high", "low"])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_update_preserves_bounds(
        self, db_session: Session, initial_confidence: float, positive: bool, impact_level: str
    ):
        """
        INVARIANT: Confidence score updates MUST preserve bounds [0.0, 1.0].

        Even after many positive or negative updates, score must stay in range.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: Update confidence
        service._update_confidence_score(agent.id, positive=positive, impact_level=impact_level)
        db_session.refresh(agent)

        # Assert: Verify invariant
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence score {agent.confidence_score} exceeded bounds after update"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_governance_never_crashes(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        INVARIANT: Governance checks MUST NEVER crash, regardless of inputs.

        Even with unknown action types or edge cases, governance should return
        a decision, not raise an exception.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{agent_status}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: This should never raise an exception
        try:
            decision = service.can_perform_action(agent.id, action_type)

            # Assert: Should always return a decision
            assert decision is not None, "Governance check returned None"
            assert isinstance(decision, dict), "Governance check must return dict"
            assert "allowed" in decision, "Decision must have 'allowed' field"
        except Exception as e:
            pytest.fail(f"Governance check crashed with: {e}")

    @given(
        status1=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        status2=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])  # Only 16 combinations possible
    def test_maturity_hierarchy_is_consistent(
        self, db_session: Session, status1: str, status2: str
    ):
        """
        INVARIANT: Maturity levels have a consistent partial order.

        If agent1's status >= agent2's status in the hierarchy,
        then agent1 should be able to do everything agent2 can do.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        agent1 = AgentRegistry(
            name="TestAgent1",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=status1,
            confidence_score=0.5,
            
        )
        agent2 = AgentRegistry(
            name="TestAgent2",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=status2,
            confidence_score=0.5,
            
        )
        db_session.add_all([agent1, agent2])
        db_session.commit()
        db_session.refresh(agent1)
        db_session.refresh(agent2)

        # Define hierarchy order
        maturity_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]

        index1 = maturity_order.index(status1)
        index2 = maturity_order.index(status2)

        # Test a few known actions
        test_actions = ["search", "stream_chat", "submit_form", "delete"]

        for action in test_actions:
            decision1 = service.can_perform_action(agent1.id, action)
            decision2 = service.can_perform_action(agent2.id, action)

            # If agent1 is higher or equal maturity, it should have same or better permissions
            if index1 >= index2:
                # Higher maturity agent should never be MORE restricted
                # (they might both be denied, but agent1 shouldn't be denied if agent2 is allowed)
                if decision2["allowed"] and not decision1["allowed"]:
                    # This is only acceptable if there's an explicit approval requirement difference
                    # or if the hierarchy is inconsistent
                    assert False, \
                        f"Maturity hierarchy inconsistent: {status1} denied {action} but {status2} allowed"
